"""ANDTI rahbariyati bergan tyutorlar ro'yxatini asosiy OTM fakultetlariga biriktiradi."""

from django.conf import settings
from django.db import migrations


def add_tutors(apps, schema_editor):
    from apps.accounts.tutors import ANDTI_TUTORS

    Institution = apps.get_model("tenants", "Institution")
    Faculty = apps.get_model("accounts", "Faculty")
    Tutor = apps.get_model("accounts", "Tutor")
    institution = Institution.objects.filter(slug=settings.DEFAULT_INSTITUTION_SLUG).first()
    if institution is None:
        return  # yangi baza: tyutorlar seed buyrug'i bilan qo'shiladi
    for short, names in ANDTI_TUTORS.items():
        faculty = Faculty.objects.filter(institution=institution, short_name=short).first()
        if faculty is None:
            continue
        for name in names:
            Tutor.objects.get_or_create(faculty=faculty, full_name=name, defaults={"institution": institution})


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_tutor"),
        ("tenants", "0002_default_institution"),
    ]

    operations = [migrations.RunPython(add_tutors, migrations.RunPython.noop)]
