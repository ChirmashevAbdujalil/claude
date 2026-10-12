"""Click SHOP API: Prepare (action=0) va Complete (action=1).

Click form-urlencoded POST yuboradi, imzo MD5 bilan tekshiriladi. Summa so'mda (tiyinsiz).
Hujjat: https://docs.click.uz/click-api-request/
"""

import hashlib
import hmac
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction

from . import services
from .models import ClickTransaction, Invoice

SUCCESS, SIGN_FAILED, BAD_AMOUNT, BAD_ACTION, ALREADY_PAID = 0, -1, -2, -3, -4
NOT_FOUND, TX_NOT_FOUND, UPDATE_FAILED, BAD_REQUEST, CANCELLED = -5, -6, -7, -8, -9
NOTES = {
    SUCCESS: "Success",
    SIGN_FAILED: "SIGN CHECK FAILED!",
    BAD_AMOUNT: "Incorrect parameter amount",
    BAD_ACTION: "Action not found",
    ALREADY_PAID: "Already paid",
    NOT_FOUND: "User does not exist",
    TX_NOT_FOUND: "Transaction does not exist",
    UPDATE_FAILED: "Failed to update user",
    BAD_REQUEST: "Error in request from click",
    CANCELLED: "Transaction cancelled",
}
REQUIRED = ["click_trans_id", "service_id", "merchant_trans_id", "amount", "action", "sign_time", "sign_string"]


def sign(data, prepare_id: str = "") -> str:
    raw = (
        f"{data['click_trans_id']}{data['service_id']}{settings.CLICK_SECRET_KEY}{data['merchant_trans_id']}"
        f"{prepare_id}{data['amount']}{data['action']}{data['sign_time']}"
    )
    return hashlib.md5(raw.encode()).hexdigest()  # noqa: S324 - Click protokoli MD5 talab qiladi


def _answer(data, code: int, **extra) -> dict:
    return {
        "click_trans_id": data.get("click_trans_id"),
        "merchant_trans_id": data.get("merchant_trans_id"),
        "error": code,
        "error_note": NOTES[code],
        **extra,
    }


def _validate(data, action: str, prepare_id: str = ""):
    """(invoice, amount) yoki xato kodi."""
    if any(not data.get(key) and data.get(key) != "0" for key in REQUIRED):
        return None, BAD_REQUEST
    if data["action"] != action:
        return None, BAD_ACTION
    if str(data["service_id"]) != str(settings.CLICK_SERVICE_ID):
        return None, BAD_REQUEST
    if not hmac.compare_digest(sign(data, prepare_id), str(data["sign_string"])):
        return None, SIGN_FAILED
    invoice = (
        Invoice.objects.filter(pk=data["merchant_trans_id"]).first()
        if str(data["merchant_trans_id"]).isdigit()
        else None
    )
    if invoice is None:
        return None, NOT_FOUND
    try:
        amount = Decimal(str(data["amount"]))
    except InvalidOperation:
        return None, BAD_AMOUNT
    if amount != Decimal(invoice.amount):
        return None, BAD_AMOUNT
    return (invoice, amount), SUCCESS


@transaction.atomic
def prepare(data) -> dict:
    found, code = _validate(data, "0")
    if code != SUCCESS:
        return _answer(data, code)
    invoice, amount = found
    if invoice.status == Invoice.Status.PAID:
        return _answer(data, ALREADY_PAID)
    if invoice.status != Invoice.Status.PENDING:
        return _answer(data, CANCELLED)
    tx, _ = ClickTransaction.objects.get_or_create(
        click_trans_id=int(data["click_trans_id"]),
        defaults={"invoice": invoice, "amount": amount, "click_paydoc_id": data.get("click_paydoc_id") or None},
    )
    if tx.invoice_id != invoice.pk:
        return _answer(data, BAD_REQUEST)
    return _answer(data, SUCCESS, merchant_prepare_id=tx.pk)


@transaction.atomic
def complete(data) -> dict:
    prepare_id = str(data.get("merchant_prepare_id") or "")
    found, code = _validate(data, "1", prepare_id)
    if code != SUCCESS:
        return _answer(data, code)
    invoice, _ = found
    tx = (
        ClickTransaction.objects.select_for_update()
        .filter(pk=prepare_id if prepare_id.isdigit() else 0, click_trans_id=int(data["click_trans_id"]))
        .first()
    )
    if tx is None or tx.invoice_id != invoice.pk:
        return _answer(data, TX_NOT_FOUND)
    if tx.state == ClickTransaction.State.CONFIRMED:
        return _answer(data, ALREADY_PAID, merchant_confirm_id=tx.pk)
    if tx.state == ClickTransaction.State.CANCELLED:
        return _answer(data, CANCELLED)
    click_error = int(data.get("error") or 0)
    if click_error < 0:
        # Click tomonida to'lov amalga oshmadi (masalan, mablag' yetarli emas)
        tx.state, tx.error = ClickTransaction.State.CANCELLED, click_error
        tx.save(update_fields=["state", "error", "updated_at"])
        return _answer(data, CANCELLED)
    if invoice.status == Invoice.Status.PAID:
        return _answer(data, ALREADY_PAID)
    try:
        services.mark_paid(invoice, Invoice.Provider.CLICK)
    except services.BillingError:
        return _answer(data, UPDATE_FAILED)
    tx.state = ClickTransaction.State.CONFIRMED
    tx.save(update_fields=["state", "updated_at"])
    return _answer(data, SUCCESS, merchant_confirm_id=tx.pk)
