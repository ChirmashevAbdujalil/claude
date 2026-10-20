"""«ANDTI TALENT» so'rovnomasining yangi nomi: «Institut talabalari qobiliyatlarini aniqlash so'rovnomasi»."""

from django.db import migrations


def rename(apps, schema_editor):
    from apps.surveys.presets import ANDTI_TALENT_TITLE, OLD_TITLES

    apps.get_model("surveys", "Survey").objects.filter(title__in=OLD_TITLES).update(title=ANDTI_TALENT_TITLE)


class Migration(migrations.Migration):
    dependencies = [("surveys", "0009_question_to_profile")]

    operations = [migrations.RunPython(rename, migrations.RunPython.noop)]
