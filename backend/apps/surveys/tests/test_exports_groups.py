import io
import zipfile
from xml.dom import minidom

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.surveys import analytics, clubs, services, xlsx
from apps.surveys.models import Question
from apps.talent.tracks import Track
from apps.web.forms import SurveyIdentityForm

Kind = Question.Kind


@pytest.fixture
def rector(make_user):
    return make_user(role=User.Role.RECTOR, username="rektor")


@pytest.fixture
def survey(rector, faculty):
    survey = services.create_survey(rector, "census")
    services.publish(survey)
    track = survey.questions.get(kind=Kind.TRACK)
    for i, (name, group, value) in enumerate(
        [
            ("Aliyev Ali", "K-21-05", Track.IT),
            ("Valiyev Vali", "K-21-05", Track.IT),
            ("Karimova Aziza", "M-22-01", Track.RESEARCH),
        ]
    ):
        services.submit(
            survey,
            answers={str(track.pk): value},
            identity={"full_name": name, "faculty": faculty, "course": 2, "group": group, "phone": f"+99890111223{i}"},
        )
    return survey


def web(user=None):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


@pytest.mark.parametrize(
    "raw, expected",
    [("k2105", "K-21-05"), ("К 21 05", "K-21-05"), ("k-21/05", "K-21-05"), ("IBKT 23-01", "IBKT-23-01"),
     ("K-21-05", "K-21-05"), ("", "")],
)  # fmt: skip
def test_normalize_group(raw, expected):
    assert services.normalize_group(raw) == expected


@pytest.mark.parametrize("raw", ["21-05", "K-2-05", "ABCDEF-21-05", "K-21-055", "", "guruh"])
def test_identity_form_rejects_bad_group(faculty, raw):
    form = SurveyIdentityForm(
        {"who-full_name": "Aliyev Ali", "who-faculty": faculty.pk, "who-course": "2", "who-group": raw}
    )
    assert not form.is_valid() and "group" in form.errors


def test_identity_form_accepts_and_normalizes_group(faculty):
    form = SurveyIdentityForm({"who-full_name": "Aliyev Ali", "who-faculty": faculty.pk, "who-course": "2",
                               "who-group": "k 21 05"})  # fmt: skip
    assert form.is_valid() and form.cleaned_data["group"] == "K-21-05"


def test_group_filter_and_crosstab_dimension(rector, survey):
    url = reverse("web:survey-results", args=[survey.pk])
    page = web(rector).get(url, {"tab": "responses", "group": "M-22-01"}).content.decode()
    assert "Karimova Aziza" in page and "Aliyev Ali" not in page and 'value="K-21-05"' in page
    track = survey.questions.get(kind=Kind.TRACK)
    table = analytics.crosstab(survey, survey.responses.all(), track, "group")
    assert {r["label"]: r["total"] for r in table["rows"]} == {"K-21-05": 2, "M-22-01": 1}


def test_results_xlsx_is_valid_workbook(rector, survey):
    clubs.form_clubs(survey, survey.questions.get(kind=Kind.TRACK), survey.responses.all(), by=rector, min_members=2)
    track = survey.questions.get(kind=Kind.TRACK)
    response = web(rector).get(reverse("web:survey-export-xlsx", args=[survey.pk]))
    assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    for name in archive.namelist():
        minidom.parseString(archive.read(name))  # har bir qism to'g'ri XML
    workbook = archive.read("xl/workbook.xml").decode()
    for sheet in ("Umumiy natija", "Javoblar", "Kesimlar", "Klublar"):
        assert f'name="{sheet}"' in workbook
    answers = archive.read("xl/worksheets/sheet2.xml").decode()
    assert (
        "Aliyev Ali" in answers and "K-21-05" in answers and "IT va dasturlash" in answers and "<autoFilter" in answers
    )
    assert "IT va dasturlash klubi" in archive.read("xl/worksheets/sheet4.xml").decode()

    filtered = web(rector).get(
        reverse("web:survey-export-xlsx", args=[survey.pk]), {"answer": f"{track.pk}:{Track.RESEARCH}"}
    )
    sheet = zipfile.ZipFile(io.BytesIO(filtered.content)).read("xl/worksheets/sheet2.xml").decode()
    assert "Karimova Aziza" in sheet and "Aliyev Ali" not in sheet


def test_xlsx_helpers():
    assert [xlsx.col_name(i) for i in (0, 25, 26, 27, 701)] == ["A", "Z", "AA", "AB", "ZZ"]
    assert xlsx.absolute("A4:K20") == "$A$4:$K$20"
    assert xlsx.bar(0.5, 10) == "█████░░░░░" and xlsx.bar(0) == ""
    assert xlsx.Sheet("a/b:c*?[d]" * 5).name.count("/") == 0
