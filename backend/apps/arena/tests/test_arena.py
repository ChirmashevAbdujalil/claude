from datetime import date, timedelta

import pytest

from apps.arena import services
from apps.arena.levels import level_for_xp
from apps.arena.models import PointTransaction, Streak
from apps.arena.services import Reason


def test_level_for_xp():
    assert level_for_xp(0)["number"] == 1
    assert level_for_xp(499)["number"] == 1
    assert level_for_xp(500)["name"] == "Izlanuvchi"
    assert level_for_xp(1250)["progress"] == 0.5
    top = level_for_xp(50000)
    assert top["number"] == 5 and top["next_level_xp"] is None and top["progress"] == 1.0


def test_award_updates_balance_and_ledger(student):
    tx = services.award(student, Reason.CHALLENGE, 100, ref="submission:1")
    student.refresh_from_db()
    assert student.xp == 100
    assert student.coins == 20
    assert tx.xp == 100
    assert PointTransaction.objects.filter(user=student).count() == 1


def test_award_is_idempotent_per_source(student):
    services.award(student, Reason.CHALLENGE, 50, ref="submission:7")
    assert services.award(student, Reason.CHALLENGE, 50, ref="submission:7") is None
    student.refresh_from_db()
    assert student.xp == 50


def test_level_up_grants_badge(student):
    services.award(student, Reason.ACHIEVEMENT, 600, ref="achievement:1")
    assert student.badges.filter(badge__code="level-2").exists()


def test_daily_cap_clips_capped_reasons(student, settings):
    settings.ARENA_DAILY_XP_CAP = 100
    services.award(student, Reason.EVENT, 80, ref="event:1")
    tx = services.award(student, Reason.EVENT, 80, ref="event:2")
    assert tx.xp == 20
    assert services.award(student, Reason.EVENT, 10, ref="event:3") is None
    # Tasdiqlangan yutuqlar limitga kirmaydi
    assert services.award(student, Reason.ACHIEVEMENT, 300, ref="achievement:9").xp == 300
    student.refresh_from_db()
    assert student.xp == 400


def test_spend_coins(student):
    services.award(student, Reason.MANUAL, 500)
    services.spend_coins(student, 60)
    student.refresh_from_db()
    assert student.coins == 40
    with pytest.raises(services.InsufficientCoins):
        services.spend_coins(student, 41)


def test_streak_continues_and_resets(student):
    day = date(2026, 3, 10)
    services.touch_streak(student, day)
    services.touch_streak(student, day)  # bir kunda ikki marta hisoblanmaydi
    services.touch_streak(student, day + timedelta(days=1))
    streak = Streak.objects.get(user=student)
    assert streak.current == 2

    services.touch_streak(student, day + timedelta(days=5))
    streak.refresh_from_db()
    assert streak.current == 1
    assert streak.longest == 2


def test_seven_day_streak_bonus(student):
    start = date(2026, 3, 1)
    for offset in range(7):
        services.touch_streak(student, start + timedelta(days=offset))
    assert PointTransaction.objects.filter(user=student, reason=Reason.STREAK).count() == 1
    assert student.badges.filter(badge__code="streak-7").exists()


def test_semester_start():
    assert services.semester_start(date(2026, 10, 10)) == date(2026, 9, 1)
    assert services.semester_start(date(2026, 3, 5)) == date(2026, 2, 1)
    assert services.semester_start(date(2026, 1, 15)) == date(2025, 9, 1)


def test_leaderboard(api, make_user):
    users = [make_user() for _ in range(3)]
    for user, xp in zip(users, [300, 900, 100], strict=True):
        services.award(user, Reason.MANUAL, xp)
    response = api(users[2]).get("/api/v1/arena/leaderboard/")
    assert response.status_code == 200
    ranking = [row["user_id"] for row in response.data["results"]]
    assert ranking == [users[1].id, users[0].id, users[2].id]
    assert response.data["me"]["rank"] == 3


def test_leaderboard_weekly_counts_recent_only(api, make_user):
    active, idle = make_user(), make_user()
    services.award(active, Reason.MANUAL, 50)
    response = api(idle).get("/api/v1/arena/leaderboard/?period=week")
    assert [row["user_id"] for row in response.data["results"]] == [active.id]


def test_faculty_league(api, student):
    services.award(student, Reason.MANUAL, 200)
    response = api(student).get("/api/v1/arena/league/")
    assert response.data["results"][0]["xp"] == 200


def test_arena_summary(api, student):
    services.award(student, Reason.MANUAL, 600)
    data = api(student).get("/api/v1/arena/me/").data
    assert data["level"]["number"] == 2
    assert any(b["code"] == "level-2" for b in data["badges"])
