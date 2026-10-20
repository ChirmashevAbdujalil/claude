import math
import os
import re

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

from apps.arena.levels import level_for_xp

register = template.Library()

RADAR_SIZE = 220
RADAR_RADIUS = 78
RADAR_MAX = 5


@register.simple_tag
def asset(path):
    """CSS/JS manzili. Ishlab chiqishda fayl o'zgarsa, brauzer eski nusxani keshdan olmasligi uchun versiya qo'shiladi.

    Production'da manifest saqlagich fayl nomiga xesh qo'shadi, shuning uchun bu yerda faqat DEBUG holati.
    """
    url = static(path)
    if settings.DEBUG:
        found = finders.find(path)
        if found:
            url += f"?v={int(os.path.getmtime(found))}"
    return url


@register.simple_tag
def icon(name, extra_class=""):
    classes = f"icon {extra_class}".strip()
    return format_html('<svg class="{}" aria-hidden="true"><use href="#i-{}"></use></svg>', classes, name)


@register.filter
def level(xp):
    return level_for_xp(xp or 0)


@register.filter
def percent(value):
    """0..1 oralig'idagi qiymatni foizga aylantiradi."""
    try:
        return max(0, min(100, round(float(value) * 100)))
    except (TypeError, ValueError):
        return 0


@register.filter
def ratio(value, total):
    try:
        total = float(total)
        return max(0, min(100, round(float(value) / total * 100))) if total else 0
    except (TypeError, ValueError):
        return 0


@register.filter
def minus(value, other):
    try:
        return max(int(value) - int(other), 0)
    except (TypeError, ValueError):
        return 0


@register.filter
def money(value):
    """1500000 -> «1 500 000» (o'zbekcha uslubda bo'shliq bilan)."""
    try:
        return f"{int(value):,}".replace(",", "\u00a0")
    except (TypeError, ValueError):
        return value


@register.filter
def display_name(user):
    return user.get_full_name() or user.username


@register.inclusion_tag("web/partials/avatar.html")
def avatar(user, size=""):
    name = user.get_full_name() or user.username
    parts = [p for p in name.split() if p]
    initials = "".join(p[0] for p in parts[:2]).upper() or "?"
    return {"user": user, "initials": initials, "hue": (user.pk or 0) * 47 % 360, "size": size}


@register.simple_tag(takes_context=True)
def active(context, *names):
    """Joriy sahifa berilgan URL nomlaridan biriga tegishli bo'lsa 'active' qaytaradi."""
    match = getattr(context.get("request"), "resolver_match", None)
    if match is None:
        return ""
    current = match.url_name or ""
    return "active" if any(current == n or current.startswith(f"{n}-") for n in names) else ""


@register.inclusion_tag("web/partials/radar.html")
def radar(skill_map):
    center = RADAR_SIZE / 2
    count = len(skill_map)

    def point(index, value):
        angle = -math.pi / 2 + 2 * math.pi * index / count
        r = RADAR_RADIUS * value / RADAR_MAX
        return round(center + r * math.cos(angle), 1), round(center + r * math.sin(angle), 1)

    grid = [" ".join(f"{x},{y}" for x, y in (point(i, level) for i in range(count))) for level in range(1, 6)]
    axes = [point(i, RADAR_MAX) for i in range(count)]
    values = [point(i, row["score"]) for i, row in enumerate(skill_map)]
    labels = []
    for i, row in enumerate(skill_map):
        x, y = point(i, RADAR_MAX + 1.1)
        anchor = "middle" if abs(x - center) < 8 else ("start" if x > center else "end")
        labels.append({"x": x, "y": y + 3, "text": row["label"], "anchor": anchor})
    return {
        "size": RADAR_SIZE,
        "center": center,
        "grid": grid,
        "axes": axes,
        "area": " ".join(f"{x},{y}" for x, y in values),
        "dots": values,
        "labels": labels,
        "has_data": any(row["score"] for row in skill_map),
    }


STEPPERS = {
    "submission": {
        "labels": ["Yuborildi", "Tekshirilmoqda", "Natija"],
        "progress": {"pending": 1},
        "done": {"accepted": "Qabul qilindi"},
        "failed": {"rejected": "Rad etildi"},
        "hint": "O'qituvchilar odatda 1–3 ish kuni ichida tekshiradi",
    },
    "achievement": {
        "labels": ["Yuborildi", "O'qituvchi ko'rmoqda", "Natija"],
        "progress": {"pending": 1},
        "done": {"approved": "Tasdiqlandi"},
        "failed": {"rejected": "Rad etildi"},
        "hint": "Hujjat tekshirilgach XP avtomatik qo'shiladi",
    },
    "application": {
        "labels": ["Yuborildi", "Ko'rib chiqilmoqda", "Saralandi", "Natija"],
        "progress": {"submitted": 1, "shortlisted": 3},
        "done": {"accepted": "Qabul qilindi"},
        "failed": {"rejected": "Rad etildi"},
        "hint": "Natija haqida bildirishnoma olasiz",
    },
}


@register.inclusion_tag("web/partials/stepper.html")
def stepper(kind, status, compact=False):
    """Jarayon bosqichlari: done / current / todo / failed."""
    config = STEPPERS[kind]
    labels = list(config["labels"])
    last = len(labels) - 1
    if status in config["done"]:
        labels[last] = config["done"][status]
        states = ["done"] * len(labels)
        hint = ""
    elif status in config["failed"]:
        labels[last] = config["failed"][status]
        states = ["done"] * last + ["failed"]
        hint = ""
    else:
        current = config["progress"].get(status, 1)
        states = ["done" if i < current else "current" if i == current else "todo" for i in range(len(labels))]
        hint = config["hint"]
    return {
        "steps": [{"label": label, "state": state} for label, state in zip(labels, states, strict=True)],
        "hint": hint,
        "compact": compact,
    }


@register.simple_tag(takes_context=True)
def brand_logo(context, size=40, extra_class=""):
    """OTM logotipi. Yuklanmagan bo'lsa: asosiy OTM uchun institut logosi, boshqalar uchun bosh harflar."""
    institution = context.get("institution")
    classes = f"brand-logo {extra_class}".strip()
    name = institution.name if institution else "Talent Hub"
    if institution is not None and institution.logo:
        return format_html(
            '<img src="{}" width="{}" height="{}" class="{}" alt="{} logotipi">',
            institution.logo.url,
            size,
            size,
            classes,
            name,
        )
    if institution is not None and not institution.is_default:
        return format_html(
            '<span class="{} brand-initials" style="width:{}px;height:{}px;font-size:{}px" aria-label="{}">{}</span>',
            classes,
            size,
            size,
            max(10, size // 3),
            name,
            institution.initials,
        )
    small = static("web/img/adti-logo-64.png")
    large = static("web/img/adti-logo-128.png") if size <= 64 else static("web/img/adti-logo-256.webp")
    return format_html(
        '<img src="{}" srcset="{} 2x" width="{}" height="{}" class="{}" alt="{} logotipi">',
        small if size <= 32 else large,
        large,
        size,
        size,
        classes,
        name,
    )


BOLD = re.compile(r"\*\*(.+?)\*\*")


@register.filter
def rich_text(value):
    """Oddiy matn: **qalin**, bo'sh qator — yangi xatboshi, oddiy qator tashlash — <br>. HTML xavfsiz qochiriladi."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", str(value or "").replace("\r\n", "\n")) if p.strip()]
    html = []
    for paragraph in paragraphs:
        text = BOLD.sub(r"<b>\1</b>", str(escape(paragraph)))
        html.append(f"<p>{text.replace(chr(10), '<br>')}</p>")
    return mark_safe("".join(html))
