"""So'rovnoma natijalarini chuqur tahlil: javob bo'yicha filtr, kesishma jadval, dinamika va avtomatik xulosalar."""

from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.talent.tracks import ICONS, Track

from .models import Question
from .services import OTHER

Kind = Question.Kind
GROUPABLE = Question.CHOICE_KINDS | {Kind.TRACK, Kind.SCALE}


def choice_questions(survey):
    """Tanlov savollari: ular bo'yicha filtr, kesishma jadval va klub tuzish mumkin."""
    return [q for q in survey.questions.all() if q.kind in GROUPABLE]


def values_of(question, raw) -> list[str]:
    """Javobni variant qiymatlari ro'yxatiga aylantiradi; ro'yxatda yo'q matn «Boshqa» bo'ladi."""
    if raw in (None, "", []):
        return []
    known = {v for v, _ in question.choices}
    items = raw if isinstance(raw, list) else [raw]
    return [str(item) if str(item) in known else OTHER for item in items]


def label_of(question, value) -> str:
    if value == OTHER:
        return "Boshqa"
    return dict(question.choices).get(value, str(value))


# ---------------------------------------------------------------- javob bo'yicha filtr


def parse_conditions(survey, raw_list) -> list[dict]:
    """GET'dagi answer=<savol>:<qiymat> shartlari. Noto'g'rilari tashlab yuboriladi."""
    questions = {q.pk: q for q in choice_questions(survey)}
    conditions = []
    for raw in raw_list:
        qid, _, value = raw.partition(":")
        if not qid.isdigit() or int(qid) not in questions or not value:
            continue
        question = questions[int(qid)]
        if value != OTHER and value not in {v for v, _ in question.choices}:
            continue
        conditions.append({"raw": raw, "question": question, "value": value, "label": label_of(question, value)})
    return conditions


def apply_conditions(responses, conditions):
    """Barcha shartlarga mos javoblar (VA). JSON maydon har xil bazada bir xil ishlashi uchun Python'da tekshiriladi."""
    if not conditions:
        return responses
    keep = []
    for pk, answers in responses.values_list("pk", "answers"):
        if all(c["value"] in values_of(c["question"], answers.get(str(c["question"].pk))) for c in conditions):
            keep.append(pk)
    return responses.filter(pk__in=keep)


# ---------------------------------------------------------------- dinamika va to'liqlik


def timeline(responses, days=21) -> dict:
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    counts = {
        row["day"]: row["n"]
        for row in responses.filter(submitted_at__date__gte=start)
        .annotate(day=TruncDate("submitted_at"))
        .values("day")
        .annotate(n=Count("id"))
    }
    series = [(start + timedelta(days=i), counts.get(start + timedelta(days=i), 0)) for i in range(days)]
    top = max([n for _, n in series] + [1])
    peak = max(series, key=lambda item: item[1])
    week = sum(n for d, n in series if d > today - timedelta(days=7))
    prev = sum(n for d, n in series if today - timedelta(days=14) < d <= today - timedelta(days=7))
    return {
        "days": [{"date": d, "count": n, "height": round(n * 100 / top), "today": d == today} for d, n in series],
        "peak": {"date": peak[0], "count": peak[1]} if peak[1] else None,
        "week": week,
        "trend": (round((week - prev) * 100 / prev) if prev else None),
    }


def completeness(survey, responses) -> dict:
    questions = [q for q in survey.questions.all() if q.is_answerable]
    if not questions:
        return {"average": 0, "buckets": []}
    keys = [str(q.pk) for q in questions]
    shares = []
    for answers in responses.values_list("answers", flat=True):
        filled = sum(1 for k in keys if answers.get(k) not in (None, "", []))
        shares.append(filled * 100 / len(keys))
    if not shares:
        return {"average": 0, "buckets": []}
    ranges = [("To'liq (100%)", 100, 101), ("75–99%", 75, 100), ("50–74%", 50, 75), ("50% dan kam", 0, 50)]
    buckets = []
    for label, low, high in ranges:
        n = sum(1 for s in shares if low <= s < high)
        buckets.append({"label": label, "count": n, "pct": round(n * 100 / len(shares))})
    return {"average": round(sum(shares) / len(shares)), "buckets": buckets}


# ---------------------------------------------------------------- kesishma jadval


def dimensions(survey) -> list[tuple[str, str]]:
    dims = []
    if survey.collect_identity:
        dims += [("faculty", "Fakultet"), ("course", "Kurs")]
    dims += [(f"q{q.pk}", q.title) for q in choice_questions(survey)]
    return dims


def _row_keys(responses, dim, survey):
    """Har bir javob uchun kesim qiymatlari: {javob_id: [(kalit, nom), ...]}."""
    if dim == "faculty":
        return {
            pk: [(name or "—", name or "Ko'rsatilmagan")]
            for pk, name in responses.values_list("pk", "faculty__short_name")
        }
    if dim == "course":
        return {
            pk: [(c or 0, f"{c}-kurs" if c else "Ko'rsatilmagan")] for pk, c in responses.values_list("pk", "course")
        }
    question = next((q for q in choice_questions(survey) if f"q{q.pk}" == dim), None)
    if question is None:
        return {}
    result = {}
    for pk, answers in responses.values_list("pk", "answers"):
        result[pk] = [(v, label_of(question, v)) for v in values_of(question, answers.get(str(question.pk)))]
    return result


def crosstab(survey, responses, question, dim) -> dict | None:
    """Qatorlar: kesim (fakultet, kurs yoki boshqa savol). Ustunlar: tanlangan savol variantlari."""
    if question is None:
        return None
    columns = [(v, label_of(question, v)) for v, _ in question.choices]
    answers_by_pk = dict(responses.values_list("pk", "answers"))
    rows_by_pk = _row_keys(responses, dim, survey)
    table = defaultdict(Counter)
    row_names, row_people = {}, Counter()
    has_other = False
    for pk, answers in answers_by_pk.items():
        picked = values_of(question, answers.get(str(question.pk)))
        if not picked:
            continue
        has_other = has_other or OTHER in picked
        for key, name in rows_by_pk.get(pk, []):
            row_names[key] = name
            row_people[key] += 1
            for value in picked:
                table[key][value] += 1
    if has_other:
        columns.append((OTHER, "Boshqa"))
    peak = max([n for row in table.values() for n in row.values()] + [1])
    rows = []
    for key in sorted(row_names, key=lambda k: (-row_people[k], str(row_names[k]))):
        cells = []
        for value, _ in columns:
            n = table[key][value]
            cells.append({"count": n, "pct": round(n * 100 / row_people[key]) if row_people[key] else 0,
                          "heat": round(n * 100 / peak)})  # fmt: skip
        counts = [c["count"] for c in cells]
        top = max(counts) if counts else 0
        best = counts.index(top) if top and counts.count(top) == 1 else None
        rows.append({"label": row_names[key], "total": row_people[key], "cells": cells, "best": best})
    totals = [sum(table[k][v] for k in table) for v, _ in columns]
    return {"question": question, "columns": [label for _, label in columns], "rows": rows, "totals": totals}


# ---------------------------------------------------------------- xulosalar


def insights(survey, responses, summary, timeline_data, complete) -> list[dict]:
    total = summary["total"]
    if not total:
        return []
    items = []
    if summary["linked"]:
        items.append({"icon": "👥", "text": f"{total} ta javobdan {summary['linked']} tasi platformadagi talabalardan "
                                            f"({round(summary['linked'] * 100 / total)}%)."})  # fmt: skip
    if summary["faculties"]:
        name, n = summary["faculties"][0]
        items.append({"icon": "🏛", "text": f"Eng faol fakultet: {name}, javoblarning {round(n * 100 / total)}% i."})
    for block in summary["blocks"]:
        if block.get("section") or not block.get("bars") or not block["answered"]:
            continue
        question = block["question"]
        best = max(block["bars"], key=lambda b: b["count"])
        if not best["count"]:
            continue
        if question.kind == Kind.SCALE:
            items.append({"icon": "⭐", "text": f"«{question.title}»: o'rtacha baho {block.get('average')} / "
                                               f"{question.scale_max}."})  # fmt: skip
        elif question.kind == Kind.TRACK:
            icon = next((ICONS[v] for v, text in Track.choices if text == best["label"]), "🧭")
            items.append({"icon": icon, "text": f"Eng ko'p iqtidor yo'nalishi: {best['label']} ({best['pct']}%)."})
        else:
            word = "tanlangan" if question.kind == Kind.MULTIPLE else "javob"
            items.append({"icon": "📌", "text": f"«{question.title}»: eng ko'p {word} «{best['label']}» "
                                               f"({best['count']} ta, {best['pct']}%)."})  # fmt: skip
        if len(items) >= 8:
            break
    if timeline_data["peak"]:
        peak = timeline_data["peak"]
        items.append({"icon": "📈", "text": f"Eng ko'p javob {peak['date']:%d.%m} kuni keldi: {peak['count']} ta."})
    if complete["average"]:
        items.append(
            {"icon": "✅", "text": f"Talabalar savollarning o'rtacha {complete['average']}% iga javob bergan."}
        )
    return items
