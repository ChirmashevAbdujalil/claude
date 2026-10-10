from datetime import timedelta

import pytest
from django.utils import timezone

from apps.discovery.models import Challenge, Submission


@pytest.fixture
def make_challenge(teacher):
    def factory(**kwargs):
        now = timezone.now()
        kwargs.setdefault("title", "Test challenge")
        kwargs.setdefault("description", "Shart")
        kwargs.setdefault("starts_at", now - timedelta(hours=1))
        kwargs.setdefault("ends_at", now + timedelta(days=1))
        return Challenge.objects.create(created_by=teacher, **kwargs)

    return factory


def test_default_xp_by_kind(make_challenge):
    assert make_challenge(kind=Challenge.Kind.DAILY).xp_reward == 10
    assert make_challenge(kind=Challenge.Kind.MONTHLY).xp_reward == 300


def test_auto_checked_correct_answer(api, student, make_challenge):
    challenge = make_challenge(kind=Challenge.Kind.DAILY, expected_answer="3")
    response = api(student).post(f"/api/v1/challenges/{challenge.id}/submit/", {"answer": " 3 "}, format="json")
    assert response.status_code == 201
    assert response.data["status"] == Submission.Status.ACCEPTED
    student.refresh_from_db()
    # 10 XP + "Birinchi qadam" nishoni bonusi 20 XP
    assert student.xp == 30
    assert student.streak.current == 1


def test_auto_checked_wrong_answer(api, student, make_challenge):
    challenge = make_challenge(expected_answer="3")
    response = api(student).post(f"/api/v1/challenges/{challenge.id}/submit/", {"answer": "4"}, format="json")
    assert response.data["status"] == Submission.Status.REJECTED
    student.refresh_from_db()
    assert student.xp == 0


def test_cannot_submit_twice(api, student, make_challenge):
    challenge = make_challenge()
    client = api(student)
    client.post(f"/api/v1/challenges/{challenge.id}/submit/", {"answer": "javob"}, format="json")
    response = client.post(f"/api/v1/challenges/{challenge.id}/submit/", {"answer": "javob"}, format="json")
    assert response.status_code == 400


def test_closed_challenge_hidden_and_rejected(api, student, make_challenge):
    past = timezone.now() - timedelta(days=2)
    challenge = make_challenge(starts_at=past, ends_at=past + timedelta(hours=1))
    client = api(student)
    assert client.get("/api/v1/challenges/").data["count"] == 0
    assert client.post(f"/api/v1/challenges/{challenge.id}/submit/", {"answer": "x"}).status_code == 404


def test_expected_answer_is_hidden_from_students(api, student, make_challenge):
    make_challenge(expected_answer="maxfiy")
    data = api(student).get("/api/v1/challenges/").data["results"][0]
    assert "expected_answer" not in data
    assert data["auto_checked"] is True


def test_teacher_review_scales_xp(api, student, teacher, make_challenge):
    challenge = make_challenge(kind=Challenge.Kind.WEEKLY)
    submission_id = (
        api(student)
        .post(f"/api/v1/challenges/{challenge.id}/submit/", {"link": "https://github.com/x/y"}, format="json")
        .data["id"]
    )
    response = api(teacher).post(
        f"/api/v1/submissions/{submission_id}/review/",
        {"accept": True, "score": 80, "feedback": "Zo'r"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["xp_awarded"] == 40
    again = api(teacher).post(f"/api/v1/submissions/{submission_id}/review/", {"accept": True}, format="json")
    assert again.status_code == 400


def test_student_cannot_review_or_create(api, student, make_user, make_challenge):
    challenge = make_challenge()
    other = make_user()
    submission_id = (
        api(other).post(f"/api/v1/challenges/{challenge.id}/submit/", {"answer": "x"}, format="json").data["id"]
    )
    client = api(student)
    assert client.post(f"/api/v1/submissions/{submission_id}/review/", {"accept": True}).status_code == 403
    assert client.post("/api/v1/challenges/", {"title": "x"}).status_code == 403


def test_faculty_only_challenge(api, make_user, make_challenge):
    from apps.accounts.models import Faculty

    other_faculty = Faculty.objects.create(name="Energetika", short_name="EN")
    challenge = make_challenge(faculty=other_faculty)
    student = make_user()
    assert api(student).get(f"/api/v1/challenges/{challenge.id}/").status_code == 404


def test_talent_flag_only_for_reviewers(api, student, teacher):
    payload = {"student": student.id, "area": "engineering", "note": "Laboratoriyada ajoyib g'oya taklif qildi"}
    assert api(student).post("/api/v1/talent-flags/", payload, format="json").status_code == 403
    response = api(teacher).post("/api/v1/talent-flags/", payload, format="json")
    assert response.status_code == 201
    assert response.data["flagged_by"]["id"] == teacher.id
