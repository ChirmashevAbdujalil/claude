from apps.accounts.models import Faculty, User
from apps.arena import services as arena


def test_dashboard_requires_management(api, student, teacher):
    assert api(student).get("/api/v1/insights/dashboard/").status_code == 403
    assert api(teacher).get("/api/v1/insights/dashboard/").status_code == 403


def test_rector_sees_everything(api, make_user):
    rector = make_user(role=User.Role.RECTOR)
    star = make_user()
    make_user()
    arena.award(star, arena.Reason.MANUAL, 700)
    data = api(rector).get("/api/v1/insights/dashboard/").data
    assert data["totals"]["students"] == 2
    assert data["top_students"][0]["id"] == star.id
    assert data["rising_stars"][0]["xp"] == 700
    levels = {row["level"]: row["count"] for row in data["level_distribution"]}
    assert levels[1] == 1 and levels[2] == 1


def test_dean_sees_only_own_faculty(api, make_user, faculty):
    other = Faculty.objects.create(name="Energetika", short_name="EN")
    dean = make_user(role=User.Role.DEAN)
    make_user()
    make_user(faculty=other)
    data = api(dean).get("/api/v1/insights/dashboard/").data
    assert data["totals"]["students"] == 1
    assert [row["faculty_id"] for row in data["by_faculty"]] == [faculty.id]
