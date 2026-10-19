import csv
import io
import json
from datetime import timedelta
from html import escape

import pytest
from django.core.management import call_command
from django.http import QueryDict
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Faculty, User
from apps.notifications.models import Notification
from apps.surveys import services
from apps.surveys.models import Question, Response, Survey
from apps.surveys.services import SurveyError
from apps.talent.models import TalentProfile
from apps.talent.tracks import Track
from apps.tenants.context import activate
from apps.tenants.models import Institution

Kind = Question.Kind


@pytest.fixture
def rector(make_user):
    return make_user(role=User.Role.RECTOR, username="rektor")


@pytest.fixture
def web():
    def factory(user=None):
        client = Client()
        if user is not None:
            client.force_login(user)
        return client

    return factory


@pytest.fixture
def survey(rector):
    survey = services.create_survey(rector, "census")
    services.publish(survey)
    return survey


def q(survey, kind=None, title=None):
    questions = survey.questions.all()
    if kind:
        questions = questions.filter(kind=kind)
    if title:
        questions = questions.filter(title=title)
    return questions.first()


def post_data(survey, faculty, **extra):
    """Shablondagi majburiy savollarga to'g'ri javoblar va talaba ma'lumotlari."""
    data = {
        f"q{q(survey, Kind.TRACK).pk}": Track.IT,
        f"q{q(survey, title='Eng yuqori natijangiz qaysi darajada?').pk}": "Viloyat",
        f"q{q(survey, Kind.SCALE).pk}": "4",
        f"q{q(survey, title='Mentor (ustoz) bilan ishlashni xohlaysizmi?').pk}": "Ha, albatta",
        "who-full_name": "Aziza Karimova",
        "who-faculty": faculty.pk,
        "who-course": "2",
        "who-group": "k2105",
        "who-phone": "+998 90 123 45 67",
    }
    data.update(extra)
    return data


def form_data(**values):
    data = QueryDict(mutable=True)
    for key, value in values.items():
        if isinstance(value, list):
            data.setlist(key, value)
        else:
            data[key] = value
    return data


# ---------------------------------------------------------------- tuzilma


def test_census_template_is_ready_to_publish(rector):
    survey = services.create_survey(rector, "census")
    assert survey.status == Survey.Status.DRAFT and survey.talent_census and survey.created_by == rector
    kinds = list(survey.questions.values_list("kind", flat=True))
    assert Kind.TRACK in kinds and Kind.SECTION in kinds and len(kinds) == 14
    assert services.answerable_count(survey) == 11


def test_save_schema_keeps_ids_reorders_and_removes(rector):
    survey = services.create_survey(rector, "blank")
    first = survey.questions.get()
    services.save_schema(
        survey,
        json.dumps(
            [
                {"kind": "single", "title": "Kursingiz", "options": ["1", " 2 ", "2", ""], "required": True},
                {"id": first.pk, "kind": "long", "title": "Fikringiz"},
            ]
        ),
    )
    questions = list(survey.questions.all())
    assert [x.title for x in questions] == ["Kursingiz", "Fikringiz"]
    assert questions[0].options == ["1", "2"] and questions[0].required
    assert questions[1].pk == first.pk and questions[1].kind == Kind.LONG

    services.save_schema(survey, [{"id": questions[0].pk, "kind": "section", "title": "Bo'lim", "required": True}])
    remaining = survey.questions.get()
    assert remaining.pk == questions[0].pk and not remaining.required
    assert not Question.objects.filter(pk=first.pk).exists()


@pytest.mark.parametrize(
    "items, message",
    [
        ([{"kind": "short", "title": "  "}], "matnini yozing"),
        ([{"kind": "single", "title": "Tanlang", "options": ["", " "]}], "variant kiriting"),
        ([{"kind": "unknown", "title": "?"}], "noma'lum tur"),
        ("not json", "o'qib bo'lmadi"),
    ],
)
def test_save_schema_rejects_invalid(rector, items, message):
    survey = services.create_survey(rector, "blank")
    with pytest.raises(SurveyError, match=message):
        services.save_schema(survey, items)
    assert survey.questions.count() == 1  # o'zgarish saqlanmadi


def test_scale_is_clamped(rector):
    survey = services.create_survey(rector, "blank")
    services.save_schema(survey, [{"kind": "scale", "title": "Baho", "scale_max": 99}])
    assert survey.questions.get().scale_max == 10


# ---------------------------------------------------------------- javoblarni tekshirish


def test_clean_answers_validates_each_kind(rector):
    survey = services.create_survey(rector, "blank")
    services.save_schema(
        survey,
        [
            {"kind": "single", "title": "A", "options": ["Ha", "Yo'q"], "allow_other": True, "required": True},
            {"kind": "multiple", "title": "B", "options": ["X", "Y"], "allow_other": True},
            {"kind": "scale", "title": "C", "scale_max": 5},
            {"kind": "email", "title": "D"},
            {"kind": "phone", "title": "E"},
            {"kind": "number", "title": "F"},
            {"kind": "date", "title": "G"},
            {"kind": "track", "title": "H", "required": True},
        ],
    )
    a, b, c, d, e, f, g, h = survey.questions.all()

    answers, errors = services.clean_answers(
        survey,
        form_data(
            **{
                f"q{a.pk}": services.OTHER,
                f"q{a.pk}_other": "Bilmayman",
                f"q{b.pk}": ["X", "Z", services.OTHER],
                f"q{b.pk}_other": "Boshqa yo'l",
                f"q{c.pk}": "5",
                f"q{d.pk}": "ali@mail.uz",
                f"q{e.pk}": "+998 (90) 123-45-67",
                f"q{f.pk}": "3,50",
                f"q{g.pk}": "2026-10-19",
                f"q{h.pk}": Track.RESEARCH,
            }
        ),
    )
    assert errors == {}
    assert answers == {
        str(a.pk): "Bilmayman",
        str(b.pk): ["X", "Boshqa yo'l"],
        str(c.pk): 5,
        str(d.pk): "ali@mail.uz",
        str(e.pk): "+998 (90) 123-45-67",
        str(f.pk): "3.5",
        str(g.pk): "2026-10-19",
        str(h.pk): Track.RESEARCH,
    }

    answers, errors = services.clean_answers(
        survey,
        form_data(
            **{
                f"q{a.pk}": "Balki",
                f"q{c.pk}": "9",
                f"q{d.pk}": "ali",
                f"q{e.pk}": "salom",
                f"q{f.pk}": "o'n",
                f"q{g.pk}": "19.10.2026",
            }
        ),
    )
    assert set(errors) == {a.pk, c.pk, d.pk, e.pk, f.pk, g.pk, h.pk}
    assert "majburiy" in errors[h.pk] and answers == {}


# ---------------------------------------------------------------- ommaviy to'ldirish


def test_anonymous_student_fills_public_survey_once(web, survey, faculty):
    client = web()
    url = reverse("web:survey-fill", args=[survey.token])
    page = client.get(url)
    assert page.status_code == 200 and "Iqtidorli talabalarni" in page.content.decode()
    assert page.cookies.get("th_sv")

    response = client.post(url, post_data(survey, faculty))
    assert response.status_code == 302 and response.url == reverse("web:survey-thanks", args=[survey.token])
    saved = Response.objects.get(survey=survey)
    assert saved.full_name == "Aziza Karimova" and saved.faculty == faculty and saved.group == "K-21-05"
    assert saved.user.issued_account.initial_password  # akkaunt avtomatik ochildi
    assert saved.course == 2 and saved.answers[str(q(survey, Kind.TRACK).pk)] == Track.IT
    assert "qabul qilindi" in client.get(response.url).content.decode()

    again = client.get(url)
    assert "allaqachon javob bergansiz" in again.content.decode()
    client.post(url, post_data(survey, faculty))
    assert Response.objects.filter(survey=survey).count() == 1

    # Boshqa brauzer (boshqa talaba) javob bera oladi
    web().post(url, post_data(survey, faculty, **{"who-full_name": "Jasur"}))
    assert Response.objects.filter(survey=survey).count() == 2


def test_errors_keep_entered_answers(web, survey, faculty):
    url = reverse("web:survey-fill", args=[survey.token])
    data = post_data(survey, faculty)
    data.pop(f"q{q(survey, Kind.TRACK).pk}")
    page = web().post(url, data)
    html = page.content.decode()
    assert page.status_code == 200 and "majburiy" in html and "Aziza Karimova" in html
    assert not Response.objects.exists()


def test_honeypot_silently_drops_bots(web, survey, faculty):
    url = reverse("web:survey-fill", args=[survey.token])
    response = web().post(url, post_data(survey, faculty, website="spam.example"))
    assert response.status_code == 302 and not Response.objects.exists()


def test_logged_in_student_gets_xp_once(web, survey, student, faculty):
    client = web(student)
    url = reverse("web:survey-fill", args=[survey.token])
    assert "Aziza" not in client.get(url).content.decode()  # ma'lumotlar profildan olinadi
    client.post(url, post_data(survey, faculty))
    student.refresh_from_db()
    assert student.xp == survey.xp_reward == 50
    assert Response.objects.get(survey=survey).user == student
    assert f"+{survey.xp_reward} XP" in client.get(reverse("web:survey-thanks", args=[survey.token])).content.decode()

    with pytest.raises(SurveyError, match="javob bergansiz"):
        services.submit(survey, answers={}, user=student)
    assert services.open_for(student).count() == 0


def test_anyone_can_answer_without_account(web, survey, faculty):
    """Ro'yxatdan o'tmagan, profilsiz talaba ham javob yuboradi: login sahifasiga yo'naltirilmaydi."""
    url = reverse("web:survey-fill", args=[survey.token])
    page = web().get(url)
    assert page.status_code == 200 and "Yuborish" in page.content.decode()
    web().post(url, post_data(survey, faculty))
    saved = Response.objects.get(survey=survey)
    assert saved.full_name == "Aziza Karimova" and saved.user.role == User.Role.STUDENT


def test_draft_is_hidden_but_management_can_preview(web, rector, student, faculty):
    survey = services.create_survey(rector, "census")
    url = reverse("web:survey-fill", args=[survey.token])
    assert web().get(url).status_code == 404
    assert web(student).get(url).status_code == 404
    page = web(rector).get(url)
    assert page.status_code == 200 and "Ko'rish rejimi" in page.content.decode()
    web(rector).post(url, post_data(survey, faculty))
    assert not Response.objects.exists()


def test_closed_and_expired_surveys_stop_accepting(web, survey):
    url = reverse("web:survey-fill", args=[survey.token])
    survey.closes_at = timezone.now() - timedelta(minutes=1)
    survey.save()
    assert "yopilgan" in web().get(url).content.decode()
    with pytest.raises(SurveyError, match="qabul qilmayapti"):
        services.submit(survey, answers={})
    with pytest.raises(SurveyError, match="Muddat o'tib ketgan"):
        services.publish(survey)

    survey.closes_at = None
    survey.save()
    services.close(survey)
    assert "yopilgan" in web().get(url).content.decode()


def test_other_institution_survey_is_not_reachable(web, rector):
    other = Institution.objects.create(slug="tatu", name="TATU", short_name="TATU")
    with activate(other):
        foreign = Survey.objects.create(title="Boshqa OTM", status=Survey.Status.OPEN, institution=other)
    assert web().get(reverse("web:survey-fill", args=[foreign.token])).status_code == 404
    assert web(rector).get(reverse("web:survey-results", args=[foreign.pk])).status_code == 404


# ---------------------------------------------------------------- boshqaruv


def test_builder_saves_and_publishes_with_notifications(web, rector, student, faculty):
    survey = services.create_survey(rector, "blank")
    schema = [{"kind": "single", "title": "Qaysi kursdasiz?", "options": ["1", "2", "3", "4"], "required": True}]
    response = web(rector).post(
        reverse("web:survey-builder", args=[survey.pk]),
        {
            "title": "Kurs so'rovnomasi",
            "description": "",
            "collect_identity": "on",
            "one_response": "on",
            "xp_reward": "10",
            "thank_you": "",
            "closes_at": "",
            "schema": json.dumps(schema),
            "then": "publish",
            "notify": "1",
        },
    )
    assert response.status_code == 302
    survey.refresh_from_db()
    assert survey.title == "Kurs so'rovnomasi" and survey.status == Survey.Status.OPEN and survey.published_at
    assert survey.questions.get().options == ["1", "2", "3", "4"]
    note = Notification.objects.get(user=student)
    assert "Kurs so'rovnomasi" in note.title and note.url == reverse("web:survey-fill", args=[survey.token])
    assert not Notification.objects.filter(user=rector, title__startswith="Yangi so'rovnoma").exists()


def test_builder_shows_error_and_keeps_draft_schema(web, rector):
    survey = services.create_survey(rector, "blank")
    page = web(rector).post(
        reverse("web:survey-builder", args=[survey.pk]),
        {"title": "X", "xp_reward": "0", "schema": json.dumps([{"kind": "single", "title": "Y"}])},
        follow=True,
    )
    assert "kamida bitta variant" in page.content.decode()
    assert survey.questions.get().kind == Kind.SHORT


def test_publish_requires_a_question(rector):
    survey = Survey.objects.create(title="Bo'sh", created_by=rector)
    with pytest.raises(SurveyError, match="Kamida bitta savol"):
        services.publish(survey)


def test_permissions(web, rector, student, teacher, make_user, faculty):
    survey = services.create_survey(rector, "census")
    for user in (student, teacher):
        assert web(user).get(reverse("web:survey-builder", args=[survey.pk])).status_code == 403
        assert web(user).get(reverse("web:survey-results", args=[survey.pk])).status_code == 403
        assert web(user).post(reverse("web:survey-create"), {"template": "census"}).status_code == 403

    other_faculty = Faculty.objects.create(name="Energetika", short_name="EN")
    dean = make_user(role=User.Role.DEAN, faculty=faculty)
    services.publish(survey)
    services.submit(survey, answers={}, identity={"full_name": "O'z fakulteti", "faculty": faculty})
    services.submit(survey, answers={}, identity={"full_name": "Boshqa fakultet", "faculty": other_faculty})
    assert web(dean).get(reverse("web:survey-builder", args=[survey.pk])).status_code == 403
    page = web(dean).get(reverse("web:survey-results", args=[survey.pk]) + "?tab=responses").content.decode()
    assert "O&#x27;z fakulteti" in page and "Boshqa fakultet" not in page
    assert services.can_edit(dean, services.create_survey(dean, "blank"))


def test_summary_counts_answers(rector, survey, faculty):
    track, scale = q(survey, Kind.TRACK), q(survey, Kind.SCALE)
    level = q(survey, title="Eng yuqori natijangiz qaysi darajada?")
    did = q(survey, title="Qaysi faoliyatlarda qatnashgansiz?")
    for t, lv, s, d in [
        (Track.IT, "Viloyat", 5, ["Fan olimpiadasi", "Robototexnika"]),
        (Track.IT, "Respublika", 4, ["Fan olimpiadasi"]),
        (Track.RESEARCH, "Viloyat", 3, None),
    ]:
        answers = {str(track.pk): t, str(level.pk): lv, str(scale.pk): s}
        if d:
            answers[str(did.pk)] = d
        services.submit(survey, answers=answers, identity={"full_name": "T", "faculty": faculty, "course": 2})

    data = services.summary(survey, survey.responses.all())
    assert data["total"] == 3 and data["courses"] == [("2-kurs", 3)]
    blocks = {b["question"].pk: b for b in data["blocks"] if not b.get("section")}
    bars = {bar["label"]: bar for bar in blocks[track.pk]["bars"]}
    assert bars["IT va dasturlash"]["count"] == 2 and bars["IT va dasturlash"]["pct"] == 67
    assert blocks[scale.pk]["average"] == 4.0
    did_bars = {bar["label"]: bar["count"] for bar in blocks[did.pk]["bars"]}
    assert did_bars["Fan olimpiadasi"] == 2 and did_bars["Boshqa"] == 1
    assert blocks[did.pk]["others"] == ["Robototexnika"] and blocks[did.pk]["skipped"] == 1


def test_results_pages_and_csv_export(web, rector, survey, faculty):
    survey.create_accounts = False
    survey.save()
    services.submit(
        survey,
        answers={str(q(survey, Kind.TRACK).pk): Track.STARTUP},
        identity={"full_name": "Madina", "faculty": faculty, "course": 3, "phone": "+998901112233"},
    )
    client = web(rector)
    results = reverse("web:survey-results", args=[survey.pk])
    assert "Fakultetlar bo'yicha ro'yxatga olish" in client.get(results).content.decode()
    assert "Madina" in client.get(results + "?tab=responses").content.decode()
    response = survey.responses.get()
    detail = client.get(reverse("web:survey-response", args=[survey.pk, response.pk])).content.decode()
    assert "Startap va tadbirkorlik" in detail and "+998901112233" in detail and "Akkauntsiz javob" in detail
    assert "<b>1</b> / 1" in detail
    assert survey.token in client.get(reverse("web:survey-poster", args=[survey.pk])).content.decode()

    export = client.get(reverse("web:survey-export", args=[survey.pk]) + f"?faculty={faculty.pk}")
    rows = list(csv.reader(io.StringIO(export.content.decode("utf-8-sig"))))
    assert rows[0][:3] == ["№", "Yuborilgan vaqt", "F.I.Sh."] and "Qaysi yo'nalishda" in " ".join(rows[0])
    assert rows[1][2] == "Madina" and "Startap va tadbirkorlik" in rows[1]

    client.post(reverse("web:survey-response-delete", args=[survey.pk, response.pk]))
    assert not survey.responses.exists()


def test_register_respondents_in_talent_registry(web, rector, survey, student, faculty):
    survey.create_accounts = False
    survey.save()
    linked = services.submit(survey, answers={str(q(survey, Kind.TRACK).pk): Track.INVENTION}, user=student)
    anonymous = services.submit(survey, answers={}, identity={"full_name": "Anonim talaba", "faculty": faculty})
    response = web(rector).post(
        reverse("web:survey-register", args=[survey.pk]), {"response": [linked.pk, anonymous.pk]}, follow=True
    )
    profile = TalentProfile.objects.get(student=student)
    assert profile.source == TalentProfile.Source.SURVEY and profile.track == Track.INVENTION
    assert "so'rovnomasi orqali" in profile.note and profile.added_by == rector
    html = response.content.decode()
    assert "qo&#x27;shildi: 1" in html and "akkaunti yo&#x27;q: 1" in html
    assert services.register_talents(survey, survey.responses.filter(pk=linked.pk), rector)["existing"] == 1


def test_list_pages_for_roles(web, rector, student, survey):
    management = web(rector).get(reverse("web:surveys")).content.decode()
    assert "Iqtidorlarni ro&#x27;yxatga olish" in management and "Barcha so'rovnomalar" in management
    own = web(student).get(reverse("web:surveys")).content.decode()
    assert "Sizni kutayotgan" in own and "Barcha so'rovnomalar" not in own
    assert escape(survey.title) in web(student).get(reverse("web:dashboard")).content.decode()


def test_duplicate_and_delete(web, rector, survey):
    client = web(rector)
    client.post(reverse("web:survey-duplicate", args=[survey.pk]))
    copy = Survey.objects.exclude(pk=survey.pk).get()
    assert copy.title.endswith("(nusxa)") and copy.status == Survey.Status.DRAFT
    assert copy.questions.count() == survey.questions.count()
    client.post(reverse("web:survey-delete", args=[copy.pk]))
    assert not Survey.objects.filter(pk=copy.pk).exists()


def test_demo_seed_creates_census_with_responses():
    call_command("seed", "--demo", verbosity=0)
    call_command("seed", "--demo", verbosity=0)
    survey = Survey.objects.get(title__endswith="(demo)")
    assert survey.status == Survey.Status.OPEN and survey.responses.count() == 6
    assert not survey.responses.filter(user__isnull=True).exists()
    assert survey.issued_accounts.count() == 2  # anonim javob berganlarga akkaunt ochildi


def test_answer_items_and_navigation(rector, survey, student, faculty):
    track, scale, did = (
        q(survey, Kind.TRACK),
        q(survey, Kind.SCALE),
        q(survey, title="Qaysi faoliyatlarda qatnashgansiz?"),
    )
    first = services.submit(survey, answers={str(track.pk): Track.IT}, identity={"full_name": "A", "faculty": faculty})
    second = services.submit(
        survey,
        answers={str(scale.pk): 4, str(did.pk): ["Fan olimpiadasi", "Robototexnika"]},
        user=student,
    )
    items = {i["question"].pk: i for i in services.answer_items(survey, second) if i["view"] != "section"}
    assert items[scale.pk]["view"] == "scale" and items[scale.pk]["dots"] == [True, True, True, True, False]
    assert items[did.pk]["chips"] == [
        {"text": "Fan olimpiadasi", "other": False},
        {"text": "Robototexnika", "other": True},
    ]
    assert items[track.pk]["view"] == "empty"
    first_items = {i["question"].pk: i for i in services.answer_items(survey, first) if i["view"] != "section"}
    assert first_items[track.pk]["view"] == "track" and first_items[track.pk]["text"] == "IT va dasturlash"

    nav = services.neighbours(survey.responses.all(), first)
    assert nav == {"position": 2, "total": 2, "prev": second.pk, "next": None}


def test_result_pages_share_link_and_missing_link(web, survey, faculty):
    client = web()
    url = reverse("web:survey-fill", args=[survey.token])
    client.get(url)  # brauzer kalitini oladi
    client.post(url, post_data(survey, faculty))
    thanks = client.get(reverse("web:survey-thanks", args=[survey.token])).content.decode()
    assert "t.me/share/url" in thanks and survey.token in thanks
    assert "Kursdoshlaringizga ham ulashing" in client.get(url).content.decode()

    missing = web().get(reverse("web:survey-fill", args=["yoqkalit1"]))
    assert missing.status_code == 404 and "So'rovnoma topilmadi" in missing.content.decode()

    services.close(survey)
    closed = web().get(url).content.decode()
    assert "So'rovnoma yopilgan" in closed and "tugagan" not in closed and "t.me/share" not in closed
