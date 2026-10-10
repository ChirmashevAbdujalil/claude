import math

from django import template
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
