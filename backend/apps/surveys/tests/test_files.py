import io
import os
import zipfile

import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.accounts.models import Faculty, User
from apps.surveys import docx, services
from apps.surveys import files as file_rules
from apps.surveys.models import Question, ResponseFile

Kind = Question.Kind
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.fixture(autouse=True)
def fresh_cache():
    cache.clear()  # bir manzildan yuklash hisobi testlar orasida o'tib ketmasin


@pytest.fixture
def rector(make_user):
    return make_user(role=User.Role.RECTOR, username="rektor")


def web(user=None):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def make_survey(rector, *, identity=False, **file_options):
    survey = services.create_survey(rector, "blank")
    survey.collect_identity = identity
    survey.create_accounts = False
    survey.save()
    options = {"file_types": ["pdf", "image"], "max_files": 2, "max_file_mb": 1, **file_options}
    services.save_schema(
        survey,
        [
            {"kind": "short", "title": "Ismingiz", "required": False},
            {"kind": "file", "title": "Sertifikat", "required": True, **options},
        ],
    )
    services.publish(survey)
    return survey


def file_q(survey):
    return survey.questions.get(kind=Kind.FILE)


def upload(name, content, content_type="application/octet-stream"):
    return SimpleUploadedFile(name, content, content_type=content_type)


def post(survey, files, client=None, **data):
    client = client or Client()
    url = reverse("web:survey-fill", args=[survey.token])
    client.get(url)  # brauzer kaliti (cookie) uchun
    payload = {f"q{file_q(survey).pk}": files, **data}
    return client.post(url, payload)


def test_schema_keeps_file_settings_within_limits(rector):
    survey = services.create_survey(rector, "blank")
    services.save_schema(
        survey,
        [{"kind": "file", "title": "Hujjat", "file_types": ["pdf", "exe", "word"], "max_files": 99, "max_file_mb": 0}],
    )
    q = file_q(survey)
    assert q.file_types == ["pdf", "word"] and q.max_files == file_rules.MAX_FILES and q.max_file_mb == 1
    copy = services.duplicate(survey, rector)
    assert file_q(copy).file_types == ["pdf", "word"]


def test_upload_is_stored_privately_and_linked_to_answer(rector):
    survey = make_survey(rector)
    response = post(survey, [upload("diplom.pdf", PDF), upload("rasm.PNG", PNG)])
    assert response.status_code == 302 and response.url.endswith("/rahmat/")
    answer = survey.responses.get()
    stored = list(answer.files.order_by("id"))
    assert answer.answers[str(file_q(survey).pk)] == ["diplom.pdf", "rasm.PNG"]
    assert [(f.category, f.content_type) for f in stored] == [("pdf", "application/pdf"), ("image", "image/png")]
    path = stored[0].file.path
    assert path.startswith(os.path.abspath(settings.PRIVATE_MEDIA_ROOT)) and not path.startswith(
        os.path.abspath(settings.MEDIA_ROOT)
    )
    with open(path, "rb") as handle:
        assert handle.read() == PDF


@pytest.mark.parametrize(
    "files, message",
    [
        ([upload("diplom.pdf", b"<html><script>alert(1)</script>")], "turi mos emas"),
        ([upload("hujjat.docx", docx.render([], layout="table", institution="X", site="x", subtitle="", signature=""))],
         "faqat PDF, Rasm"),
        ([upload("katta.pdf", PDF + b"0" * (1024 * 1024))], "1 MB dan oshmasin"),
        ([upload("a.pdf", PDF), upload("b.pdf", PDF), upload("c.pdf", PDF)], "Ko'pi bilan 2 ta"),
        ([upload("rasm.pdf", JPG)], "turi mos emas"),
        ([], "majburiy"),
    ],
)  # fmt: skip
def test_bad_uploads_are_rejected(rector, files, message):
    survey = make_survey(rector)
    page = post(survey, files).content.decode()
    assert message in page.replace("&#x27;", "'") and not survey.responses.exists()
    assert not ResponseFile.objects.exists()


def test_sniff_recognizes_office_files():
    word = io.BytesIO(docx.render([], layout="table", institution="X", site="x", subtitle="", signature=""))
    assert file_rules.sniff(word, "docx") == "word"
    assert file_rules.sniff(io.BytesIO(PDF), "pdf") == "pdf"
    assert file_rules.sniff(io.BytesIO(PNG), "jpg") == "image"  # kengaytma almashgan rasm ham rasm
    assert file_rules.sniff(io.BytesIO(b"PK\x03\x04broken"), "docx") is None


def test_other_errors_ask_to_reselect_file(rector):
    survey = make_survey(rector)
    survey.questions.filter(kind=Kind.SHORT).update(required=True)
    page = post(survey, [upload("diplom.pdf", PDF)]).content.decode()
    assert "faylni qayta tanlang" in page and not survey.responses.exists()


def test_files_are_visible_only_to_management(rector, make_user, student):
    survey = make_survey(rector, identity=True)
    faculty = Faculty.objects.get(short_name="KI")
    post(
        survey,
        [upload("diplom.pdf", PDF), upload("rasm.jpg", JPG)],
        **{"who-full_name": "Aliyev Vali", "who-faculty": faculty.pk, "who-course": 2, "who-group": "KI-23-01"},
    )
    pdf, jpg = ResponseFile.objects.order_by("id")
    url = reverse("web:survey-file", args=[survey.pk, pdf.pk])

    shown = web(rector).get(url)
    assert shown.status_code == 200 and shown["Content-Type"] == "application/pdf"
    assert shown["X-Content-Type-Options"] == "nosniff" and "sandbox" in shown["Content-Security-Policy"]
    assert "inline" in shown["Content-Disposition"] and b"".join(shown.streaming_content) == PDF
    assert "attachment" in web(rector).get(url, {"download": "1"})["Content-Disposition"]

    assert web().get(url).status_code == 302  # kirmagan
    assert web(student).get(url).status_code in (302, 403)
    other = Faculty.objects.exclude(pk=faculty.pk).first()
    dean = make_user(role=User.Role.DEAN, faculty=other, username="dekan")
    assert web(dean).get(url).status_code == 404  # boshqa fakultet javobi
    own_dean = make_user(role=User.Role.DEAN, faculty=faculty, username="dekan2")
    assert web(own_dean).get(url).status_code == 200

    page = web(rector).get(reverse("web:survey-response", args=[survey.pk, pdf.response_id])).content.decode()
    assert "diplom.pdf" in page and "Yuklab olish" in page
    results = web(rector).get(reverse("web:survey-results", args=[survey.pk])).content.decode()
    assert "Barcha fayllar (ZIP)" in results and "talaba yukladi" in results

    archive = web(rector).get(reverse("web:survey-files-zip", args=[survey.pk]), {"question": file_q(survey).pk})
    names = zipfile.ZipFile(io.BytesIO(b"".join(archive.streaming_content))).namelist()
    assert names == ["KI/Aliyev Vali KI-23-01/diplom.pdf", "KI/Aliyev Vali KI-23-01/rasm.jpg"]
    assert web(student).get(reverse("web:survey-files-zip", args=[survey.pk])).status_code in (302, 403)

    content = web(rector).get(reverse("web:survey-export-xlsx", args=[survey.pk])).content
    sheets = " ".join(
        zipfile.ZipFile(io.BytesIO(content)).read(n).decode()
        for n in zipfile.ZipFile(io.BytesIO(content)).namelist()
        if n.startswith("xl/worksheets/")
    )
    assert "2 ta fayl: diplom.pdf; rasm.jpg" in sheets


def test_deleting_response_removes_files_from_disk(rector, django_capture_on_commit_callbacks):
    survey = make_survey(rector)
    post(survey, [upload("diplom.pdf", PDF)])
    stored = ResponseFile.objects.get()
    path = stored.file.path
    assert os.path.exists(path)
    with django_capture_on_commit_callbacks(execute=True):
        web(rector).post(reverse("web:survey-response-delete", args=[survey.pk, stored.response_id]))
    assert not ResponseFile.objects.exists() and not os.path.exists(path)


def test_oversized_request_is_stopped_before_reading(rector):
    survey = make_survey(rector)
    url = reverse("web:survey-fill", args=[survey.token])
    response = Client().post(url, {"q": "x"}, CONTENT_LENGTH=str(file_rules.MAX_REQUEST_BYTES + 1))
    assert response.status_code == 413 and "juda katta" in response.content.decode()


def test_ip_limit(rector, monkeypatch):
    monkeypatch.setattr(file_rules, "IP_HOURLY_LIMIT", 2)
    survey = make_survey(rector)
    survey.one_response = False
    survey.save()
    assert post(survey, [upload("a.pdf", PDF), upload("b.pdf", PDF)]).status_code == 302
    page = post(survey, [upload("c.pdf", PDF)]).content.decode()
    assert "Juda ko'p fayl" in page.replace("&#x27;", "'") and survey.responses.count() == 1


def test_fill_page_and_builder_show_file_question(rector):
    survey = make_survey(rector)
    page = web().get(reverse("web:survey-fill", args=[survey.token])).content.decode()
    assert 'enctype="multipart/form-data"' in page and "data-file-input" in page and "multiple" in page
    assert 'data-exts="pdf,jpg,jpeg,png,webp,heic,heif"' in page and "har biri 1 MB gacha" in page
    builder = web(rector).get(reverse("web:survey-builder", args=[survey.pk])).content.decode()
    assert "Fayl yuklash" in builder and '"max_files": 2' in builder
