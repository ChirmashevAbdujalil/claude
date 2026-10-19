import io
import zipfile
from xml.dom import minidom

import pytest
from django.contrib.auth import authenticate
from django.test import Client
from django.urls import reverse

from apps.accounts.models import Faculty, User
from apps.audit.models import AuditLog
from apps.surveys import accounts, services
from apps.surveys.models import IssuedAccount, Question
from apps.talent.tracks import Track


@pytest.fixture
def rector(make_user):
    return make_user(role=User.Role.RECTOR, username="rektor")


@pytest.fixture
def survey(rector):
    survey = services.create_survey(rector, "census")
    services.publish(survey)
    return survey


def answer(survey, faculty, name="Karimova Aziza Rustamovna", phone="+998 90 123 45 67", **extra):
    track = survey.questions.get(kind=Question.Kind.TRACK)
    identity = {"full_name": name, "faculty": faculty, "course": 2, "group": "210-21", "phone": phone, **extra}
    return services.submit(survey, answers={str(track.pk): Track.IT}, identity=identity)


def web(user=None):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


# ---------------------------------------------------------------- akkaunt ochish


def test_anonymous_answer_creates_student_account(survey, faculty):
    response = answer(survey, faculty)
    student = response.user
    assert student.role == User.Role.STUDENT and student.first_name == "Aziza" and student.last_name == "Karimova"
    assert student.username == "aziza.karimova" and student.faculty == faculty and student.course == 2
    issued = student.issued_account
    assert issued.survey == survey and issued.group == "210-21" and issued.must_change_password
    assert authenticate(username=student.username, password=issued.initial_password) == student
    assert len(issued.initial_password) == 9 and "-" in issued.initial_password
    student.refresh_from_db()
    assert student.xp == survey.xp_reward  # javob uchun XP yangi akkauntga yozildi


def test_same_student_reuses_account_by_phone(rector, survey, faculty):
    first = answer(survey, faculty)
    other = services.create_survey(rector, "feedback")
    other.collect_identity = True
    other.save()
    services.publish(other)
    second = services.submit(
        other, answers={}, identity={"full_name": "Karimova Aziza", "faculty": faculty, "phone": "90-123-45-67"}
    )
    assert second.user == first.user and IssuedAccount.objects.count() == 1


def test_namesakes_get_unique_logins_and_cyrillic_is_transliterated(survey, faculty):
    a = answer(survey, faculty, phone="+998901111111")
    b = answer(survey, faculty, phone="+998902222222", course=3)
    c = answer(survey, faculty, name="Қодиров Шоҳрух", phone="")
    assert a.user != b.user and b.user.username == "aziza.karimova2"
    assert c.user.username == "shohrux.qodirov" and c.user.first_name == "Шоҳрух"


def test_no_account_when_disabled_or_without_name(rector, survey, faculty):
    survey.create_accounts = False
    survey.save()
    assert answer(survey, faculty).user is None
    feedback = services.create_survey(rector, "feedback")  # ism so'ralmaydi
    services.publish(feedback)
    assert services.submit(feedback, answers={}).user is None
    assert not IssuedAccount.objects.exists()


def test_student_limit_stops_new_accounts(survey, faculty, monkeypatch):
    monkeypatch.setattr(accounts, "_limit_reached", lambda: True)
    response = answer(survey, faculty)
    assert response.user is None and response.full_name  # javob baribir saqlanadi


def test_provision_existing_anonymous_responses(rector, survey, faculty, make_user):
    survey.create_accounts = False
    survey.save()
    answer(survey, faculty)
    answer(survey, faculty, name="Toshmatov Jasur", phone="+998905555555")
    dean = make_user(role=User.Role.DEAN, faculty=faculty)
    url = reverse("web:credentials-provision", args=[survey.pk])
    web(dean).post(url)
    assert not IssuedAccount.objects.exists()  # faqat rektorat yoki admin
    page = web(rector).post(url, follow=True).content.decode()
    assert IssuedAccount.objects.count() == 2 and "2 ta yangi akkaunt ochildi" in page
    assert not survey.responses.filter(user__isnull=True).exists()


def test_thanks_page_tells_student_about_account(survey, faculty):
    client = web()
    url = reverse("web:survey-fill", args=[survey.token])
    client.get(url)
    track = survey.questions.get(kind=Question.Kind.TRACK)
    data = {
        f"q{track.pk}": Track.IT,
        f"q{survey.questions.get(title='Eng yuqori natijangiz qaysi darajada?').pk}": "Viloyat",
        f"q{survey.questions.get(kind=Question.Kind.SCALE).pk}": "4",
        f"q{survey.questions.get(title='Mentor (ustoz) bilan ishlashni xohlaysizmi?').pk}": "Ha, albatta",
        "who-full_name": "Yusupova Madina",
        "who-faculty": faculty.pk,
        "who-course": "1",
        "who-group": "K-23-01",
    }
    page = client.post(url, data, follow=True).content.decode()
    assert "akkaunt ochildi" in page
    assert "akkaunt ochildi" not in client.get(reverse("web:survey-thanks", args=[survey.token])).content.decode()


# ---------------------------------------------------------------- birinchi kirish


def test_first_login_clears_initial_password_and_asks_for_new_one(survey, faculty):
    student = answer(survey, faculty).user
    password = student.issued_account.initial_password
    client = Client()
    response = client.post(reverse("web:login"), {"username": student.username, "password": password})
    assert response.status_code == 302 and response.url == reverse("web:password-change")
    issued = IssuedAccount.objects.get(user=student)
    assert issued.initial_password == "" and issued.first_login_at is not None and issued.must_change_password

    assert "Xavfsizlik uchun parolingizni" in client.get(reverse("web:notifications")).content.decode()
    assert student.username in client.get(reverse("web:password-change")).content.decode()
    client.post(
        reverse("web:password-change"), {"new_password1": "Yangi-Parol-2026", "new_password2": "Yangi-Parol-2026"}
    )
    issued.refresh_from_db()
    assert not issued.must_change_password
    assert authenticate(username=student.username, password="Yangi-Parol-2026") == student
    assert "Xavfsizlik uchun parolingizni" not in client.get(reverse("web:notifications")).content.decode()


# ---------------------------------------------------------------- login va parollar sahifasi


def test_credentials_page_access_and_dean_scope(rector, survey, faculty, make_user, student, teacher):
    mine = answer(survey, faculty)
    other_faculty = Faculty.objects.create(name="Energetika", short_name="EN")
    theirs = answer(survey, other_faculty, name="Boshqa Talaba", phone="+998907777777")
    url = reverse("web:credentials")
    for user in (student, teacher):
        assert web(user).get(url).status_code == 403
    page = web(rector).get(url).content.decode()
    assert mine.user.issued_account.initial_password in page and theirs.user.username in page
    dean = make_user(role=User.Role.DEAN, faculty=faculty)
    page = web(dean).get(url).content.decode()
    assert mine.user.username in page and theirs.user.username not in page
    waiting = web(rector).get(url + "?status=active").content.decode()
    assert mine.user.username not in waiting


def test_word_export_table_and_cards(rector, survey, faculty):
    student = answer(survey, faculty).user
    password = student.issued_account.initial_password
    for layout in ("", "cards"):
        response = web(rector).get(reverse("web:credentials-word") + (f"?layout={layout}" if layout else ""))
        assert response["Content-Type"].startswith("application/vnd.openxmlformats-officedocument.wordprocessingml")
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        for name in archive.namelist():
            if name.endswith(".xml") or name.endswith(".rels"):
                minidom.parseString(archive.read(name))  # har bir qism to'g'ri XML
        document = archive.read("word/document.xml").decode()
        assert student.username in document and password in document and "Karimova Aziza" in document
    assert AuditLog.objects.filter(action=AuditLog.Action.EXPORT, actor=rector).count() == 2


def test_reset_password(rector, survey, faculty):
    student = answer(survey, faculty).user
    issued = student.issued_account
    old = issued.initial_password
    IssuedAccount.objects.filter(pk=issued.pk).update(initial_password="", must_change_password=False)
    web(rector).post(reverse("web:credentials-reset", args=[issued.pk]))
    issued.refresh_from_db()
    assert issued.initial_password and issued.initial_password != old and issued.must_change_password
    assert authenticate(username=student.username, password=issued.initial_password) == student
