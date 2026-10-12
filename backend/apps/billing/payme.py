"""Payme Merchant API (JSON-RPC 2.0).

Payme bizning manzilga POST so'rov yuboradi: Basic auth (login «Paycom», parol — kassa kaliti).
Summalar tiyinda, vaqtlar millisekundlarda. Javob doim HTTP 200, xato bo'lsa "error" maydoni bilan.
Hujjat: https://developer.help.paycom.uz/metody-merchant-api/
"""

import base64
import binascii
import hmac
import time

from django.conf import settings
from django.db import transaction

from . import services
from .models import Invoice, PaymeTransaction

TIMEOUT_MS = 12 * 60 * 60 * 1000  # yaratilgan tranzaksiya 12 soat ichida bajarilmasa bekor qilinadi
REASON_TIMEOUT = 4


def now_ms() -> int:
    return int(time.time() * 1000)


class PaymeError(Exception):
    def __init__(self, code: int, uz: str, ru: str = "", en: str = "", data=None):
        super().__init__(uz)
        self.code, self.data = code, data
        self.message = {"uz": uz, "ru": ru or uz, "en": en or uz}


def _invalid_amount():
    return PaymeError(-31001, "Noto'g'ri summa", "Неверная сумма", "Invalid amount")


def _not_found():
    return PaymeError(-31003, "Tranzaksiya topilmadi", "Транзакция не найдена", "Transaction not found")


def _cannot_perform():
    return PaymeError(
        -31008, "Amalni bajarib bo'lmaydi", "Невозможно выполнить операцию", "Unable to perform operation"
    )


def check_auth(header: str) -> bool:
    if not header.startswith("Basic "):
        return False
    try:
        login, _, password = base64.b64decode(header[6:]).decode().partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return False
    return login == "Paycom" and bool(settings.PAYME_KEY) and hmac.compare_digest(password, settings.PAYME_KEY)


def _invoice(params) -> Invoice:
    field = settings.PAYME_ACCOUNT_FIELD
    value = (params.get("account") or {}).get(field)
    invoice = Invoice.objects.filter(pk=value).first() if str(value or "").isdigit() else None
    if invoice is None:
        raise PaymeError(-31050, "To'lov hisobi topilmadi", "Счёт не найден", "Invoice not found", data=field)
    return invoice


def check_perform_transaction(params) -> dict:
    invoice = _invoice(params)
    if invoice.status != Invoice.Status.PENDING:
        raise PaymeError(-31051, "Hisob to'langan yoki bekor qilingan", "Счёт уже оплачен или отменён",
                         "Invoice is already paid or cancelled", data=settings.PAYME_ACCOUNT_FIELD)  # fmt: skip
    if int(params.get("amount", -1)) != invoice.amount_tiyin:
        raise _invalid_amount()
    return {"allow": True}


def _cancel(tx: PaymeTransaction, reason: int, state: int):
    tx.state, tx.reason, tx.cancel_time = state, reason, now_ms()
    tx.save(update_fields=["state", "reason", "cancel_time"])


def _details(tx: PaymeTransaction) -> dict:
    return {
        "create_time": tx.create_time,
        "perform_time": tx.perform_time,
        "cancel_time": tx.cancel_time,
        "transaction": str(tx.pk),
        "state": tx.state,
        "reason": tx.reason,
    }


def _committed(func):
    """Tranzaksiya ichida qaytarilgan PaymeError'ni commit'dan keyin ko'taradi.

    Muddati o'tgan tranzaksiyani bekor qilish saqlanib qolishi kerak, xato esa Payme'ga baribir qaytadi.
    """

    def wrapper(params):
        result = transaction.atomic(func)(params)
        if isinstance(result, PaymeError):
            raise result
        return result

    wrapper.__name__ = func.__name__
    return wrapper


@_committed
def create_transaction(params) -> dict:
    tx = PaymeTransaction.objects.select_for_update().filter(payme_id=params.get("id")).first()
    if tx is not None:
        if tx.state != PaymeTransaction.State.CREATED:
            raise _cannot_perform()
        if now_ms() - tx.create_time > TIMEOUT_MS:
            _cancel(tx, REASON_TIMEOUT, PaymeTransaction.State.CANCELLED)
            services.cancel(tx.invoice)
            return _cannot_perform()
        return {"create_time": tx.create_time, "transaction": str(tx.pk), "state": tx.state}

    check_perform_transaction(params)
    invoice = _invoice(params)
    if invoice.payme_transactions.filter(state=PaymeTransaction.State.CREATED).exists():
        raise PaymeError(-31052, "Bu hisob bo'yicha boshqa to'lov kutilmoqda", "По счёту ожидается другой платёж",
                         "Another payment is pending for this invoice", data=settings.PAYME_ACCOUNT_FIELD)  # fmt: skip
    tx = PaymeTransaction.objects.create(
        payme_id=params["id"],
        invoice=invoice,
        amount=int(params["amount"]),
        payme_time=int(params.get("time") or now_ms()),
        create_time=now_ms(),
    )
    return {"create_time": tx.create_time, "transaction": str(tx.pk), "state": tx.state}


@_committed
def perform_transaction(params) -> dict:
    tx = PaymeTransaction.objects.select_for_update().filter(payme_id=params.get("id")).first()
    if tx is None:
        raise _not_found()
    if tx.state == PaymeTransaction.State.CREATED:
        if now_ms() - tx.create_time > TIMEOUT_MS:
            _cancel(tx, REASON_TIMEOUT, PaymeTransaction.State.CANCELLED)
            services.cancel(tx.invoice)
            return _cannot_perform()
        services.mark_paid(tx.invoice, Invoice.Provider.PAYME)
        tx.state, tx.perform_time = PaymeTransaction.State.PERFORMED, now_ms()
        tx.save(update_fields=["state", "perform_time"])
    elif tx.state != PaymeTransaction.State.PERFORMED:
        raise _cannot_perform()
    return {"transaction": str(tx.pk), "perform_time": tx.perform_time, "state": tx.state}


@transaction.atomic
def cancel_transaction(params) -> dict:
    tx = PaymeTransaction.objects.select_for_update().filter(payme_id=params.get("id")).first()
    if tx is None:
        raise _not_found()
    reason = params.get("reason")
    if tx.state == PaymeTransaction.State.CREATED:
        _cancel(tx, reason, PaymeTransaction.State.CANCELLED)
        services.cancel(tx.invoice)
    elif tx.state == PaymeTransaction.State.PERFORMED:
        services.refund(tx.invoice)
        _cancel(tx, reason, PaymeTransaction.State.CANCELLED_AFTER_PERFORM)
    return {"transaction": str(tx.pk), "cancel_time": tx.cancel_time, "state": tx.state}


def check_transaction(params) -> dict:
    tx = PaymeTransaction.objects.filter(payme_id=params.get("id")).first()
    if tx is None:
        raise _not_found()
    return _details(tx)


def get_statement(params) -> dict:
    rows = PaymeTransaction.objects.filter(payme_time__gte=int(params["from"]), payme_time__lte=int(params["to"]))
    return {
        "transactions": [
            {
                "id": tx.payme_id,
                "time": tx.payme_time,
                "amount": tx.amount,
                "account": {settings.PAYME_ACCOUNT_FIELD: str(tx.invoice_id)},
                **_details(tx),
            }
            for tx in rows.order_by("payme_time")
        ]
    }


def set_fiscal_data(params) -> dict:
    # Fiskal chek ma'lumotlari: hozircha saqlanmaydi, Payme muvaffaqiyatli javob kutadi
    return {"success": True}


METHODS = {
    "CheckPerformTransaction": check_perform_transaction,
    "CreateTransaction": create_transaction,
    "PerformTransaction": perform_transaction,
    "CancelTransaction": cancel_transaction,
    "CheckTransaction": check_transaction,
    "GetStatement": get_statement,
    "SetFiscalData": set_fiscal_data,
}


def dispatch(payload) -> dict:
    """JSON-RPC so'rovini bajaradi va javob obyektini qaytaradi (HTTP holati doim 200)."""
    request_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or "method" not in payload or not isinstance(payload.get("params", {}), dict):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32600, "message": "Invalid Request"}}
    method = METHODS.get(payload["method"])
    if method is None:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
    try:
        result = method(payload.get("params") or {})
    except PaymeError as exc:
        error = {"code": exc.code, "message": exc.message}
        if exc.data is not None:
            error["data"] = exc.data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}
    except (KeyError, TypeError, ValueError):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32600, "message": "Invalid params"}}
    return {"jsonrpc": "2.0", "id": request_id, "result": result}
