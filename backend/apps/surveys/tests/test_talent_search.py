import io
import zipfile

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import Faculty, User
from apps.profiles.models import Skill, UserSkill
from apps.surveys import presets, services, skills


@pytest.fixture
def rector(make_user):
    return make_user(role=User.Role.RECTOR, username="rektor")


def web(user=None):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


@pytest.fixture
def talent_survey(rector):
    survey = services.create_survey(rector, "andti_talent")
    services.publish(survey)
    return survey


def skills_q(survey):
    return survey.questions.get(title="Sizning qanday qobiliyatlaringiz bor?")


def submit(survey, name, faculty, picked, course=2, group="AT-24-01"):
    return services.submit(
        survey,
        answers={str(skills_q(survey).pk): picked},
        identity={"full_name": name, "faculty": faculty, "course": course, "group": group, "phone": ""},
    )


def test_skill_names_and_categories():
    assert skills.skill_name("🎬 Video montaj") == "Video montaj"
    assert skills.skill_name("❤️ Volontyorlik") == "Volontyorlik"
    assert skills.category_of("Dasturlash") == Skill.Category.PROGRAMMING
    assert skills.category_of("Chet tillari") == Skill.Category.LANGUAGES


def test_answers_become_profile_skills_and_are_searchable(rector, talent_survey):
    at = Faculty.objects.get(short_name="AT")
    ib = Faculty.objects.get(short_name="IB")
    a = submit(talent_survey, "Aliyev Ali", at, ["🎬 Video montaj", "🎤 Notiqlik"], course=3)
    submit(talent_survey, "Valiyeva Lola", at, ["🎤 Notiqlik"], course=1, group="AT-25-02")
    submit(talent_survey, "Karimov Bek", ib, ["🎬 Video montaj", "💻 Dasturlash"], course=3, group="IB-23-01")
    names = set(UserSkill.objects.filter(user=a.user).values_list("skill__name", flat=True))
    assert names == {"Video montaj", "Notiqlik"}
    existing = Skill.objects.get(name="Sun'iy intellekt")  # seed'dagi ko'nikma qayta yaratilmaydi
    submit(talent_survey, "Toshev Ilm", ib, ["🤖 Sun'iy intellekt"])
    assert Skill.objects.filter(name__iexact="Sun'iy intellekt").count() == 1 and existing.user_skills.count() == 1

    video = Skill.objects.get(name="Video montaj")
    notiq = Skill.objects.get(name="Notiqlik")
    url = reverse("web:talent-search")
    page = web(rector).get(url, {"skill": video.pk, "course": 3}).content.decode()
    assert "2 nafar talaba topildi" in page and "Aliyev Ali" in page and "Karimov Bek" in page
    page = web(rector).get(url, {"skill": [video.pk, notiq.pk]}).content.decode()  # ikkalasi ham bor
    assert "1 nafar talaba topildi" in page and "Aliyev Ali" in page
    page = web(rector).get(url, {"skill": [video.pk, notiq.pk], "mode": "any"}).content.decode()
    assert "3 nafar talaba topildi" in page
    page = web(rector).get(url, {"skill": notiq.pk, "group": "at-25-02"}).content.decode()
    assert "Valiyeva Lola" in page and "Aliyev Ali" not in page
    assert "Eng ko&#x27;p uchraydigan qobiliyatlar" in page or "Eng ko'p uchraydigan qobiliyatlar" in page

    dean = User.objects.create_user(username="dekan", password="x", role=User.Role.DEAN, faculty=ib)
    page = web(dean).get(url, {"skill": video.pk}).content.decode()
    assert "Karimov Bek" in page and "Aliyev Ali" not in page

    export = web(rector).get(reverse("web:talent-search-export"), {"skill": video.pk})
    sheet = zipfile.ZipFile(io.BytesIO(export.content)).read("xl/worksheets/sheet1.xml").decode()
    assert "Aliyev Ali" in sheet and "Video montaj" in sheet

    student = a.user
    assert web(student).get(url).status_code in (302, 403)


def test_turning_on_profile_flag_backfills_old_answers(rector, django_capture_on_commit_callbacks):
    survey = services.create_survey(rector, "andti_talent")
    q = skills_q(survey)
    q.to_profile = False
    q.save()
    services.publish(survey)
    at = Faculty.objects.get(short_name="AT")
    submit(survey, "Aliyev Ali", at, ["🎸 Musiqa asboblari chalish (gitara yoki boshqalar)"])
    assert not UserSkill.objects.exists()
    items = services.schema(survey)
    next(i for i in items if i["id"] == q.pk)["to_profile"] = True
    with django_capture_on_commit_callbacks(execute=True):
        services.save_schema(survey, items)
    assert UserSkill.objects.get().skill.name == "Musiqa asboblari chalish (gitara yoki boshqalar)"

    UserSkill.objects.all().delete()
    response = web(rector).post(reverse("web:talent-search-sync"), follow=True)
    assert "1 ta yangi qobiliyat" in response.content.decode() and UserSkill.objects.count() == 1


def test_preset_marks_skills_question():
    item = next(q for q in presets.ANDTI_TALENT["questions"] if q["title"] == "Sizning qanday qobiliyatlaringiz bor?")
    assert item["to_profile"] is True
