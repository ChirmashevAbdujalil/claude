import csv
import io
import zipfile

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import Faculty, User
from apps.notifications.models import Notification
from apps.surveys import analytics, clubs, services
from apps.surveys.models import Club, Question
from apps.talent.models import TalentProfile
from apps.talent.tracks import Track

Kind = Question.Kind


@pytest.fixture
def rector(make_user):
    return make_user(role=User.Role.RECTOR, username="rektor")


@pytest.fixture
def survey(rector):
    survey = services.create_survey(rector, "census")
    services.publish(survey)
    return survey


@pytest.fixture
def other_faculty(db):
    return Faculty.objects.create(name="Energetika", short_name="EN")


def web(user=None):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def q(survey, kind=None, title=None):
    qs = survey.questions.all()
    if kind:
        qs = qs.filter(kind=kind)
    if title:
        qs = qs.filter(title=title)
    return qs.first()


@pytest.fixture
def filled(survey, faculty, other_faculty):
    """6 ta javob: 4 tasi IT (3 tasi bitta fakultetdan), 2 tasi Ilmiy; faoliyatlar bir nechta variantli."""
    track, did, scale = (
        q(survey, Kind.TRACK),
        q(survey, title="Qaysi faoliyatlarda qatnashgansiz?"),
        q(survey, Kind.SCALE),
    )
    rows = [
        ("Aliyev Ali", faculty, Track.IT, ["Hakaton yoki IT tanlov", "Fan olimpiadasi"], 5),
        ("Valiyev Vali", faculty, Track.IT, ["Hakaton yoki IT tanlov"], 4),
        ("Karimova Aziza", faculty, Track.IT, ["Hakaton yoki IT tanlov", "Robototexnika"], 3),
        ("Toshmatov Jasur", other_faculty, Track.IT, ["Fan olimpiadasi"], 4),
        ("Yusupova Madina", other_faculty, Track.RESEARCH, ["Ilmiy maqola yoki tezis"], 5),
        ("Ergasheva Nilufar", faculty, Track.RESEARCH, [], 2),
    ]
    out = []
    for i, (name, fac, track_value, activities, score) in enumerate(rows):
        answers = {str(track.pk): track_value, str(scale.pk): score}
        if activities:
            answers[str(did.pk)] = activities
        out.append(
            services.submit(
                survey,
                answers=answers,
                identity={"full_name": name, "faculty": fac, "course": 1 + i % 3, "phone": f"+99890000000{i}"},
            )
        )
    return out


# ---------------------------------------------------------------- tahlil


def test_answer_filter_and_drill_down(rector, survey, filled):
    track, did = q(survey, Kind.TRACK), q(survey, title="Qaysi faoliyatlarda qatnashgansiz?")
    conditions = analytics.parse_conditions(
        survey, [f"{track.pk}:{Track.IT}", f"{did.pk}:Fan olimpiadasi", "999:x", f"{track.pk}:yoq"]
    )
    assert len(conditions) == 2 and conditions[0]["label"] == "IT va dasturlash"
    matched = analytics.apply_conditions(survey.responses.all(), conditions)
    assert {r.full_name for r in matched} == {"Aliyev Ali", "Toshmatov Jasur"}

    other = analytics.parse_conditions(survey, [f"{did.pk}:__other__"])
    assert [r.full_name for r in analytics.apply_conditions(survey.responses.all(), other)] == ["Karimova Aziza"]

    url = reverse("web:survey-results", args=[survey.pk])
    page = web(rector).get(url, {"tab": "responses", "answer": f"{track.pk}:{Track.RESEARCH}"}).content.decode()
    assert "Yusupova Madina" in page and "Aliyev Ali" not in page and "Faqat shu javobni berganlar" in page
    export = web(rector).get(reverse("web:survey-export", args=[survey.pk]), {"answer": f"{track.pk}:{Track.RESEARCH}"})
    assert len(list(csv.reader(io.StringIO(export.content.decode("utf-8-sig"))))) == 3  # sarlavha + 2


def test_crosstab_timeline_completeness_and_insights(survey, filled, faculty):
    track = q(survey, Kind.TRACK)
    table = analytics.crosstab(survey, survey.responses.all(), track, "faculty")
    rows = {r["label"]: r for r in table["rows"]}
    it_index = table["columns"].index("IT va dasturlash")
    assert rows["KI"]["total"] == 4 and rows["KI"]["cells"][it_index]["count"] == 3
    assert rows["KI"]["cells"][it_index]["pct"] == 75 and rows["KI"]["best"] == it_index
    assert table["totals"][it_index] == 4

    did = q(survey, title="Qaysi faoliyatlarda qatnashgansiz?")
    by_activity = analytics.crosstab(survey, survey.responses.all(), track, f"q{did.pk}")
    assert {r["label"] for r in by_activity["rows"]} >= {"Hakaton yoki IT tanlov", "Boshqa"}

    timeline = analytics.timeline(survey.responses.all())
    assert timeline["days"][-1]["count"] == 6 and timeline["days"][-1]["today"] and timeline["week"] == 6
    complete = analytics.completeness(survey, survey.responses.all())
    assert 0 < complete["average"] < 100 and sum(b["count"] for b in complete["buckets"]) == 6

    summary = services.summary(survey, survey.responses.all())
    texts = " ".join(i["text"] for i in analytics.insights(survey, survey.responses.all(), summary, timeline, complete))
    assert "IT va dasturlash (67%)" in texts and "Eng faol fakultet: KI" in texts


def test_analysis_tab_renders(rector, survey, filled):
    page = web(rector).get(reverse("web:survey-results", args=[survey.pk]), {"tab": "analysis"}).content.decode()
    assert "Asosiy xulosalar" in page and "Kesishma jadval" in page and "Javoblar dinamikasi" in page


# ---------------------------------------------------------------- klublar


def test_form_clubs_by_track_with_leader_and_notifications(rector, survey, filled):
    track = q(survey, Kind.TRACK)
    preview = {p["value"]: p for p in clubs.preview(survey, track, survey.responses.all())}
    assert (
        preview[Track.IT]["count"] == 4 and preview[Track.RESEARCH]["count"] == 2 and preview[Track.IT]["emoji"] == "💻"
    )

    result = clubs.form_clubs(survey, track, survey.responses.all(), by=rector, min_members=3)
    assert result == {"created": 1, "updated": 0, "members": 4}
    club = Club.objects.get()
    assert club.name == "IT va dasturlash klubi" and club.members.count() == 4
    assert club.leader.first_name == "Ali"  # eng to'liq javob va eng yuqori o'z bahosi
    assert Notification.objects.filter(title__contains="IT va dasturlash klubi").count() == 4

    # Takror tuzilganda takrorlanmaydi; kichik variantni ham tanlab ochish mumkin
    again = clubs.form_clubs(survey, track, survey.responses.all(), by=rector, values=[Track.RESEARCH], min_members=1)
    assert again == {"created": 1, "updated": 0, "members": 2} and Club.objects.count() == 2


def test_multiple_choice_puts_student_in_several_clubs(rector, survey, filled):
    did = q(survey, title="Qaysi faoliyatlarda qatnashgansiz?")
    clubs.form_clubs(survey, did, survey.responses.all(), by=rector, min_members=2)
    assert set(Club.objects.values_list("name", flat=True)) == {"Hakaton yoki IT tanlov klubi", "Fan olimpiadasi klubi"}
    ali = filled[0]
    assert ali.club_memberships.count() == 2


def test_sync_adds_late_respondents(rector, survey, filled, faculty):
    track = q(survey, Kind.TRACK)
    clubs.form_clubs(survey, track, survey.responses.all(), by=rector)
    club = Club.objects.get()
    services.submit(survey, answers={str(track.pk): Track.IT}, identity={"full_name": "Kech Keldi", "faculty": faculty})
    assert clubs.sync(club, survey.responses.all()) == 1 and club.members.count() == 5


def test_club_pages_and_actions(rector, survey, filled, make_user, student):
    track = q(survey, Kind.TRACK)
    url = reverse("web:survey-clubs-create", args=[survey.pk])
    page = (
        web(rector)
        .post(
            url,
            {
                "question": track.pk,
                "option": [Track.IT],
            },
            follow=True,
        )
        .content.decode()
    )
    assert "Yangi klublar: 1" in page and "IT va dasturlash klubi" in page
    club = Club.objects.get()
    detail = reverse("web:club-detail", args=[survey.pk, club.pk])
    teacher = make_user(role=User.Role.TEACHER, first_name="Mentor", last_name="Ustoz")
    web(rector).post(detail, {"name": "IT klubi", "emoji": "🖥", "description": "Har payshanba", "mentor": teacher.pk,
                              "leader": club.leader_id, "telegram_url": "t.me/it_klub"})  # fmt: skip
    club.refresh_from_db()
    assert club.name == "IT klubi" and club.mentor == teacher and club.telegram_url == "https://t.me/it_klub"

    action = lambda name, **data: web(rector).post(reverse("web:club-action", args=[survey.pk, club.pk, name]), data)  # noqa: E731
    action("notify", title="Uchrashuv", body="Payshanba 15:00")
    assert Notification.objects.filter(title="🖥 Uchrashuv").count() == 4
    action("register")
    assert TalentProfile.objects.filter(source=TalentProfile.Source.SURVEY).count() == 4
    export = web(rector).get(reverse("web:club-export", args=[survey.pk, club.pk]))
    sheet = zipfile.ZipFile(io.BytesIO(export.content)).read("xl/worksheets/sheet1.xml").decode()
    assert "Aliyev Ali" in sheet and "Sardor" in sheet
    csv_export = web(rector).get(reverse("web:club-export", args=[survey.pk, club.pk]), {"format": "csv"})
    assert "Aliyev Ali" in csv_export.content.decode("utf-8-sig")

    member_user = filled[0].user
    assert "Har payshanba" in web(member_user).get(reverse("web:club-page", args=[club.pk])).content.decode()
    assert web(student).get(reverse("web:club-page", args=[club.pk])).status_code == 404
    assert web().get(reverse("web:club-page", args=[club.pk])).status_code == 302
    assert "IT klubi" in web(member_user).get(reverse("web:surveys")).content.decode()

    member = club.members.first()
    action("remove", member=member.pk)
    assert club.members.count() == 3
    action("delete")
    assert not Club.objects.exists()


def test_clubs_permissions(rector, survey, filled, make_user, faculty, teacher):
    track = q(survey, Kind.TRACK)
    dean = make_user(role=User.Role.DEAN, faculty=faculty)
    url = reverse("web:survey-clubs-create", args=[survey.pk])
    assert web(dean).post(url, {"question": track.pk}).status_code == 403
    assert web(teacher).post(url, {"question": track.pk}).status_code == 403
    assert not Club.objects.exists()
    page = web(rector).get(reverse("web:survey-results", args=[survey.pk]), {"tab": "clubs"}).content.decode()
    assert "Belgilanganlardan klub tuzish" in page and "IT va dasturlash" in page
