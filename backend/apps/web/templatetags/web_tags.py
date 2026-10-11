import math

from django import template
from django.templatetags.static import static
from django.utils.html import format_html

from apps.arena.levels import level_for_xp

register = template.Library()

RADAR_SIZE = 220
RADAR_RADIUS = 78
RADAR_MAX = 5


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


@register.simple_tag
def brand_logo(size=40, extra_class=""):
    """Institut logotipi: oddiy va retina ekranlar uchun."""
    small = static("web/img/adti-logo-64.png")
    large = static("web/img/adti-logo-128.png") if size <= 64 else static("web/img/adti-logo-256.webp")
    classes = f"brand-logo {extra_class}".strip()
    return format_html(
        '<img src="{}" srcset="{} 2x" width="{}" height="{}" class="{}" '
        'alt="Andijon davlat texnika instituti logotipi">',
        small if size <= 32 else large,
        large,
        size,
        size,
        classes,
    )
