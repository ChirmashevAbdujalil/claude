from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import Faculty, User
from apps.discovery.models import Challenge


def test_real_faculties_created():
    names = set(Faculty.objects.values_list("name", flat=True))
    assert {
        "Iqtisodiyot va boshqaruv fakulteti",
        "Intellektual boshqaruv va kompyuter tizimlari fakulteti",
        "Qurilish muhandisligi va elektroenergetika fakulteti",
        "Mexanika va kimyo muhandisligi fakulteti",
        "Avtomobilsozlik va transport fakulteti",
    } <= names


def test_legacy_demo_faculties_are_migrated(db):
    Faculty.objects.all().delete()
    renamed = Faculty.objects.create(name="Kompyuter injiniringi (demo)", short_name="KI")
    merged_target = Faculty.objects.create(name="Mexanika va kimyo muhandisligi fakulteti", short_name="MKM")
    merged = Faculty.objects.create(name="Mashinasozlik (demo)", short_name="MSH")
    student = User.objects.create_user(username="eski", password="x", faculty=merged)
    teacher = User.objects.create_user(username="ustoz", password="x", role=User.Role.TEACHER)
    challenge = Challenge.objects.create(
        title="x",
        description="x",
        faculty=merged,
        created_by=teacher,
        ends_at=timezone.now() + timedelta(days=1),
    )

    call_command("seed", verbosity=0)
    call_command("seed", verbosity=0)  # qayta ishga tushirish xavfsiz

    renamed.refresh_from_db()
    assert renamed.name == "Intellektual boshqaruv va kompyuter tizimlari fakulteti"
    assert not Faculty.objects.filter(name__endswith="(demo)").exists()
    student.refresh_from_db()
    challenge.refresh_from_db()
    assert student.faculty == merged_target and challenge.faculty == merged_target
    assert Faculty.objects.count() == 5
