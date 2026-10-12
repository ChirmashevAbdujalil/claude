from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("payme/", views.payme_endpoint, name="payme"),
    path("click/prepare/", views.click_prepare, name="click-prepare"),
    path("click/complete/", views.click_complete, name="click-complete"),
    path("invoices/new/", views.invoice_create, name="invoice-create"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice"),
]
