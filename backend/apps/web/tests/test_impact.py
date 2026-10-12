from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.arena.models import PointTransaction
from apps.tenants.context import default_institution
from apps.web import impact


@pytest.fixture(autouse=True)
def fresh_cache():
    cache.clear()
    yield
    cache.clear()


def tx(user, days_ago, reason=PointTransaction.Reason.CHALLENGE, xp=10):
    row = PointTransaction.objects.create(user=user, reason=reason, xp=xp)
    PointTransaction.objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(days=days_ago))


def test_impact_numbers(make_user):
    now = timezone.now()
    old, returning, fresh = make_user(first_name="Yashirin"), make_user(), make_user()
    type(old).objects.filter(pk=old.pk).update(date_joined=now - timedelta(days=40))
    tx(old, 10)  # o'tgan hafta faol, shu hafta yo'q
    tx(returning, 10)
    tx(returning, 2, PointTransaction.Reason.EVENT, xp=30)
    tx(fresh, 1, PointTransaction.Reason.MANUAL, xp=500)  # qo'lda berilgan ball faollik emas

    data = impact.compute()
    assert data["students"] == 3
    assert data["active_week"] == 1  # faqat "returning"
    assert data["retention"] == 50  # o'tgan haftadagi 2 faoldan 1 tasi qaytdi
    assert [row["reason"] for row in data["mix"]] == ["event", "challenge"]
    assert sum(row["share"] for row in data["mix"]) == 100
    weekly = data["weekly"]
    assert len(weekly) == impact.WEEKS and weekly[-1]["total"] == 3
    # 40 kun oldin qo'shilgan talaba: 12 hafta oldin 0, keyin 1, shu hafta yana 2 nafar qo'shildi
    assert weekly[0]["total"] == 0 and any(row["total"] == 1 for row in weekly) and weekly[-1]["new"] == 2
    assert data["faculties"][0]["students"] == 3


def test_impact_page_is_public_and_anonymous(client, make_user):
    student = make_user(first_name="Maxfiy", last_name="Familiya")
    tx(student, 0)
    page = client.get("/natijalar/").content.decode()
    assert "Natijalar" in page and "impact-weekly" in page
    assert '<svg class="qr-svg"' in page  # QR internetsiz, serverda chiziladi
    assert "Maxfiy" not in page and "Familiya" not in page and student.username not in page
    assert '"partial": true' in page  # joriy hafta alohida belgilanadi


def test_impact_is_cached_per_institution(make_user):
    institution = default_institution()
    make_user()
    assert impact.impact(institution)["students"] == 1
    make_user()
    assert impact.impact(institution)["students"] == 1  # 5 daqiqa keshdan
    cache.clear()
    assert impact.impact(institution)["students"] == 2
