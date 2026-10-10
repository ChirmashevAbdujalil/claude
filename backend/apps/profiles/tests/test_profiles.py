from datetime import date

from apps.profiles.models import Achievement, Skill, UserSkill


def add_skill(user, name="Python", level=3):
    return UserSkill.objects.create(user=user, skill=Skill.objects.get(name=name), level=level)


def test_add_skill_and_map(api, student):
    client = api(student)
    python = Skill.objects.get(name="Python")
    response = client.post("/api/v1/me/skills/", {"skill_id": python.id, "level": 4}, format="json")
    assert response.status_code == 201
    duplicate = client.post("/api/v1/me/skills/", {"skill_id": python.id, "level": 2}, format="json")
    assert duplicate.status_code == 400

    skill_map = {row["category"]: row["score"] for row in client.get("/api/v1/me/skills/map/").data}
    assert skill_map["programming"] == 4
    assert skill_map["design"] == 0


def test_teacher_endorses_skill(api, student, teacher):
    user_skill = add_skill(student)
    response = api(teacher).post(f"/api/v1/user-skills/{user_skill.id}/endorse/", {}, format="json")
    assert response.status_code == 201
    student.refresh_from_db()
    # 30 XP tasdiq + 20 XP "Tan olingan" nishoni
    assert student.xp == 50
    again = api(teacher).post(f"/api/v1/user-skills/{user_skill.id}/endorse/", {}, format="json")
    assert again.status_code == 400


def test_student_cannot_endorse(api, student, make_user):
    user_skill = add_skill(make_user())
    assert api(student).post(f"/api/v1/user-skills/{user_skill.id}/endorse/", {}).status_code == 403


def test_achievement_requires_proof(api, student):
    payload = {"kind": "olympiad", "title": "Respublika olimpiadasi", "achieved_on": "2026-04-01"}
    assert api(student).post("/api/v1/achievements/", payload, format="json").status_code == 400
    payload["proof_url"] = "https://example.com/diplom.pdf"
    assert api(student).post("/api/v1/achievements/", payload, format="json").status_code == 201


def test_achievement_review_flow(api, student, teacher):
    achievement = Achievement.objects.create(
        user=student,
        kind=Achievement.Kind.HACKATHON,
        title="AI Hackathon g'olibi",
        achieved_on=date(2026, 5, 1),
        proof_url="https://example.com",
    )
    pending = api(teacher).get("/api/v1/achievements/?scope=all&status=pending").data
    assert pending["count"] == 1

    response = api(teacher).post(f"/api/v1/achievements/{achievement.id}/review/", {"approve": True}, format="json")
    assert response.status_code == 200
    assert response.data["xp_awarded"] == 300
    student.refresh_from_db()
    assert student.badges.filter(badge__code="hackathon").exists()

    again = api(teacher).post(f"/api/v1/achievements/{achievement.id}/review/", {"approve": False}, format="json")
    assert again.status_code == 400


def test_reject_achievement_gives_no_xp(api, student, teacher):
    achievement = Achievement.objects.create(
        user=student,
        kind=Achievement.Kind.OTHER,
        title="Shubhali",
        achieved_on=date(2026, 5, 1),
    )
    api(teacher).post(
        f"/api/v1/achievements/{achievement.id}/review/", {"approve": False, "comment": "Hujjat yo'q"}, format="json"
    )
    student.refresh_from_db()
    assert student.xp == 0


def test_student_sees_only_own_achievements(api, student, make_user):
    other = make_user()
    Achievement.objects.create(user=other, kind="other", title="Begona", achieved_on=date(2026, 1, 1))
    assert api(student).get("/api/v1/achievements/?scope=all").data["count"] == 0


def test_public_portfolio(api, student):
    student.portfolio_slug = "aziz"
    student.save()
    add_skill(student)
    response = api().get("/api/v1/portfolio/aziz/")
    assert response.status_code == 200
    assert response.data["skills"][0]["skill"]["name"] == "Python"

    student.is_public = False
    student.save()
    assert api().get("/api/v1/portfolio/aziz/").status_code == 404
