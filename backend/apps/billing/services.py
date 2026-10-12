"""To'lov hisoblari va OTM obunasini uzaytirish."""

import base64
import calendar
from datetime import date
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.tenants import plans
from apps.tenants.models import Institution

from .models import Invoice

# Necha oyga to'lanadi -> necha oy narxi olinadi (yillik to'lovda 2 oy bepul)
PERIODS = {1: 1, 3: 3, 6: 6, 12: 10}


class BillingError(Exception):
    pass


def add_months(start: date, months: int) -> date:
    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def price(plan: str, months: int) -> int:
    if plan not in plans.PLANS or not plans.PLANS[plan]["price"]:
        raise BillingError("Bu tarif uchun to'lov talab qilinmaydi")
    if months not in PERIODS:
        raise BillingError("Muddat noto'g'ri tanlangan")
    return plans.PLANS[plan]["price"] * PERIODS[months]


def create_invoice(institution: Institution, plan: str, months: int, user=None) -> Invoice:
    return Invoice.objects.create(
        institution=institution, plan=plan, months=months, amount=price(plan, months), created_by=user
    )


@transaction.atomic
def mark_paid(invoice: Invoice, provider: str) -> Invoice:
    """To'lov tasdiqlandi: OTM tarifini o'rnatadi va muddatini uzaytiradi. Takroriy chaqiruv xavfsiz."""
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status == Invoice.Status.PAID:
        return invoice
    if invoice.status != Invoice.Status.PENDING:
        raise BillingError("Hisob bekor qilingan")
    institution = Institution.objects.select_for_update().get(pk=invoice.institution_id)
    today = timezone.localdate()
    start = institution.paid_until if institution.paid_until and institution.paid_until > today else today
    invoice.previous_plan = institution.plan
    invoice.previous_paid_until = institution.paid_until
    invoice.new_paid_until = add_months(start, invoice.months)
    institution.plan = invoice.plan
    institution.paid_until = invoice.new_paid_until
    institution.is_active = True
    institution.save(update_fields=["plan", "paid_until", "is_active"])
    invoice.status = Invoice.Status.PAID
    invoice.provider = provider
    invoice.paid_at = timezone.now()
    invoice.save()
    return invoice


@transaction.atomic
def refund(invoice: Invoice) -> Invoice:
    """To'lov qaytarildi: agar keyin boshqa to'lov bo'lmagan bo'lsa, OTMning oldingi holatini tiklaydi."""
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status != Invoice.Status.PAID:
        return invoice
    institution = Institution.objects.select_for_update().get(pk=invoice.institution_id)
    if institution.paid_until == invoice.new_paid_until:
        institution.plan = invoice.previous_plan or institution.plan
        institution.paid_until = invoice.previous_paid_until
        institution.save(update_fields=["plan", "paid_until"])
    invoice.status = Invoice.Status.REFUNDED
    invoice.save(update_fields=["status"])
    return invoice


def cancel(invoice: Invoice) -> None:
    Invoice.objects.filter(pk=invoice.pk, status=Invoice.Status.PENDING).update(status=Invoice.Status.CANCELLED)


# ---------------------------------------------------------------- to'lov sahifasiga havolalar


def payme_enabled() -> bool:
    return bool(settings.PAYME_MERCHANT_ID and settings.PAYME_KEY)


def click_enabled() -> bool:
    return bool(settings.CLICK_SERVICE_ID and settings.CLICK_MERCHANT_ID and settings.CLICK_SECRET_KEY)


def payme_checkout_url(invoice: Invoice, return_url: str = "") -> str:
    """Payme to'lov sahifasi: parametrlar base64 bilan kodlanadi."""
    params = [
        f"m={settings.PAYME_MERCHANT_ID}",
        f"ac.{settings.PAYME_ACCOUNT_FIELD}={invoice.pk}",
        f"a={invoice.amount_tiyin}",
        "l=uz",
    ]
    if return_url:
        params.append(f"c={return_url}")
    encoded = base64.b64encode(";".join(params).encode()).decode()
    base = "https://test.paycom.uz" if settings.PAYME_TEST else "https://checkout.paycom.uz"
    return f"{base}/{encoded}"


def click_checkout_url(invoice: Invoice, return_url: str = "") -> str:
    query = {
        "service_id": settings.CLICK_SERVICE_ID,
        "merchant_id": settings.CLICK_MERCHANT_ID,
        "amount": f"{invoice.amount}.00",
        "transaction_param": invoice.pk,
    }
    if settings.CLICK_MERCHANT_USER_ID:
        query["merchant_user_id"] = settings.CLICK_MERCHANT_USER_ID
    if return_url:
        query["return_url"] = return_url
    return "https://my.click.uz/services/pay?" + urlencode(query)
