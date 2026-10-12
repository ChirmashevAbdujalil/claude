"""OTM obunasi uchun to'lovlar.

Bu modellar OTM bo'yicha avtomatik cheklanmaydi: Payme va Click so'rovlari platforma darajasida keladi.
"""

from django.conf import settings
from django.db import models

from apps.tenants import plans


class Invoice(models.Model):
    """To'lov hisobi: qaysi OTM, qaysi tarif, necha oyga va qancha."""

    class Status(models.TextChoices):
        PENDING = "pending", "To'lov kutilmoqda"
        PAID = "paid", "To'langan"
        CANCELLED = "cancelled", "Bekor qilingan"
        REFUNDED = "refunded", "Qaytarilgan"

    class Provider(models.TextChoices):
        PAYME = "payme", "Payme"
        CLICK = "click", "Click"

    institution = models.ForeignKey(
        "tenants.Institution", on_delete=models.PROTECT, related_name="invoices", verbose_name="OTM"
    )
    plan = models.CharField("tarif", max_length=20, choices=plans.CHOICES)
    months = models.PositiveSmallIntegerField("oylar soni")
    amount = models.PositiveIntegerField("summa (so'm)")
    status = models.CharField("holat", max_length=20, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField("to'lov tizimi", max_length=10, choices=Provider.choices, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField("to'langan vaqt", null=True, blank=True)
    # To'lov qaytarilsa, OTM holatini tiklash uchun
    previous_plan = models.CharField(max_length=20, blank=True, editable=False)
    previous_paid_until = models.DateField(null=True, blank=True, editable=False)
    new_paid_until = models.DateField("yangi muddat", null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "to'lov hisobi"
        verbose_name_plural = "to'lov hisoblari"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} {self.institution.short_name}: {self.get_plan_display()} × {self.months} oy"

    @property
    def amount_tiyin(self) -> int:
        return self.amount * 100


class PaymeTransaction(models.Model):
    """Payme Merchant API tranzaksiyasi. Vaqtlar Payme talabiga ko'ra millisekundlarda."""

    class State(models.IntegerChoices):
        CREATED = 1, "Yaratilgan"
        PERFORMED = 2, "Bajarilgan"
        CANCELLED = -1, "Bajarilmasdan bekor qilingan"
        CANCELLED_AFTER_PERFORM = -2, "Bajarilgandan keyin bekor qilingan"

    payme_id = models.CharField("Payme ID", max_length=64, unique=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payme_transactions")
    amount = models.PositiveBigIntegerField("summa (tiyin)")
    state = models.SmallIntegerField("holat", choices=State.choices, default=State.CREATED)
    reason = models.SmallIntegerField("bekor qilish sababi", null=True, blank=True)
    payme_time = models.BigIntegerField("Payme vaqti")
    create_time = models.BigIntegerField()
    perform_time = models.BigIntegerField(default=0)
    cancel_time = models.BigIntegerField(default=0)

    class Meta:
        verbose_name = "Payme tranzaksiyasi"
        verbose_name_plural = "Payme tranzaksiyalari"
        ordering = ["-create_time"]

    def __str__(self):
        return f"Payme {self.payme_id} ({self.get_state_display()})"


class ClickTransaction(models.Model):
    class State(models.TextChoices):
        PREPARED = "prepared", "Tayyorlangan"
        CONFIRMED = "confirmed", "Tasdiqlangan"
        CANCELLED = "cancelled", "Bekor qilingan"

    click_trans_id = models.BigIntegerField("Click ID", unique=True)
    click_paydoc_id = models.BigIntegerField("Click paydoc ID", null=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="click_transactions")
    amount = models.DecimalField("summa (so'm)", max_digits=14, decimal_places=2)
    state = models.CharField("holat", max_length=10, choices=State.choices, default=State.PREPARED)
    error = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Click tranzaksiyasi"
        verbose_name_plural = "Click tranzaksiyalari"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Click {self.click_trans_id} ({self.get_state_display()})"
