import base64
import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.models import User
from apps.arena import services as arena
from apps.arena.models import PointTransaction
from apps.audit import services
from apps.audit.context import request_scope
from apps.audit.models import AuditLog
from apps.billing import services as billing
from apps.discovery.models import Challenge, Submission
from apps.tenants import services as tenant_services
from apps.tenants.context import activate, default_institution, unscoped


def as_user(user):
    request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.7", HTTP_USER_AGENT="pytest")
    request.user = user
    request.institution = default_institution()
    return request_scope(request)


def entries(**filters):
    with unscoped():
        return list(AuditLog.objects.filter(**filters).order_by("id"))


def test_teacher_review_is_logged_with_old_and_new_values(teacher, student):
    now = timezone.now()
    challenge = Challenge.objects.create(
        title="Ohm qonuni", description="?", created_by=teacher, xp_reward=10, ends_at=now + timedelta(days=1)
    )
    submission = Submission.objects.create(challenge=challenge, user=student, answer="3")
    assert not entries(target_type="discovery.submission")  # talaba yuborgani yozilmaydi

    with as_user(teacher):
        submission.status, submission.score = Submission.Status.ACCEPTED, 90
        submission.save()
    (entry,) = entries(target_type="discovery.submission")
    assert entry.action == AuditLog.Action.UPDATE and entry.actor == teacher and entry.actor_role == "O'qituvchi"
    assert entry.changes["status"] == {"label": "holat", "old": "Tekshirilmoqda", "new": "Qabul qilindi"}
    assert entry.changes["score"]["new"] == "90" and entry.ip == "10.0.0.7"
    assert entry.institution_id == default_institution().pk


def test_student_actions_are_not_logged(student):
    with as_user(student):
        student.first_name = "Yangi"
        student.save()
    assert not entries(target_type="accounts.user")


def test_manual_xp_is_logged_but_regular_awards_are_not(make_user, student):
    rector = make_user(role=User.Role.RECTOR)
    with as_user(rector):
        arena.award(student, PointTransaction.Reason.MANUAL, 500, note="Olimpiada")
        arena.award(student, PointTransaction.Reason.EVENT, 20)
    (entry,) = entries(target_type="arena.pointtransaction")
    assert entry.action == AuditLog.Action.CREATE and entry.changes["xp"]["new"] == "500"


def test_password_change_hides_values(client, make_user):
    owner = make_user(username="owner", is_superuser=True, is_staff=True)
    teacher = make_user(role=User.Role.TEACHER)
    client.force_login(owner)
    client.post(f"/platform/users/{teacher.pk}/reset-password/")
    (entry,) = entries(action=AuditLog.Action.PASSWORD)
    assert entry.actor_repr == "owner" and entry.actor_role == "Platforma egasi"
    assert entry.changes == {"password": {"label": "parol", "old": "••••••", "new": "••••••"}}


def test_logins_and_failed_attempts(client, make_user, student):
    rector = make_user(role=User.Role.RECTOR, username="rektor")
    client.post("/login/", {"username": "rektor", "password": "notogri-parol"})
    client.post("/login/", {"username": "rektor", "password": "pass12345"})
    client.post("/logout/")
    client.post("/login/", {"username": student.username, "password": "pass12345"})
    actions = [(e.action, e.actor_repr) for e in entries(target_type="")]
    assert actions == [("login_failed", "rektor"), ("login", "rektor"), ("logout", "rektor")]
    assert "notogri-parol" not in json.dumps([e.changes for e in entries()])
    assert rector.pk


def test_payme_payment_is_logged_as_system(client, settings):
    settings.PAYME_KEY = "k"
    institution = default_institution()
    invoice = billing.create_invoice(institution, "standart", 1)
    auth = "Basic " + base64.b64encode(b"Paycom:k").decode()

    def rpc(method, params):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        return client.post("/billing/payme/", body, content_type="application/json", HTTP_AUTHORIZATION=auth)

    params = {"id": "p1", "time": 1, "amount": invoice.amount_tiyin, "account": {"order_id": str(invoice.pk)}}
    rpc("CreateTransaction", params)
    rpc("PerformTransaction", {"id": "p1"})
    logged = {(e.target_type, e.actor_repr) for e in entries(action=AuditLog.Action.UPDATE)}
    assert ("billing.invoice", "Payme") in logged and ("tenants.institution", "Payme") in logged
    plan = next(e for e in entries(target_type="tenants.institution")).changes["plan"]
    assert plan["new"] == "Standart"


def test_subscription_command_is_logged():
    institution = default_institution()
    institution.paid_until = timezone.localdate() - timedelta(days=10)
    institution.save()
    call_command("check_subscriptions", verbosity=0)
    (entry,) = entries(target_type="tenants.institution")
    assert entry.actor_repr == "Tizim: obuna nazorati" and entry.changes["is_active"]["new"] == "yo'q"


def test_journal_is_append_only_and_tamper_evident(make_user, faculty):
    rector = make_user(role=User.Role.RECTOR)
    with as_user(rector):
        for name in ("A", "B", "C"):
            faculty.name = name
            faculty.save()
    institution_id = default_institution().pk
    assert services.verify(institution_id) == (3, None)
    first = entries()[0]
    with pytest.raises(ValueError):
        first.save()
    with pytest.raises(ValueError):
        first.delete()
    # Bazada qo'lda o'zgartirish zanjirni uzadi
    AuditLog._base_manager.filter(pk=first.pk).update(actor_repr="boshqa")
    assert services.verify(institution_id) == (0, first.pk)
    with pytest.raises(Exception, match="buzilgan"):
        call_command("verify_audit_log", verbosity=0)


def test_journal_page_permissions_filters_and_csv(client, make_user, student):
    rector = make_user(role=User.Role.RECTOR)
    blocked = make_user(username="bloklangan_talaba", first_name="Bloklangan", last_name="Talabayev")
    with as_user(rector):
        blocked.is_active = False
        blocked.save()
    client.force_login(student)
    assert client.get("/settings/otm/jurnal/").status_code == 403

    client.force_login(rector)
    page = client.get("/settings/otm/jurnal/?verify=1").content.decode()
    name = str(blocked)
    assert "Jurnal butun" in page and name in page
    filtered = client.get("/settings/otm/jurnal/?action=delete").content.decode()
    assert name not in filtered
    csv = client.get("/settings/otm/jurnal/?format=csv")
    assert csv["Content-Type"].startswith("text/csv") and name in csv.content.decode()


def test_institutions_see_only_their_own_journal(client, make_user, faculty):
    tatu, tatu_admin, _ = tenant_services.create_institution(name="TATU", short_name="TATU", slug="tatu")
    rector = make_user(role=User.Role.RECTOR)
    with as_user(rector):
        faculty.name = "ANDTI maxfiy o'zgarishi"
        faculty.save()
    with activate(tatu):
        assert not AuditLog.objects.filter(target_type="accounts.faculty").exists()
    client.defaults["HTTP_HOST"] = "tatu.localhost"
    client.force_login(tatu_admin)
    page = client.get("/settings/otm/jurnal/").content.decode()
    assert "ANDTI maxfiy" not in page
