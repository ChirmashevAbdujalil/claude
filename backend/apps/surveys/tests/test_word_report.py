import io
import zipfile
from xml.dom import minidom

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import Faculty, Tutor, User
from apps.surveys import clubs, services
from apps.surveys.models import Question
from apps.talent.tracks import Track

Kind = Question.Kind


@pytest.fixture
def rector(make_user):
    return make_user(role=User.Role.RECTOR, username="rektor", first_name="Rahbar", last_name="Rektorov")


def test_word_report_contains_all_sections(rector):
    survey = services.create_survey(rector, "census")
    services.publish(survey)
    at = Faculty.objects.get(short_name="AT")
    tutor = Tutor.objects.filter(faculty=at).first()
    track = survey.questions.get(kind=Kind.TRACK)
    story = survey.questions.get(title="Eng katta yutug'ingiz yoki loyihangiz haqida yozing")
    for i, value in enumerate([Track.IT, Track.IT, Track.IT, Track.RESEARCH]):
        services.submit(
            survey,
            answers={str(track.pk): value, str(story.pk): f"Hakatonda {i + 1}-o'rin oldim"},
            identity={"full_name": f"Talabov Talaba{i}", "faculty": at, "tutor": tutor, "course": 2,
                      "group": "AT-24-01", "phone": f"+99890555000{i}"},
        )  # fmt: skip
    clubs.form_clubs(survey, track, survey.responses.all(), by=rector, min_members=3)

    client = Client()
    client.force_login(rector)
    response = client.get(reverse("web:survey-export-docx", args=[survey.pk]))
    assert response.status_code == 200 and response["Content-Disposition"].endswith('.docx"')
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    xml = archive.read("word/document.xml").decode()
    minidom.parseString(xml)  # to'g'ri XML
    for text in [
        "Natijalar hisoboti",
        "Asosiy xulosalar",
        "Fakultetlar kesimida",
        "Tyutorlar kesimida",
        tutor.full_name,
        "Savollar bo&apos;yicha natijalar" if "&apos;" in xml else "Savollar bo'yicha natijalar",
        "IT va dasturlash",
        "Hakatonda 1-o",
        "Tuzilgan klublar",
        "Rahbar Rektorov",
    ]:
        assert text in xml, text
    assert 'w:fill="0E5A73"' in xml  # diagramma chiziqlari

    filtered = client.get(
        reverse("web:survey-export-docx", args=[survey.pk]), {"answer": f"{track.pk}:{Track.RESEARCH}"}
    )
    xml = zipfile.ZipFile(io.BytesIO(filtered.content)).read("word/document.xml").decode()
    assert "faqat quyidagi javobni berganlar" in xml

    student = User.objects.filter(role=User.Role.STUDENT).first()
    client.force_login(student)
    assert client.get(reverse("web:survey-export-docx", args=[survey.pk])).status_code in (302, 403)
