from datetime import timedelta

from django.utils import timezone

from apps.community.models import Event


def make_event(creator, starts_in=timedelta(0), duration=timedelta(hours=2), **kwargs):
    starts_at = timezone.now() + starts_in
    return Event.objects.create(
        title="Robototexnika master-klassi",
        description="Tavsif",
        location="A-101",
        starts_at=starts_at,
        ends_at=starts_at + duration,
        created_by=creator,
        **kwargs,
    )


def test_event_check_in_awards_once(api, student, teacher):
    event = make_event(teacher, xp_reward=25)
    client = api(student)
    response = client.post("/api/v1/events/check-in/", {"code": event.checkin_code}, format="json")
    assert response.status_code == 200
    assert response.data["attended_at"]
    student.refresh_from_db()
    assert student.xp == 25
    again = client.post("/api/v1/events/check-in/", {"code": event.checkin_code}, format="json")
    assert again.status_code == 400


def test_check_in_outside_window(api, student, teacher):
    event = make_event(teacher, starts_in=timedelta(days=2))
    response = api(student).post("/api/v1/events/check-in/", {"code": event.checkin_code}, format="json")
    assert response.status_code == 400


def test_check_in_wrong_code(api, student):
    assert api(student).post("/api/v1/events/check-in/", {"code": "nope"}, format="json").status_code == 400


def test_qr_code_only_for_organizers(api, student, teacher):
    event = make_event(teacher)
    assert api(student).get(f"/api/v1/events/{event.id}/qr/").status_code == 403
    assert api(teacher).get(f"/api/v1/events/{event.id}/qr/").data["code"] == event.checkin_code


def test_checkin_code_not_exposed_in_list(api, student, teacher):
    make_event(teacher)
    data = api(student).get("/api/v1/events/").data["results"][0]
    assert "checkin_code" not in data


def test_registration_capacity(api, teacher, make_user):
    event = make_event(teacher, starts_in=timedelta(days=1), capacity=1)
    assert api(make_user()).post(f"/api/v1/events/{event.id}/register/").status_code == 201
    assert api(make_user()).post(f"/api/v1/events/{event.id}/register/").status_code == 400


def test_post_like_toggle_and_comments(api, student, make_user):
    client = api(student)
    post_id = client.post("/api/v1/posts/", {"text": "Birinchi robotimni yasadim!"}, format="json").data["id"]
    fan = api(make_user())
    assert fan.post(f"/api/v1/posts/{post_id}/like/").data == {"liked": True, "like_count": 1}
    assert fan.post(f"/api/v1/posts/{post_id}/like/").data == {"liked": False, "like_count": 0}
    fan.post(f"/api/v1/posts/{post_id}/comments/", {"text": "Zo'r!"}, format="json")
    feed = client.get("/api/v1/posts/").data["results"][0]
    assert feed["comment_count"] == 1


def test_only_author_edits_post(api, student, make_user):
    post_id = api(student).post("/api/v1/posts/", {"text": "Salom"}, format="json").data["id"]
    assert api(make_user()).patch(f"/api/v1/posts/{post_id}/", {"text": "x"}, format="json").status_code == 403
