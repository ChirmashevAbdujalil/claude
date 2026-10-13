from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.models import Faculty, User
from apps.audit.context import request_scope
from apps.audit.models import AuditLog
from apps.discovery.models import TalentFlag
from apps.notifications.models import Notification
from apps.opportunities.models import Opportunity
from apps.profiles.models import Achievement
from apps.talent import diagnostics, services
from apps.talent.models import DevelopmentGoal, DiagnosticResult, TalentProfile
from apps.talent.tracks import Track
from apps.tenants import services as tenant_services
from apps.tenants.context import default_institution

TODAY = timezone.localdate()


def answers_for(track):
    return {
        key: max(options, key=lambda option: option[2].get(track, 0))[0] for key, _, options in diagnostics.QUESTIONS
    }


def titles(user):
    return list(Notification.objects.filter(user=user).values_list("title", flat=True))


@pytest.fixture
def rector(make_user):
    return make_user(role=User.Role.RECTOR, username="rektor")


@pytest.fixture
def profile(student, rector):
    return services.ensure_profile(student, source=TalentProfile.Source.MANUAL, track=Track.IT, by=rector)[0]


# ---------------------------------------------------------------- reyestr va holat zanjiri


def test_teacher_flag_adds_student_to_registry(student, teacher):
    TalentFlag.objects.create(student=student, flagged_by=teacher, area="engineering", note="Qurilma yasaydi")
    profile = TalentProfile.objects.get(student=student)
    assert profile.source == TalentProfile.Source.FLAG and profile.track == Track.INVENTION
    assert profile.status == TalentProfile.Status.IDENTIFIED and "Qurilma yasaydi" in profile.note
    assert any("reyestriga" in t for t in titles(student))


def test_status_pipeline_follows_real_work(profile, teacher, rector):
    services.assign_mentor(profile, teacher, by=rector)
    assert profile.status == TalentProfile.Status.MENTORED
    assert any("shogird" in t for t in titles(teacher)) and any("mentor" in t for t in titles(profile.student))

    goal = services.save_goal(
        DevelopmentGoal(profile=profile, title="Olimpiada", due_date=TODAY + timedelta(days=10)), by=teacher
    )
    profile.refresh_from_db()
    assert profile.status == TalentProfile.Status.DEVELOPING

    goal.status = DevelopmentGoal.Status.DONE
    services.save_goal(goal)
    assert goal.progress == 100 and goal.completed_at is not None

    Achievement.objects.create(user=profile.student, kind="olympiad", title="Respublika olimpiadasi, 2-o'rin",
                               achieved_on=TODAY, status=Achievement.Status.APPROVED)  # fmt: skip
    profile.refresh_from_db()
    assert profile.status == TalentProfile.Status.ACHIEVED and profile.stage == 4


def test_approved_olympiad_brings_new_student_into_registry(make_user):
    winner = make_user()
    Achievement.objects.create(user=winner, kind="patent", title="Patent", achieved_on=TODAY,
                               status=Achievement.Status.PENDING)  # fmt: skip
    assert not TalentProfile.objects.filter(student=winner).exists()
    achievement = Achievement.objects.get(user=winner)
    achievement.status = Achievement.Status.APPROVED
    achievement.save()
    profile = TalentProfile.objects.get(student=winner)
    assert profile.track == Track.INVENTION and profile.status == TalentProfile.Status.ACHIEVED


def test_mentor_must_be_staff_of_same_institution(profile, make_user):
    with pytest.raises(services.TalentError):
        services.assign_mentor(profile, make_user())  # talaba mentor bo'la olmaydi
    tatu, tatu_admin, _ = tenant_services.create_institution(name="TATU", short_name="TATU", slug="tatu")
    with pytest.raises(services.TalentError):
        services.assign_mentor(profile, tatu_admin)


def test_only_students_enter_registry(teacher):
    with pytest.raises(services.TalentError):
        services.ensure_profile(teacher, source=TalentProfile.Source.MANUAL)


# ---------------------------------------------------------------- diagnostika va yo'naltirish


def test_diagnostic_requires_all_answers_and_finds_track(student):
    with pytest.raises(ValueError):
        services.save_diagnostic(student, {"free_time": "code"})
    result = services.save_diagnostic(student, answers_for(Track.IT))
    assert result.track == Track.IT and result.scores[Track.IT] == 100
    assert result.second_track != Track.IT and set(result.scores) == set(Track.values)
    # Qayta topshirilsa, natija yangilanadi
    result = services.save_diagnostic(student, answers_for(Track.CREATIVE))
    assert DiagnosticResult.objects.get(user=student).track == Track.CREATIVE


def test_diagnostic_fills_empty_registry_track(student, rector):
    profile, _ = services.ensure_profile(student, source=TalentProfile.Source.MANUAL, by=rector)
    assert profile.track == ""
    services.save_diagnostic(student, answers_for(Track.RESEARCH))
    profile.refresh_from_db()
    assert profile.track == Track.RESEARCH


def test_new_opportunity_reaches_matching_students_only(django_capture_on_commit_callbacks, make_user, rector):
    it_student, research_student, archived, low_level = make_user(), make_user(), make_user(), make_user()
    services.ensure_profile(it_student, source="manual", track=Track.IT)
    services.save_diagnostic(research_student, answers_for(Track.RESEARCH))
    old, _ = services.ensure_profile(archived, source="manual", track=Track.IT)
    TalentProfile.objects.filter(pk=old.pk).update(status=TalentProfile.Status.ARCHIVED)
    services.save_diagnostic(low_level, answers_for(Track.IT))
    User.objects.filter(pk__in=[it_student.pk]).update(xp=5000)

    with django_capture_on_commit_callbacks(execute=True):
        Opportunity.objects.create(kind="hackathon", title="AI hakaton", organization="IT Park", description="48 soat",
                                   tracks=[Track.IT], min_level=2, created_by=rector)  # fmt: skip
    assert any("AI hakaton" in t for t in titles(it_student))
    for other in (research_student, archived, low_level):
        assert not any("AI hakaton" in t for t in titles(other))


def test_opportunity_kind_gives_default_tracks(make_user, rector):
    student = make_user()
    services.save_diagnostic(student, answers_for(Track.RESEARCH))
    grant = Opportunity.objects.create(kind="grant", title="Grant", organization="Vazirlik", description="-",
                                       created_by=rector)  # fmt: skip
    assert services.opportunity_tracks(grant) == [Track.RESEARCH, Track.STARTUP]
    assert student in services.matching_students(grant)


# ---------------------------------------------------------------- eslatmalar


def test_reminders_are_sent_once(profile, teacher, rector, make_user, faculty):
    services.assign_mentor(profile, teacher)
    soon = services.save_goal(DevelopmentGoal(profile=profile, title="Tezis", due_date=TODAY + timedelta(days=2)))
    late = services.save_goal(DevelopmentGoal(profile=profile, title="Maqola", due_date=TODAY - timedelta(days=1)))
    stats = services.send_reminders(TODAY)
    assert stats["soon"] == 1 and stats["overdue"] == 1
    assert services.send_reminders(TODAY) == {"soon": 0, "overdue": 0, "unattended": 0}
    assert any("Maqsad muddati" in t and "Tezis" in t for t in titles(profile.student))
    assert any("muddati o'tdi" in t for t in titles(teacher))
    assert soon.pk and late.pk


def test_unattended_talents_reported_to_dean_on_monday(make_user, faculty):
    dean = make_user(role=User.Role.DEAN, faculty=faculty)
    waiting = make_user(faculty=faculty)
    profile, _ = services.ensure_profile(waiting, source="manual")
    TalentProfile.objects.filter(pk=profile.pk).update(created_at=timezone.now() - timedelta(days=30))
    monday = TODAY - timedelta(days=TODAY.weekday())
    assert services.send_reminders(monday)["unattended"] == 1
    assert any("mentorsiz" in t for t in titles(dean))


# ---------------------------------------------------------------- sahifalar va huquqlar


def test_registry_permissions_and_dean_scope(client, student, make_user, faculty, rector):
    other_faculty = Faculty.objects.create(name="Boshqa fakultet", short_name="BF")
    mine = make_user(faculty=faculty, first_name="Mening", last_name="Talabam")
    theirs = make_user(faculty=other_faculty, first_name="Begona", last_name="Talaba")
    services.ensure_profile(mine, source="manual")
    services.ensure_profile(theirs, source="manual")

    client.force_login(student)
    assert client.get("/iqtidorlar/").status_code == 403
    client.force_login(make_user(role=User.Role.DEAN, faculty=faculty))
    page = client.get("/iqtidorlar/").content.decode()
    assert "Mening Talabam" in page and "Begona Talaba" not in page
    client.force_login(rector)
    page = client.get("/iqtidorlar/").content.decode()
    assert "Mening Talabam" in page and "Begona Talaba" in page


def test_rector_adds_student_and_assigns_mentor(client, rector, student, teacher):
    client.force_login(rector)
    response = client.post("/iqtidorlar/qoshish/", {"username": student.username, "track": "it", "note": "Kuchli"})
    profile = TalentProfile.objects.get(student=student)
    assert response.url == f"/iqtidorlar/{profile.pk}/"
    assert client.get(response.url).status_code == 200
    client.post(f"/iqtidorlar/{profile.pk}/mentor/", {"mentor": teacher.pk})
    profile.refresh_from_db()
    assert profile.mentor == teacher and profile.status == TalentProfile.Status.MENTORED
    entries = AuditLog.objects.filter(target_type="talent.talentprofile", action="update")
    entry = next(e for e in entries if "mentor" in e.changes)
    assert entry.changes["mentor"]["new"] == str(teacher) and entry.actor == rector


def test_mentor_plans_and_student_updates_progress(client, profile, teacher, make_user, rector):
    services.assign_mentor(profile, teacher, by=rector)
    stranger = make_user(role=User.Role.TEACHER)
    client.force_login(stranger)
    assert client.get(f"/iqtidorlar/{profile.pk}/").status_code == 403

    client.force_login(teacher)
    goal_data = {"title": "Olimpiadaga tayyorlanish", "kind": "olympiad", "due_date": TODAY + timedelta(days=30),
                 "status": "planned", "progress": 0, "mentor_comment": ""}  # fmt: skip
    client.post(f"/iqtidorlar/{profile.pk}/maqsad/", goal_data)
    goal = DevelopmentGoal.objects.get(profile=profile)
    assert goal.created_by == teacher
    assert "Shogirdlarim" in client.get("/shogirdlarim/").content.decode()

    client.force_login(profile.student)
    assert client.post(f"/iqtidorlar/{profile.pk}/maqsad/", goal_data).status_code == 403
    prefix = f"g{goal.pk}"
    update = {f"{prefix}-status": "in_progress", f"{prefix}-progress": 50, f"{prefix}-student_note": "Yarmi tayyor"}
    client.post(f"/maqsadlar/{goal.pk}/", {**update, "next": "/mening-yolim/"})
    goal.refresh_from_db()
    assert goal.status == "in_progress" and goal.progress == 50 and goal.title == "Olimpiadaga tayyorlanish"
    assert any("maqsadini yangiladi" in t for t in titles(teacher))
    page = client.get("/mening-yolim/").content.decode()
    assert "Olimpiadaga tayyorlanish" in page and str(teacher) in page


def test_diagnostic_page_flow(client, student):
    client.force_login(student)
    assert "Iqtidor yo&#x27;nalishingizni aniqlang" in client.get("/app/").content.decode()
    assert client.get("/mening-yolim/test/").status_code == 200
    page = client.post("/mening-yolim/test/", {"free_time": "code"}).content.decode()
    assert "Barcha savollarga javob bering" in page
    response = client.post("/mening-yolim/test/", answers_for(Track.STARTUP))
    assert response.url == "/mening-yolim/"
    assert "Startap va tadbirkorlik" in client.get("/mening-yolim/").content.decode()


def test_opportunity_form_saves_tracks_and_list_marks_match(client, make_user, student, rector):
    services.save_diagnostic(student, answers_for(Track.IT))
    client.force_login(rector)
    form = {"kind": "vacancy", "title": "Junior dasturchi", "organization": "EPAM", "description": "Python"}
    client.post("/opportunities/new/", {**form, "min_level": 1, "tracks": ["it", "startup"]})
    opportunity = Opportunity.objects.get(title="Junior dasturchi")
    assert opportunity.tracks == ["it", "startup"]
    client.force_login(student)
    assert "Sizga mos" in client.get("/opportunities/").content.decode()


def test_report_html_pdf_csv(client, profile, teacher, rector):
    services.assign_mentor(profile, teacher, by=rector)
    Achievement.objects.create(user=profile.student, kind="publication", title="Maqola", achieved_on=TODAY,
                               status=Achievement.Status.APPROVED)  # fmt: skip
    client.force_login(rector)
    page = client.get("/iqtidorlar/hisobot/").content.decode()
    assert "Fakultetlar kesimida" in page and "Maqola" in page
    pdf = client.get("/iqtidorlar/hisobot/?format=pdf")
    assert pdf["Content-Type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    csv = client.get("/iqtidorlar/hisobot/?format=csv").content.decode()
    assert "Reyestrda,1" in csv and "Maqola" in csv
    data = services.report(rector, *services.semester_bounds())
    assert data["totals"]["mentored_pct"] == 100 and data["totals"]["results"] == 1


def test_semester_bounds():
    from datetime import date

    assert services.semester_bounds(date(2026, 10, 13)) == (date(2026, 9, 1), date(2027, 1, 31))
    assert services.semester_bounds(date(2027, 1, 10)) == (date(2026, 9, 1), date(2027, 1, 31))
    assert services.semester_bounds(date(2027, 3, 1)) == (date(2027, 2, 1), date(2027, 8, 31))


def test_portfolio_offers_registry_button(client, rector, student):
    student.portfolio_slug = "talaba-1"
    student.save()
    client.force_login(rector)
    assert "Iqtidorlar reyestriga qo" in client.get("/u/talaba-1/").content.decode()


def test_seed_demo_builds_talent_pipeline():
    call_command("seed", "--demo", verbosity=0)
    statuses = set(TalentProfile.objects.values_list("status", flat=True))
    assert statuses == {"identified", "mentored", "developing", "achieved"}
    assert DevelopmentGoal.objects.filter(due_date__lt=TODAY, status="in_progress").exists()
    count = TalentProfile.objects.count()
    call_command("seed", "--demo", verbosity=0)  # takroriy ishga tushirish xavfsiz
    assert TalentProfile.objects.count() == count


def test_audit_scope_helper_is_available():
    request = RequestFactory().get("/")
    request.institution = default_institution()
    with request_scope(request):
        assert True
