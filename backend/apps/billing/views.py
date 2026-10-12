import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.tenants.context import unscoped

from . import click, payme, services
from .models import Invoice


@csrf_exempt
def payme_endpoint(request):
    """Payme Merchant API. Kassa sozlamalarida manzil: https://<domen>/billing/payme/"""
    if request.method != "POST":
        return JsonResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32300, "message": "POST required"}})
    try:
        payload = json.loads(request.body or b"")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
    request_id = payload.get("id") if isinstance(payload, dict) else None
    if not payme.check_auth(request.headers.get("Authorization", "")):
        error = {
            "code": -32504,
            "message": {"uz": "Ruxsat yo'q", "ru": "Недостаточно привилегий", "en": "Insufficient privileges"},
        }
        return JsonResponse({"jsonrpc": "2.0", "id": request_id, "error": error})
    with unscoped():
        return JsonResponse(payme.dispatch(payload))


@csrf_exempt
@require_POST
def click_prepare(request):
    """Click SHOP API, Prepare URL: https://<domen>/billing/click/prepare/"""
    with unscoped():
        return JsonResponse(click.prepare(request.POST))


@csrf_exempt
@require_POST
def click_complete(request):
    """Click SHOP API, Complete URL: https://<domen>/billing/click/complete/"""
    with unscoped():
        return JsonResponse(click.complete(request.POST))


def _admin_institution(request):
    if not request.user.is_institution_admin or request.institution is None:
        raise PermissionDenied
    return request.institution


@login_required
@require_POST
def invoice_create(request):
    institution = _admin_institution(request)
    try:
        invoice = services.create_invoice(
            institution, request.POST.get("plan", ""), int(request.POST.get("months") or 0), request.user
        )
    except (services.BillingError, ValueError) as exc:
        messages.error(request, str(exc) or "Noto'g'ri ma'lumot")
        return redirect("web:institution-settings")
    return redirect("billing:invoice", pk=invoice.pk)


@login_required
def invoice_detail(request, pk):
    institution = _admin_institution(request)
    invoice = get_object_or_404(Invoice, pk=pk, institution=institution)
    return_url = request.build_absolute_uri(reverse("billing:invoice", args=[invoice.pk]))
    context = {
        "invoice": invoice,
        "payme_url": services.payme_checkout_url(invoice, return_url) if services.payme_enabled() else "",
        "click_url": services.click_checkout_url(invoice, return_url) if services.click_enabled() else "",
        "test_mode": services.payme_enabled() and settings.PAYME_TEST,
    }
    return render(request, "web/billing/invoice.html", context)
