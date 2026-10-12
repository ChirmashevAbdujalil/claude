import base64
import json
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.billing import click, payme, services
from apps.billing.models import ClickTransaction, Invoice, PaymeTransaction
from apps.tenants.context import default_institution

KEY = "payme-test-key"


@pytest.fixture(autouse=True)
def gateways(settings):
    settings.PAYME_MERCHANT_ID = "merchant123"
    settings.PAYME_KEY = KEY
    settings.PAYME_TEST = True
    settings.CLICK_SERVICE_ID = "111"
    settings.CLICK_MERCHANT_ID = "222"
    settings.CLICK_SECRET_KEY = "click-secret"
    settings.CLICK_MERCHANT_USER_ID = ""


@pytest.fixture
def institution(db):
    institution = default_institution()
    institution.plan, institution.paid_until = "pilot", None
    institution.save()
    return institution


@pytest.fixture
def invoice(institution):
    return services.create_invoice(institution, "standart", 3)


# ---------------------------------------------------------------- xizmatlar


def test_price_and_periods():
    assert services.price("standart", 1) == 1_500_000
    assert services.price("standart", 12) == 15_000_000  # yillik: 2 oy bepul
    with pytest.raises(services.BillingError):
        services.price("pilot", 1)
    with pytest.raises(services.BillingError):
        services.price("standart", 5)


def test_add_months_clamps_day():
    assert services.add_months(timezone.datetime(2026, 1, 31).date(), 1).isoformat() == "2026-02-28"
    assert services.add_months(timezone.datetime(2026, 11, 15).date(), 3).isoformat() == "2027-02-15"


def test_mark_paid_extends_from_current_paid_until(institution, invoice):
    future = timezone.localdate() + timedelta(days=10)
    institution.paid_until = future
    institution.save()
    services.mark_paid(invoice, "click")
    services.mark_paid(invoice, "click")  # takroriy chaqiruv muddatni ikki marta uzaytirmaydi
    institution.refresh_from_db()
    assert institution.plan == "standart"
    assert institution.paid_until == services.add_months(future, 3)


def test_checkout_urls(invoice):
    url = services.payme_checkout_url(invoice, "https://x.uz/back")
    assert url.startswith("https://test.paycom.uz/")
    decoded = base64.b64decode(url.rsplit("/", 1)[1]).decode()
    assert decoded == f"m=merchant123;ac.order_id={invoice.pk};a={invoice.amount * 100};l=uz;c=https://x.uz/back"
    query = parse_qs(urlparse(services.click_checkout_url(invoice)).query)
    assert query["service_id"] == ["111"] and query["merchant_id"] == ["222"]
    assert query["transaction_param"] == [str(invoice.pk)] and query["amount"] == [f"{invoice.amount}.00"]


# ---------------------------------------------------------------- Payme


def rpc(client, method, params, key=KEY, rid=1):
    auth = "Basic " + base64.b64encode(f"Paycom:{key}".encode()).decode()
    body = json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
    return client.post("/billing/payme/", body, content_type="application/json", HTTP_AUTHORIZATION=auth).json()


def account(invoice):
    return {"account": {"order_id": str(invoice.pk)}, "amount": invoice.amount_tiyin}


def test_payme_auth_and_protocol_errors(client, invoice):
    assert rpc(client, "CheckPerformTransaction", account(invoice), key="wrong")["error"]["code"] == -32504
    assert client.get("/billing/payme/").json()["error"]["code"] == -32300
    bad = client.post("/billing/payme/", "{oops", content_type="application/json").json()
    assert bad["error"]["code"] == -32700
    assert rpc(client, "Nomalum", {})["error"]["code"] == -32601


def test_payme_check_perform(client, invoice):
    assert rpc(client, "CheckPerformTransaction", account(invoice))["result"] == {"allow": True}
    wrong = {**account(invoice), "amount": 100}
    assert rpc(client, "CheckPerformTransaction", wrong)["error"]["code"] == -31001
    missing = {"account": {"order_id": "999999"}, "amount": 100}
    assert rpc(client, "CheckPerformTransaction", missing)["error"]["code"] == -31050


def test_payme_full_flow_and_refund(client, institution, invoice):
    params = {**account(invoice), "id": "pm-1", "time": payme.now_ms()}
    created = rpc(client, "CreateTransaction", params)["result"]
    assert created["state"] == 1
    assert rpc(client, "CreateTransaction", params)["result"]["transaction"] == created["transaction"]
    # Shu hisob uchun boshqa Payme tranzaksiyasi ochib bo'lmaydi
    other = rpc(client, "CreateTransaction", {**params, "id": "pm-2"})
    assert other["error"]["code"] == -31052

    performed = rpc(client, "PerformTransaction", {"id": "pm-1"})["result"]
    assert performed["state"] == 2 and performed["perform_time"] > 0
    assert rpc(client, "PerformTransaction", {"id": "pm-1"})["result"]["state"] == 2  # idempotent
    invoice.refresh_from_db()
    institution.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID and invoice.provider == "payme"
    assert institution.plan == "standart"
    assert institution.paid_until == services.add_months(timezone.localdate(), 3)

    checked = rpc(client, "CheckTransaction", {"id": "pm-1"})["result"]
    assert checked["state"] == 2 and checked["reason"] is None

    cancelled = rpc(client, "CancelTransaction", {"id": "pm-1", "reason": 5})["result"]
    assert cancelled["state"] == -2
    invoice.refresh_from_db()
    institution.refresh_from_db()
    assert invoice.status == Invoice.Status.REFUNDED
    assert institution.plan == "pilot" and institution.paid_until is None

    statement = rpc(client, "GetStatement", {"from": 0, "to": payme.now_ms() + 1000})["result"]["transactions"]
    assert [row["id"] for row in statement] == ["pm-1"]
    assert statement[0]["account"] == {"order_id": str(invoice.pk)}
    assert rpc(client, "CheckTransaction", {"id": "yoq"})["error"]["code"] == -31003


def test_payme_cancel_before_perform_closes_invoice(client, invoice):
    rpc(client, "CreateTransaction", {**account(invoice), "id": "pm-3", "time": payme.now_ms()})
    assert rpc(client, "CancelTransaction", {"id": "pm-3", "reason": 3})["result"]["state"] == -1
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.CANCELLED
    assert rpc(client, "PerformTransaction", {"id": "pm-3"})["error"]["code"] == -31008


def test_payme_timeout(client, invoice):
    rpc(client, "CreateTransaction", {**account(invoice), "id": "pm-4", "time": payme.now_ms()})
    PaymeTransaction.objects.filter(payme_id="pm-4").update(create_time=payme.now_ms() - payme.TIMEOUT_MS - 1)
    assert rpc(client, "PerformTransaction", {"id": "pm-4"})["error"]["code"] == -31008
    tx = PaymeTransaction.objects.get(payme_id="pm-4")
    assert tx.state == -1 and tx.reason == payme.REASON_TIMEOUT


# ---------------------------------------------------------------- Click


def click_data(invoice, action, trans_id=7001, prepare_id="", **overrides):
    data = {
        "click_trans_id": str(trans_id),
        "service_id": "111",
        "click_paydoc_id": "555",
        "merchant_trans_id": str(invoice.pk),
        "amount": f"{invoice.amount}.00",
        "action": action,
        "error": "0",
        "error_note": "Success",
        "sign_time": "2026-10-12 10:00:00",
        **overrides,
    }
    if action == "1":
        data["merchant_prepare_id"] = str(prepare_id)
    data["sign_string"] = click.sign(data, str(prepare_id) if action == "1" else "")
    return data


def test_click_prepare_and_complete(client, institution, invoice):
    prepared = client.post("/billing/click/prepare/", click_data(invoice, "0")).json()
    assert prepared["error"] == 0
    prepare_id = prepared["merchant_prepare_id"]
    completed = client.post("/billing/click/complete/", click_data(invoice, "1", prepare_id=prepare_id)).json()
    assert completed["error"] == 0 and completed["merchant_confirm_id"] == prepare_id
    invoice.refresh_from_db()
    institution.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID and invoice.provider == "click"
    assert institution.plan == "standart"
    # Qayta yuborilsa: "allaqachon to'langan"
    again = client.post("/billing/click/complete/", click_data(invoice, "1", prepare_id=prepare_id)).json()
    assert again["error"] == click.ALREADY_PAID
    assert client.post("/billing/click/prepare/", click_data(invoice, "0", trans_id=7002)).json()["error"] == -4


def test_click_rejects_bad_requests(client, invoice):
    bad_sign = {**click_data(invoice, "0"), "sign_string": "0" * 32}
    assert client.post("/billing/click/prepare/", bad_sign).json()["error"] == click.SIGN_FAILED
    wrong_amount = click_data(invoice, "0", amount="1000.00")
    assert client.post("/billing/click/prepare/", wrong_amount).json()["error"] == click.BAD_AMOUNT
    unknown = click_data(invoice, "0", merchant_trans_id="999999")
    assert client.post("/billing/click/prepare/", unknown).json()["error"] == click.NOT_FOUND
    assert client.post("/billing/click/complete/", click_data(invoice, "0")).json()["error"] == click.BAD_ACTION
    no_prepare = click_data(invoice, "1", prepare_id="12345")
    assert client.post("/billing/click/complete/", no_prepare).json()["error"] == click.TX_NOT_FOUND


def test_click_failed_payment_cancels_transaction(client, institution, invoice):
    prepare_id = client.post("/billing/click/prepare/", click_data(invoice, "0")).json()["merchant_prepare_id"]
    failed = click_data(invoice, "1", prepare_id=prepare_id, error="-5017", error_note="Insufficient funds")
    assert client.post("/billing/click/complete/", failed).json()["error"] == click.CANCELLED
    assert ClickTransaction.objects.get(pk=prepare_id).state == ClickTransaction.State.CANCELLED
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PENDING


# ---------------------------------------------------------------- sahifalar va buyruq


def test_invoice_pages_for_rector(client, make_user, institution):
    rector = make_user(role=User.Role.RECTOR)
    client.force_login(rector)
    response = client.post(reverse("billing:invoice-create"), {"plan": "premium", "months": "12"})
    invoice = Invoice.objects.get()
    assert response.url == reverse("billing:invoice", args=[invoice.pk])
    assert invoice.amount == 35_000_000 and invoice.created_by == rector
    page = client.get(response.url).content.decode()
    assert "test.paycom.uz" in page and "my.click.uz" in page
    client.post(reverse("billing:invoice-create"), {"plan": "pilot", "months": "1"})
    assert Invoice.objects.count() == 1


def test_invoice_pages_forbidden_for_student(client, student, invoice):
    client.force_login(student)
    assert client.post(reverse("billing:invoice-create"), {"plan": "standart", "months": "1"}).status_code == 403
    assert client.get(reverse("billing:invoice", args=[invoice.pk])).status_code == 403


def test_check_subscriptions_command(institution):
    institution.paid_until = timezone.localdate() - timedelta(days=5)
    institution.is_active = True
    institution.save()
    call_command("check_subscriptions", "--dry-run", verbosity=0)
    institution.refresh_from_db()
    assert institution.is_active
    call_command("check_subscriptions", verbosity=0)
    institution.refresh_from_db()
    assert not institution.is_active
