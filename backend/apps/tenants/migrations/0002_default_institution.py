from django.conf import settings
from django.db import migrations


def create_default(apps, schema_editor):
    Institution = apps.get_model("tenants", "Institution")
    Institution.objects.get_or_create(
        slug=settings.DEFAULT_INSTITUTION_SLUG,
        defaults={
            "name": settings.DEFAULT_INSTITUTION_NAME,
            "short_name": settings.DEFAULT_INSTITUTION_SHORT,
            "tagline": "Ta'lim · Fan · Ishlab chiqarish",
            "plan": "premium",
        },
    )


class Migration(migrations.Migration):
    dependencies = [("tenants", "0001_initial")]

    operations = [migrations.RunPython(create_default, migrations.RunPython.noop)]
