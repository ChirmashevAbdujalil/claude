from apps.profiles.models import Skill, UserSkill
from apps.projects.models import Project, ProjectMember


def create_project(api, owner, **extra):
    payload = {"title": "Aqlli issiqxona", "description": "IoT asosida issiqxona", **extra}
    response = api(owner).post("/api/v1/projects/", payload, format="json")
    assert response.status_code == 201, response.data
    return Project.objects.get(pk=response.data["id"])


def test_owner_becomes_founder(api, student):
    project = create_project(api, student)
    member = project.members.get()
    assert member.user == student and member.role == "Asoschi" and member.status == ProjectMember.Status.ACTIVE


def test_join_and_approve(api, student, make_user):
    project = create_project(api, student)
    newcomer = make_user()
    join = api(newcomer).post(f"/api/v1/projects/{project.id}/join/", {"role": "Dizayner"}, format="json")
    assert join.status_code == 201
    # Kutilayotgan so'rovni faqat asoschi ko'radi
    assert len(api(newcomer).get(f"/api/v1/projects/{project.id}/").data["members"]) == 1
    assert len(api(student).get(f"/api/v1/projects/{project.id}/").data["members"]) == 2

    forbidden = api(newcomer).post(f"/api/v1/projects/{project.id}/approve/", {"member_id": join.data["id"]})
    assert forbidden.status_code == 400
    approved = api(student).post(f"/api/v1/projects/{project.id}/approve/", {"member_id": join.data["id"]})
    assert approved.data["status"] == "active"
    assert newcomer.badges.filter(badge__code="team-player").exists()


def test_advance_stage_rewards_active_members(api, student, make_user):
    project = create_project(api, student)
    pending = make_user()
    ProjectMember.objects.create(project=project, user=pending)
    response = api(student).post(f"/api/v1/projects/{project.id}/advance/")
    assert response.data["stage"] == "prototype"
    student.refresh_from_db()
    pending.refresh_from_db()
    assert student.xp == 100
    assert pending.xp == 0


def test_last_stage_and_founder_badge(api, student):
    project = create_project(api, student)
    client = api(student)
    for _ in range(3):
        client.post(f"/api/v1/projects/{project.id}/advance/")
    assert student.badges.filter(badge__code="startup-founder").exists()
    assert client.post(f"/api/v1/projects/{project.id}/advance/").status_code == 400


def test_only_owner_can_edit(api, student, make_user):
    project = create_project(api, student)
    response = api(make_user()).patch(f"/api/v1/projects/{project.id}/", {"title": "O'g'irlangan"}, format="json")
    assert response.status_code == 403


def test_teammate_recommendations(api, student, make_user):
    python = Skill.objects.get(name="Python")
    design = Skill.objects.get(name="UI/UX dizayn")
    project = create_project(api, student, skill_ids=[python.id, design.id])
    both, one = make_user(), make_user()
    make_user()  # mos ko'nikmasi yo'q talaba tavsiya qilinmaydi
    UserSkill.objects.create(user=both, skill=python)
    UserSkill.objects.create(user=both, skill=design)
    UserSkill.objects.create(user=one, skill=python)
    UserSkill.objects.create(user=student, skill=python)  # a'zo tavsiya qilinmaydi
    data = api(student).get(f"/api/v1/projects/{project.id}/recommendations/").data
    assert [row["id"] for row in data] == [both.id, one.id]
    assert data[0]["matched"] == 2
