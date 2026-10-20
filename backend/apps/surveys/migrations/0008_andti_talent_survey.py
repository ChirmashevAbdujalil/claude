"""«ANDTI TALENT» 1-bosqich so'rovnomasini asosiy OTMda qoralama sifatida yaratadi (rahbariyat tahrirlab e'lon qiladi)."""

from django.conf import settings
from django.db import migrations


def add_survey(apps, schema_editor):
    from apps.surveys.presets import ANDTI_TALENT, ANDTI_TALENT_TITLE

    Institution = apps.get_model("tenants", "Institution")
    Survey = apps.get_model("surveys", "Survey")
    Question = apps.get_model("surveys", "Question")
    User = apps.get_model("accounts", "User")
    institution = Institution.objects.filter(slug=settings.DEFAULT_INSTITUTION_SLUG).first()
    if institution is None or Survey.objects.filter(institution=institution, title=ANDTI_TALENT_TITLE).exists():
        return  # yangi baza: so'rovnoma «Yangi so'rovnoma» oynasidagi shablondan bir bosishda yaratiladi
    author = (
        User.objects.filter(institution=institution, role="rector", is_active=True).order_by("id").first()
        or User.objects.filter(institution=institution, role="admin", is_active=True).order_by("id").first()
    )
    if author is None:
        return  # rahbariyati hali yo'q baza: shablondan yaratiladi
    survey = Survey.objects.create(institution=institution, created_by=author, status="draft", **ANDTI_TALENT["survey"])
    for order, item in enumerate(ANDTI_TALENT["questions"]):
        Question.objects.create(survey=survey, order=order, **item)


class Migration(migrations.Migration):
    dependencies = [
        ("surveys", "0007_response_files"),
        ("tenants", "0002_default_institution"),
        ("accounts", "0006_andti_tutors"),
    ]

    operations = [migrations.RunPython(add_survey, migrations.RunPython.noop)]
