"""So'rovnoma natijalari va klub a'zolari uchun dizaynli Excel (.xlsx) fayllar."""

from collections import Counter

from django.utils import timezone

from . import analytics
from . import xlsx as x
from .models import Question
from .services import _label, summary

Kind = Question.Kind


def _answer_value(question, value):
    """Excel uchun javob: shkala va raqam son bo'ladi (saralash va hisoblash uchun), qolgani matn."""
    if value in (None, "", []):
        return ""
    if question.kind == Kind.SCALE:
        return int(value)
    if question.kind == Kind.NUMBER:
        try:
            return float(value) if "." in str(value) else int(value)
        except ValueError:
            return str(value)
    return _label(question, value)


def _widths_for(questions):
    widths = []
    for q in questions:
        if q.kind == Kind.LONG:
            widths.append(48)
        elif q.kind in (Kind.SCALE, Kind.NUMBER):
            widths.append(14)
        elif q.kind == Kind.MULTIPLE:
            widths.append(36)
        else:
            widths.append(26)
    return widths


def _responses_sheet(survey, responses, subtitle):
    questions = [q for q in survey.questions.all() if q.is_answerable]
    sheet = x.Sheet("Javoblar")
    identity = survey.collect_identity
    head = ["№", "Yuborilgan"]
    widths = [6, 17]
    if identity:
        head += ["F.I.Sh.", "Fakultet", "Kurs", "Guruh", "Telefon"]
        widths += [30, 26, 7, 12, 18]
    head += ["Login"] + [q.title for q in questions]
    widths += [20] + _widths_for(questions)
    sheet.widths = widths
    x.title_block(sheet, f"«{survey.title}»: barcha javoblar", subtitle, len(head))
    header_row = sheet.add([(h, "head") for h in head], height=42)
    numeric = {Kind.SCALE, Kind.NUMBER}
    rows = responses.select_related("faculty", "user").order_by("submitted_at", "id")
    count = 0
    for count, r in enumerate(rows, 1):
        z = "_z" if count % 2 == 0 else ""
        cells = [(count, f"num{z}"), (timezone.localtime(r.submitted_at).strftime("%d.%m.%Y %H:%M"), f"text{z}")]
        if identity:
            cells += [
                (r.display_name, f"bold{z}"),
                (getattr(r.faculty, "name", ""), f"text{z}"),
                (r.course or "", f"num{z}"),
                (r.group, f"num{z}"),
                (r.phone, f"text{z}"),
            ]
        cells.append((r.user.username if r.user_id else "", f"text{z}"))
        for q in questions:
            value = _answer_value(q, r.answers.get(str(q.pk)))
            cells.append((value, f"num{z}" if q.kind in numeric else f"text{z}"))
        sheet.add(cells)
    last = header_row + max(count, 1)
    sheet.freeze = (header_row, 3 if identity else 2)
    sheet.filter = f"A{header_row}:{x.col_name(len(head) - 1)}{last}"
    return sheet


def _summary_sheet(survey, responses, data, subtitle):
    sheet = x.Sheet("Umumiy natija", tab_color=x.CHART, landscape=False)
    sheet.widths = [44, 10, 10, 34]
    x.title_block(sheet, f"«{survey.title}»: umumiy natija", subtitle, 4)
    complete = analytics.completeness(survey, responses)
    kpis = [
        ("Jami javob", data["total"]),
        ("Platformadagi talabalardan", data["linked"]),
        ("Qamrab olingan fakultetlar", len(data["faculties"])),
        ("O'rtacha to'liqlik", complete["average"] / 100 if complete["average"] else 0),
    ]
    for label, value in kpis:
        style = "pct" if label == "O'rtacha to'liqlik" else "kpi_value"
        row = sheet.add([(label, "kpi_label"), (value, style), ("", "kpi_label"), ("", "kpi_label")], height=22)
        sheet.merge(row, 1, 3)
    sheet.blank(14)
    for block in data["blocks"]:
        question = block["question"]
        if block.get("section"):
            row = sheet.add([(question.title.upper(), "section")] + [("", "section")] * 3, height=24)
            sheet.merge(row, 0, 3)
            continue
        info = f"{block['answered']} ta javob"
        if block.get("skipped"):
            info += f" · {block['skipped']} kishi o'tkazib yuborgan"
        if block.get("average") is not None:
            info += f" · o'rtacha {block['average']}"
            if question.kind == Kind.SCALE:
                info += f" / {question.scale_max}"
        row = sheet.add([(question.title, "bold"), (info, "note"), ("", "note"), ("", "note")], height=30)
        sheet.merge(row, 1, 3)
        if block.get("bars"):
            sheet.add([(h, "head") for h in ("Variant", "Soni", "Foiz", "Grafik")], height=22)
            answered = block["answered"] or 1
            top = max([b["count"] for b in block["bars"]] + [1])
            for i, item in enumerate(block["bars"], 1):
                z = "_z" if i % 2 == 0 else ""
                sheet.add([
                    (item["label"], f"text{z}"),
                    (item["count"], f"num{z}"),
                    (item["count"] / answered if item["count"] else 0, f"pct{z}"),
                    (x.bar(item["count"] / top), f"bar{z}"),
                ])  # fmt: skip
        else:
            for i, text in enumerate(block.get("texts", [])[:10], 1):
                row = sheet.add([(f"{i}. {text}", "text")] + [("", "text")] * 3)
                sheet.merge(row, 0, 3)
            if block["answered"] > 10:
                sheet.add([("Barcha matnli javoblar «Javoblar» varag'ida", "note")])
        sheet.blank(14)
    return sheet


def _breakdown_sheet(survey, responses, data, subtitle):
    sheet = x.Sheet("Kesimlar", tab_color=x.DARK, landscape=False)
    sheet.widths = [34, 10, 10, 34]
    x.title_block(sheet, "Fakultet, kurs va guruh kesimi", subtitle, 4)
    total = data["total"] or 1
    groups = Counter(g for g in responses.values_list("group", flat=True) if g)
    sections = [
        ("Fakultetlar", data["faculties"]),
        ("Kurslar", data["courses"]),
        ("Guruhlar (eng faol 30 ta)", groups.most_common(30)),
    ]
    for title, items in sections:
        if not items:
            continue
        row = sheet.add([(title.upper(), "section")] + [("", "section")] * 3, height=24)
        sheet.merge(row, 0, 3)
        sheet.add([(h, "head") for h in ("Nomi", "Javob", "Ulushi", "Grafik")], height=22)
        top = max([n for _, n in items] + [1])
        for i, (name, n) in enumerate(items, 1):
            z = "_z" if i % 2 == 0 else ""
            sheet.add([(name, f"text{z}"), (n, f"num{z}"), (n / total, f"pct{z}"), (x.bar(n / top), f"bar{z}")])
        sheet.blank(14)
    return sheet


def _clubs_sheet(survey, subtitle):
    clubs = list(survey.clubs.select_related("leader", "mentor"))
    if not clubs:
        return None
    sheet = x.Sheet("Klublar", tab_color="F59E0B")
    head = ["Klub", "F.I.Sh.", "Fakultet", "Kurs", "Guruh", "Telefon", "Login", "Rol"]
    sheet.widths = [30, 30, 26, 7, 12, 18, 20, 12]
    x.title_block(sheet, "Javoblar asosida tuzilgan klublar", subtitle, len(head))
    header = sheet.add([(h, "head") for h in head], height=24)
    count = 0
    for club in clubs:
        row = sheet.add(
            [(f"{club.emoji} {club.name} · {club.members.count()} a'zo"
              + (f" · mentor: {club.mentor}" if club.mentor else ""), "section")] + [("", "section")] * 7,
            height=24,
        )  # fmt: skip
        sheet.merge(row, 0, 7)
        members = club.members.select_related("response__faculty", "response__user").order_by("response__full_name")
        for i, member in enumerate(members, 1):
            r = member.response
            z = "_z" if i % 2 == 0 else ""
            role = "Sardor" if r.user_id and r.user_id == club.leader_id else "A'zo"
            count += 1
            sheet.add([
                (club.name, f"text{z}"), (r.display_name, f"bold{z}"), (getattr(r.faculty, "name", ""), f"text{z}"),
                (r.course or "", f"num{z}"), (r.group, f"num{z}"), (r.phone, f"text{z}"),
                (r.user.username if r.user_id else "", f"text{z}"), (role, f"num{z}"),
            ])  # fmt: skip
    sheet.freeze = (header, 0)
    return sheet


def results_workbook(survey, responses, *, institution, conditions=()) -> bytes:
    now = timezone.localtime()
    data = summary(survey, responses)
    subtitle = f"{institution} · {data['total']} ta javob · {now:%d.%m.%Y %H:%M}"
    if conditions:
        subtitle += " · filtr: " + "; ".join(f"{c['question'].title[:40]} = {c['label']}" for c in conditions)
    sheets = [
        _summary_sheet(survey, responses, data, subtitle),
        _responses_sheet(survey, responses, subtitle),
    ]
    if survey.collect_identity:
        sheets.append(_breakdown_sheet(survey, responses, data, subtitle))
    clubs_sheet = _clubs_sheet(survey, subtitle)
    if clubs_sheet is not None:
        sheets.append(clubs_sheet)
    return x.workbook(sheets, title=survey.title, author=institution)


def club_workbook(club, *, institution) -> bytes:
    now = timezone.localtime()
    sheet = x.Sheet(club.name[:31])
    head = ["№", "F.I.Sh.", "Fakultet", "Kurs", "Guruh", "Telefon", "Login", "Rol"]
    sheet.widths = [6, 32, 30, 7, 12, 18, 20, 12]
    people = club.members.count()
    extra = " · ".join(filter(None, [f"sardor: {club.leader}" if club.leader else "",
                                     f"mentor: {club.mentor}" if club.mentor else ""]))  # fmt: skip
    subtitle = f"{institution} · {people} a'zo{' · ' + extra if extra else ''} · {now:%d.%m.%Y %H:%M}"
    x.title_block(sheet, f"{club.emoji} {club.name}", subtitle, len(head))
    header = sheet.add([(h, "head") for h in head], height=24)
    members = club.members.select_related("response__faculty", "response__user").order_by("response__full_name")
    for i, member in enumerate(members, 1):
        r = member.response
        z = "_z" if i % 2 == 0 else ""
        role = "Sardor" if r.user_id and r.user_id == club.leader_id else "A'zo"
        sheet.add([
            (i, f"num{z}"), (r.display_name, f"bold{z}"), (getattr(r.faculty, "name", ""), f"text{z}"),
            (r.course or "", f"num{z}"), (r.group, f"num{z}"), (r.phone, f"text{z}"),
            (r.user.username if r.user_id else "", f"text{z}"), (role, f"num{z}"),
        ])  # fmt: skip
    sheet.freeze = (header, 2)
    sheet.filter = f"A{header}:H{header + max(people, 1)}"
    return x.workbook([sheet], title=club.name, author=institution)
