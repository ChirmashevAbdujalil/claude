from io import StringIO

from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.test import Client

from apps.accounts.models import User
from apps.surveys.models import IssuedAccount, Response, Survey


def run(*args):
    out = StringIO()
    call_command("prepare_production", *args, stdout=out)
    return out.getvalue()


def test_prepare_production_removes_demo_data(make_user):
    call_command("seed", "--demo", verbosity=0)
    admin = make_user(role=User.Role.RECTOR, username="haqiqiy_rektor")
    demo_count = User.objects.filter(username__startswith="demo_").count()
    assert demo_count >= 3 and Survey.objects.filter(title__endswith="(demo)").exists()

    report = run()
    assert "Hech narsa o'zgarmadi" in report and "demo_rector" in report
    assert User.objects.filter(username__startswith="demo_").count() == demo_count  # hisobot hech narsani o'chirmaydi

    Session.objects.create(session_key="x" * 32, session_data="", expire_date="2100-01-01T00:00:00Z")
    report = run("--apply")
    demo = User.objects.filter(username__startswith="demo_")
    assert demo.count() == demo_count and not demo.filter(is_active=True).exists()  # bloklangan, kontenti joyida
    assert not any(u.has_usable_password() for u in demo)
    assert not Client().login(username="demo_rector", password="demo12345")
    assert not Survey.objects.filter(title__endswith="(demo)").exists() and not Session.objects.exists()
    assert "haqiqiy_rektor" in report and User.objects.filter(pk=admin.pk).exists()


def test_clear_responses_removes_test_answers_and_accounts(make_user):
    call_command("seed", "--demo", verbosity=0)
    assert Response.objects.exists() and IssuedAccount.objects.exists()
    report = run("--apply", "--clear-responses")
    assert not Response.objects.exists() and not IssuedAccount.objects.filter(user__role=User.Role.STUDENT).exists()
    assert "createsuperuser" in report
