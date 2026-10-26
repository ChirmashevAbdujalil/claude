import io
import re
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.accounts import tutors as tutor_services
from apps.accounts.models import Faculty, Tutor, User
from apps.surveys import analytics, services
from apps.surveys.models import IssuedAccount, Question, Response
from apps.talent.tracks import Track
from apps.web.forms import SurveyIdentityForm

Kind = Question.Kind


@pytest.fixture
def rector(make_user):
    return make_user(role=User.Role.RECTOR, username="rektor")


@pytest.fixture
def andti():
    """Seed asosiy OTM fakultetlariga ANDTI tyutorlarini biriktirgan bo'ladi."""
    return {f.short_name: f for f in Faculty.objects.filter(short_name__in=tutor_services.ANDTI_TUTORS)}


def web(user=None):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def docx_with_rows(rows) -> bytes:
    def cell(text):
        return f"<w:tc><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>"

    body = "".join("<w:tr>" + "".join(cell(c) for c in row) + "</w:tr>" for row in rows)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
        f'wordprocessingml/2006/main"><w:body><w:tbl>{body}</w:tbl></w:body></w:document>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


def test_andti_tutors_are_attached_to_their_faculties(andti):
    assert Tutor.objects.count() == 25
    counts = {short: Tutor.objects.filter(faculty=f).count() for short, f in andti.items()}
    assert counts == {"AT": 4, "MKM": 4, "IBKT": 3, "QMEE": 6, "IB": 8}
    assert Tutor.objects.filter(faculty=andti["IB"], full_name="Axmedova Ra'noxon").exists()
    assert tutor_services.ensure_andti_tutors() == 0  # takror qo'shilmaydi


@pytest.mark.parametrize(
    "text, short",
    [("Avtomobilsozlik va transport", "AT"), ("Qurilish muxandisligi va elektr energiya", "QMEE"),
     ("Intellektual boshqaruv va kompyuter tizimlari", "IBKT"), ("Iqtisodiyot va boshqaruv", "IB"),
     ("Mexanika va kimyo muhandisligi", "MKM"), ("IBKT", "IBKT")],
)  # fmt: skip
def test_faculty_matching(andti, text, short):
    assert tutor_services.match_faculty(text, andti.values()).short_name == short


def test_docx_import(andti):
    content = docx_with_rows([
        ["Fakultet nomi", "Lavozimi", "F.I.Sh"],
        ["Avtomobilsozlik va transport", "Tyutor", "Yangi  Tyutorbek"],
        ["Avtomobilsozlik va transport", "Dekan", "Dekan Rahbarov"],
        ["Noma'lum fakultet", "Tyutor", "Kimdir"],
        ["Avtomobilsozlik va transport", "Tyutor", "Yaxshiboyev Davronbek"],
    ])  # fmt: skip
    result = tutor_services.import_rows(tutor_services.read_docx_rows(io.BytesIO(content)))
    assert result == {"added": 1, "existing": 1, "unknown": ["Noma'lum fakultet"]}
    assert Tutor.objects.filter(faculty=andti["AT"], full_name="Yangi Tyutorbek").exists()
    assert not Tutor.objects.filter(full_name="Dekan Rahbarov").exists()
    with pytest.raises(tutor_services.TutorImportError):
        tutor_services.import_rows([["Ism"], ["x"]])


def test_tutors_page_add_delete_import(rector, andti, student):
    url = reverse("web:tutors")
    assert web(student).get(url).status_code == 403
    page = web(rector).get(url).content.decode()
    assert "Yaxshiboyev Davronbek" in page and "25 ta tyutor" in page
    web(rector).post(url, {"faculty": andti["MKM"].pk, "full_name": "  Yangi   Ustoz ", "phone": ""})
    tutor = Tutor.objects.get(full_name="Yangi Ustoz")
    assert tutor.faculty == andti["MKM"]
    web(rector).post(reverse("web:tutor-delete", args=[tutor.pk]))
    assert not Tutor.objects.filter(pk=tutor.pk).exists()
    upload = SimpleUploadedFile("tyutorlar.docx", docx_with_rows([["Fakultet", "F.I.Sh."], ["IB", "Import Qilingan"]]))
    web(rector).post(reverse("web:tutor-import"), {"file": upload})
    assert Tutor.objects.filter(full_name="Import Qilingan", faculty=andti["IB"]).exists()


def identity(faculty, tutor=None, **extra):
    data = {"who-full_name": "Aliyev Ali", "who-faculty": faculty.pk, "who-course": "2", "who-group": "K-21-05"}
    if tutor is not None:
        data["who-tutor"] = tutor.pk
    data.update(extra)
    return SurveyIdentityForm(data)


def test_identity_form_requires_tutor_of_chosen_faculty(andti, faculty):
    at, ib = andti["AT"], andti["IB"]
    at_tutor = Tutor.objects.filter(faculty=at).first()
    assert not identity(at).is_valid()  # tyutori bor fakultet: tanlash majburiy
    wrong = identity(ib, at_tutor)
    assert not wrong.is_valid() and "tutor" in wrong.errors
    ok = identity(at, at_tutor)
    assert ok.is_valid() and ok.cleaned_data["tutor"] == at_tutor
    assert identity(faculty).is_valid()  # tyutori yo'q fakultet: majburiy emas
    rendered = str(identity(at)["tutor"])
    assert f'data-faculty="{at.pk}"' in rendered and "(AT)" in rendered


def test_tutor_statistics_on_results(rector, andti):
    survey = services.create_survey(rector, "census")
    services.publish(survey)
    track = survey.questions.get(kind=Kind.TRACK)
    at_tutors = list(Tutor.objects.filter(faculty=andti["AT"]).order_by("full_name"))
    for i, tutor in enumerate([at_tutors[0], at_tutors[0], at_tutors[1], None]):
        services.submit(
            survey,
            answers={str(track.pk): Track.IT},
            identity={"full_name": f"Talaba {i}", "faculty": andti["AT"], "tutor": tutor, "phone": f"+99890999000{i}"},
        )
    assert Response.objects.filter(tutor=at_tutors[0]).count() == 2
    data = analytics.tutor_registration(survey.responses.all(), list(Tutor.objects.select_related("faculty")))
    at_group = next(g for g in data["faculties"] if g["faculty"] == andti["AT"])
    assert at_group["total"] == 3 and at_group["silent"] == 2 and at_group["tutors"][0]["medal"] == "🥇"
    assert data["leader"]["name"] == at_tutors[0].full_name and data["without"] == 1 and data["tutors_count"] == 25

    url = reverse("web:survey-results", args=[survey.pk])
    page = web(rector).get(url).content.decode()
    assert "Tyutorlar kesimida" in page and "Eng faol tyutor" in page and "2 tyutordan javob yo" in page
    filtered = web(rector).get(url, {"tab": "responses", "tutor": at_tutors[1].pk}).content.decode()
    assert "Talaba 2" in filtered and "Talaba 0" not in filtered
    table = analytics.crosstab(survey, survey.responses.all(), track, "tutor")
    assert {r["label"]: r["total"] for r in table["rows"]}[at_tutors[0].full_name] == 2

    content = web(rector).get(reverse("web:survey-export-xlsx", args=[survey.pk])).content
    archive = zipfile.ZipFile(io.BytesIO(content))
    names = re.findall(r'<sheet name="([^"]+)"', archive.read("xl/workbook.xml").decode())
    sheet = archive.read(f"xl/worksheets/sheet{names.index('Tyutorlar') + 1}.xml").decode()
    assert at_tutors[0].full_name in sheet and "Tyutor tanlamagan talabalar: 1" in sheet


def test_tutor_personal_link_prefills_identity(rector, andti):
    survey = services.create_survey(rector, "census")
    services.publish(survey)
    tutor = Tutor.objects.filter(faculty=andti["IB"]).order_by("full_name").first()
    fill = reverse("web:survey-fill", args=[survey.token])
    page = web().get(fill, {"t": tutor.pk}).content.decode()
    assert "Havolani tyutoringiz" in page and f'<option value="{tutor.pk}" selected' in page
    assert "Havolani tyutoringiz" not in web().get(fill, {"t": "999999"}).content.decode()

    links = web(rector).get(reverse("web:survey-tutor-links", args=[survey.pk])).content.decode()
    assert f"{fill}?t={tutor.pk}" in links and "Telegram xabari" in links and links.count("tl-card") >= 25
    poster = web(rector).get(reverse("web:survey-poster", args=[survey.pk]), {"t": tutor.pk}).content.decode()
    assert tutor.full_name in poster and f"?t={tutor.pk}" in poster


def test_credentials_by_tutor(rector, andti):
    survey = services.create_survey(rector, "census")
    services.publish(survey)
    first, second = Tutor.objects.filter(faculty=andti["AT"]).order_by("full_name")[:2]
    for i, tutor in enumerate([first, first, second]):
        services.submit(
            survey,
            answers={},
            identity={"full_name": f"Tursunov Talaba{i}", "faculty": andti["AT"], "tutor": tutor, "course": 2,
                      "group": f"AT-23-0{i}", "phone": f"+99890777000{i}"},
        )  # fmt: skip
    assert IssuedAccount.objects.filter(tutor=first).count() == 2

    # Talaba keyingi so'rovnomada boshqa tyutorni ko'rsatsa, akkauntda yangisi turadi
    again = services.create_survey(rector, "census")
    services.publish(again)
    services.submit(
        again,
        answers={},
        identity={"full_name": "Tursunov Talaba0", "faculty": andti["AT"], "tutor": second, "phone": "+998907770000"},
    )
    assert IssuedAccount.objects.filter(tutor=second).count() == 2

    url = reverse("web:credentials")
    page = web(rector).get(url, {"tutor": first.pk}).content.decode()
    assert "Talaba1" in page and "Talaba2" not in page and "Word: tyutorlar bo" in page
    word = web(rector).get(reverse("web:credentials-word"), {"layout": "tutors"})
    document = zipfile.ZipFile(io.BytesIO(word.content)).read("word/document.xml").decode()
    assert f"Tyutor: {first.full_name}" in document and f"Tyutor: {second.full_name}" in document
    assert document.count('w:type="page"') == 1 and "tyutorlar" in word["Content-Disposition"]


def test_tutor_cabinet(rector, andti, make_user):
    survey = services.create_survey(rector, "census")
    services.publish(survey)
    first, second = Tutor.objects.filter(faculty=andti["AT"]).order_by("full_name")[:2]
    for i, tutor in enumerate([first, first, second]):
        services.submit(
            survey,
            answers={},
            identity={"full_name": f"Tursunov Talaba{i}", "faculty": andti["AT"], "tutor": tutor, "course": 2,
                      "group": f"AT-23-0{i % 2}", "phone": f"+99890777100{i}"},
        )  # fmt: skip

    admin = web(rector)
    admin.post(reverse("web:tutor-account", args=[first.pk]))
    first.refresh_from_db()
    account = IssuedAccount.objects.get(user=first.user)
    assert first.user.role == User.Role.TEACHER and account.initial_password and account.group == "Tyutor"
    assert first.user.username in admin.get(reverse("web:tutors")).content.decode()  # xabarda login va parol
    credentials = admin.get(reverse("web:credentials")).content.decode()
    assert first.user.username not in credentials  # tyutor talabalar login ro'yxatiga aralashmaydi
    admin.post(reverse("web:tutor-accounts-all"))
    assert Tutor.objects.filter(user__isnull=True).count() == 0
    word = admin.get(reverse("web:tutor-accounts-word"))
    document = zipfile.ZipFile(io.BytesIO(word.content)).read("word/document.xml").decode()
    assert first.user.username in document and account.initial_password in document
    assert "Tyutorlar kabineti" in document and "/tyutor/" in document and "talabaga o" not in document

    me = web(first.user)
    page = me.get(reverse("web:tutor-cabinet")).content.decode()
    assert "Tyutor kabineti" in page and "Talaba0" in page and "Talaba1" in page and "Talaba2" not in page
    assert f"?t={first.pk}" in page and "Telegram xabari" in page
    assert "<b>2</b> ta talabam" in page
    filtered = me.get(reverse("web:tutor-cabinet"), {"group": "AT-23-01"}).content.decode()
    assert "Talaba1" in filtered and "Talaba0" not in filtered

    own = IssuedAccount.objects.get(user__last_name="Tursunov", user__first_name="Talaba0")
    other = IssuedAccount.objects.get(user__first_name="Talaba2")
    old = own.initial_password
    assert me.post(reverse("web:tutor-cabinet-reset", args=[own.pk])).status_code == 302
    own.refresh_from_db()
    assert own.initial_password != old
    assert me.post(reverse("web:tutor-cabinet-reset", args=[other.pk])).status_code == 404
    document = (
        zipfile.ZipFile(io.BytesIO(me.get(reverse("web:tutor-cabinet-word")).content))
        .read("word/document.xml")
        .decode()
    )
    assert "Talaba0" in document and "Talaba2" not in document

    poster = reverse("web:survey-poster", args=[survey.pk])
    assert me.get(poster, {"t": first.pk}).status_code == 200
    assert me.get(poster, {"t": second.pk}).status_code == 403

    teacher = make_user(role=User.Role.TEACHER, username="oddiy-ustoz")
    assert web(teacher).get(reverse("web:tutor-cabinet")).status_code == 403  # tushunarli izoh bilan
    chooser = admin.get(reverse("web:tutor-cabinet"))  # rahbar: barcha tyutorlar ro'yxati
    assert chooser.status_code == 200 and "Tyutor kabinetlari" in chooser.content.decode()
    assert reverse("web:tutor-cabinet-view", args=[second.pk]) in chooser.content.decode()
    assert admin.get(reverse("web:tutor-cabinet-view", args=[first.pk])).status_code == 200
    dean = make_user(role=User.Role.DEAN, faculty=andti["IB"], username="ib-dekan")
    assert web(dean).get(reverse("web:tutor-cabinet-view", args=[first.pk])).status_code == 403
