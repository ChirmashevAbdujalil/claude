"""So'rovnoma natijalari bo'yicha Word (.docx) hisobot: rahbariyat yig'ilishi yoki yuqori tashkilot uchun.

Tarkibi: asosiy ko'rsatkichlar, xulosalar, fakultetlar va tyutorlar kesimi, har bir savol bo'yicha natija
(variantlar ulushi chiziqli diagramma bilan, matnli javoblardan namunalar), klublar va imzo joyi.
"""

from django.utils import timezone

from . import analytics, clubs, services
from .docx import DARK, LIGHT, LINE, MUTED, TEAL, _banner, _borders, _cell, _note, _p, _row, _run, _table, package
from .models import Question

Kind = Question.Kind
WIDTH = 10466  # A4 kitob varaq, 1,27 sm hoshiya
GOLD = "F59E0B"
SOFT = "E2F0F4"
TEXT_SAMPLES = 8


def _heading(text, *, number=None):
    runs = []
    if number is not None:
        runs.append(_run(f"{number}  ", bold=True, size=13, color=GOLD))
    runs.append(_run(text, bold=True, size=13, color=DARK))
    return _p(*runs, before=320, after=120, keep=True)


def _subheading(text, extra=""):
    runs = [_run(text, bold=True, size=11, color=DARK)]
    if extra:
        runs.append(_run(f"   {extra}", size=8.5, color=MUTED))
    return _p(*runs, before=220, after=80, keep=True)


def _bar(share, width):
    """Jadval katagidagi chiziqli diagramma: to'lgan qismi rangli, qolgani och."""
    share = max(0.0, min(1.0, share))
    filled = round(width * share)
    empty = width - filled
    cells, widths = [], []
    tiny = '<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="120" w:lineRule="exact"/></w:pPr></w:p>'
    for part, fill in ((filled, TEAL), (empty, SOFT)):
        if part > 0:
            cells.append(_cell(tiny, part, fill=fill, borders=_borders("FFFFFF", style="nil")))
            widths.append(part)
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    nil = "".join(f'<w:{side} w:val="nil"/>' for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
    return (
        f'<w:tbl><w:tblPr><w:tblW w:w="{width}" w:type="dxa"/><w:tblLayout w:type="fixed"/>'
        f"<w:tblBorders>{nil}</w:tblBorders>"
        '<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="0" w:type="dxa"/>'
        '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="0" w:type="dxa"/></w:tblCellMar></w:tblPr>'
        f'<w:tblGrid>{grid}</w:tblGrid><w:tr><w:trPr><w:trHeight w:val="150" w:hRule="exact"/></w:trPr>'
        f"{''.join(cells)}</w:tr></w:tbl>" + tiny  # Word katak oxirida paragraf bo'lishini talab qiladi
    )


def _head_row(titles, widths):
    return _row(
        [
            _cell(_p(_run(t, bold=True, size=8.5, color="FFFFFF"), align=a), w, fill=TEAL)
            for (t, a), w in zip(titles, widths, strict=True)
        ],
        header=True,
        height=380,
    )


def _kpis(items):
    width = WIDTH // len(items)
    cells = []
    for value, label, fill in items:
        content = _p(_run(value, bold=True, size=20, color=DARK), align="center") + _p(
            _run(label, size=8.5, color=MUTED), align="center"
        )
        cells.append(_cell(content, width, fill=fill, borders=_borders("FFFFFF", size=24), margins=(160, 80, 160, 80)))
    return _table([_row(cells)], [width] * len(items), borders=False)


def _bars_table(bars, *, value_label="Soni"):
    widths = [3900, 900, 900, 4766]
    rows = [_head_row([("Variant", "left"), (value_label, "center"), ("Ulushi", "center"), ("", "left")], widths)]
    top = max([b["count"] for b in bars] + [1])
    for index, bar in enumerate(bars):
        fill = LIGHT if index % 2 else None
        best = bar["count"] == top and bar["count"] > 0
        rows.append(
            _row(
                [
                    _cell(_p(_run(bar["label"], bold=best, size=9.5)), widths[0], fill=fill),
                    _cell(_p(_run(bar["count"], bold=True, size=9.5), align="center"), widths[1], fill=fill),
                    _cell(_p(_run(f"{bar['pct']}%", size=9, color=MUTED), align="center"), widths[2], fill=fill),
                    _cell(_bar(bar["count"] / top, widths[3] - 200), widths[3], fill=fill),
                ],
                height=330,
            )
        )
    return _table(rows, widths)


def _faculties(data):
    rows = data["rows"]
    contingent = data["has_contingent"]
    widths = [500, 3700, 1000, 1050, 1050] + ([1150, 2016] if contingent else [3166])
    titles = [("№", "center"), ("Fakultet", "left"), ("Javob", "center"), ("Akkaunt", "center"), ("Kirgan", "center")]
    titles += [("Qamrov", "center"), ("", "left")] if contingent else [("", "left")]
    table = [_head_row(titles, widths)]
    top = max([r["total"] for r in rows] + [1])
    for index, r in enumerate(rows, 1):
        fill = LIGHT if index % 2 == 0 else None
        cells = [
            _p(_run(r["medal"] or index, size=9, color=MUTED), align="center"),
            _p(_run(r["name"], bold=True, size=9.5)),
            _p(_run(r["total"], bold=True, size=10), align="center"),
            _p(_run(r["accounts"], size=9.5), align="center"),
            _p(_run(r["logged"], size=9.5), align="center"),
        ]
        if contingent:
            cover = f"{r['coverage']}%" if r["coverage"] is not None else "—"
            cells.append(_p(_run(cover, bold=True, size=9.5, color=TEAL), align="center"))
        bar_width = widths[-1]
        cells.append(_bar(r["total"] / top, bar_width - 200))
        table.append(_row([_cell(c, w, fill=fill) for c, w in zip(cells, widths, strict=True)], height=340))
    t = data["totals"]
    total_cells = ["", "Jami", t["total"], t["accounts"], t["logged"]]
    if contingent:
        total_cells.append(f"{t['coverage']}%" if t["coverage"] is not None else "—")
    total_cells.append("")
    table.append(
        _row(
            [
                _cell(_p(_run(v, bold=True, size=9.5, color=DARK), align="left" if i == 1 else "center"), w, fill=SOFT)
                for i, (v, w) in enumerate(zip(total_cells, widths, strict=True))
            ],
            height=340,
        )
    )
    return _table(table, widths)


def _tutors(data):
    widths = [2300, 4200, 1000, 2966]
    parts = []
    table = [_head_row([("Fakultet", "left"), ("Tyutor", "left"), ("Talaba", "center"), ("", "left")], widths)]
    top = max([t["total"] for g in data["faculties"] for t in g["tutors"]] + [1])
    index = 0
    for group in data["faculties"]:
        for tutor in group["tutors"]:
            index += 1
            fill = LIGHT if index % 2 == 0 else None
            color = None if tutor["total"] else MUTED
            name = f"{tutor.get('medal', '')} {tutor['name']}".strip()
            cells = [
                (_p(_run(group["faculty"].short_name, size=9, color=MUTED)), widths[0]),
                (_p(_run(name, size=9.5, color=color)), widths[1]),
                (_p(_run(tutor["total"], bold=True, size=9.5, color=color), align="center"), widths[2]),
                (_bar(tutor["total"] / top, widths[3] - 200), widths[3]),
            ]
            table.append(_row([_cell(content, width, fill=fill) for content, width in cells], height=310))
    parts.append(_table(table, widths))
    silent = [f"{g['faculty'].short_name}: {g['silent']}" for g in data["faculties"] if g["silent"]]
    if silent:
        parts.append(
            _p(_run("Javobi hali yo'q tyutorlar soni — " + ", ".join(silent), size=8.5, color=MUTED), before=80)
        )
    return "".join(parts)


def _question_block(number, block, total):
    question = block["question"]
    extra = f"{block['answered']} ta javob" + (
        f" · {block['skipped']} kishi o'tkazib yuborgan" if block["skipped"] else ""
    )
    if block.get("average") is not None:
        extra += f" · o'rtacha {block['average']}" + (f" / {question.scale_max}" if question.kind == Kind.SCALE else "")
    parts = [_subheading(f"{number}. {question.title}", extra)]
    if question.kind == Kind.FILE:
        files = block.get("files") or {}
        if files.get("count"):
            parts.append(_p(_run(f"Yuklangan fayllar: {files['count']} ta, umumiy hajmi {files['size']}.", size=9.5)))
            parts.append(_bars_table(files["bars"], value_label="Fayl"))
        else:
            parts.append(_p(_run("Fayl yuklanmagan.", size=9, color=MUTED, italic=True)))
    elif block.get("bars"):
        parts.append(_bars_table(block["bars"]))
        if block.get("others"):
            sample = "; ".join(block["others"][:10])
            parts.append(_p(_run("«Boshqa» javoblari: ", bold=True, size=8.5, color=MUTED), _run(sample, size=8.5),
                            before=60))  # fmt: skip
    elif block.get("texts"):
        if block.get("min") is not None:
            parts.append(_p(_run(f"Eng kichik: {block['min']} · eng katta: {block['max']}", size=9.5)))
        for text in block["texts"][:TEXT_SAMPLES]:
            parts.append(
                _table(
                    [
                        _row(
                            [
                                _cell(
                                    _p(_run(f"«{text}»", size=9.5, italic=True)),
                                    WIDTH,
                                    fill=LIGHT,
                                    borders=_borders(LINE),
                                    margins=(70, 160, 70, 160),
                                )
                            ]
                        )
                    ],
                    [WIDTH],
                    borders=False,
                )  # fmt: skip
                + _p(after=40)
            )
        rest = block["answered"] - min(len(block["texts"]), TEXT_SAMPLES)
        if rest > 0:
            parts.append(_p(_run(f"… va yana {rest} ta javob (to'liq ro'yxat Excel faylida).", size=8.5,
                                 color=MUTED, italic=True)))  # fmt: skip
    else:
        parts.append(_p(_run("Javob yo'q.", size=9, color=MUTED, italic=True)))
    return "".join(parts)


def _clubs(rows):
    widths = [4200, 1300, 2300, 2666]
    table = [_head_row([("Klub", "left"), ("A'zolar", "center"), ("Sardor", "left"), ("Mentor", "left")], widths)]
    for index, row in enumerate(rows, 1):
        club = row["club"]
        fill = LIGHT if index % 2 == 0 else None
        table.append(
            _row(
                [
                    _cell(_p(_run(f"{club.emoji} {club.name}", bold=True, size=9.5)), widths[0], fill=fill),
                    _cell(_p(_run(row["count"], bold=True, size=10), align="center"), widths[1], fill=fill),
                    _cell(_p(_run(str(club.leader) if club.leader else "—", size=9)), widths[2], fill=fill),
                    _cell(_p(_run(str(club.mentor) if club.mentor else "—", size=9)), widths[3], fill=fill),
                ],
                height=330,
            )
        )
    return _table(table, widths)


def render(survey, responses, *, institution, prepared_by="", conditions=(), faculties=None, tutors=None) -> bytes:
    data = services.summary(survey, responses)
    timeline = analytics.timeline(responses)
    complete = analytics.completeness(survey, responses)
    insights = analytics.insights(survey, responses, data, timeline, complete)
    now = timezone.localtime()
    total = data["total"]

    subtitle = (
        f"Natijalar hisoboti · {institution} · holat: {survey.get_status_display().lower()} · {now:%d.%m.%Y %H:%M}"
    )
    parts = [_banner(survey.title, subtitle, WIDTH), _p(after=160)]
    if conditions:
        labels = ", ".join(f"{c['question'].title}: {c['label']}" for c in conditions)
        parts += [_note(f"Hisobot faqat quyidagi javobni berganlar bo'yicha: {labels}", WIDTH), _p(after=160)]
    reg = analytics.faculty_registration(responses, faculties) if survey.collect_identity and faculties else None
    coverage = reg["totals"]["coverage"] if reg and reg["totals"]["coverage"] is not None else None
    parts.append(
        _kpis(
            [
                (str(total), "javob", SOFT),
                (str(data["linked"]), "platformadagi talaba", LIGHT),
                (f"{complete['average']}%", "o'rtacha to'liqlik", LIGHT),
                (
                    f"{coverage}%" if coverage is not None else str(timeline.get("week", 0)),
                    "kontingent qamrovi" if coverage is not None else "so'nggi 7 kunda",
                    "FFF6E0",
                ),
            ]
        )  # fmt: skip
    )

    if insights:
        parts.append(_heading("Asosiy xulosalar", number="I"))
        for item in insights:
            parts.append(_p(_run(f"{item['icon']}  ", size=10), _run(item["text"], size=10), after=70))

    section = 2
    if reg and reg["rows"]:
        parts.append(_heading("Fakultetlar kesimida", number="II"))
        parts.append(_faculties(reg))
        if reg["silent"]:
            parts.append(_p(_run("Javob kelmagan fakultetlar: " + ", ".join(reg["silent"]), size=8.5, color=MUTED),
                            before=80))  # fmt: skip
        section += 1
    if survey.collect_identity and tutors:
        tutor_data = analytics.tutor_registration(responses, tutors)
        if tutor_data["faculties"]:
            parts.append(_heading("Tyutorlar kesimida", number=_roman(section)))
            leader = tutor_data["leader"]
            if leader:
                parts.append(_p(_run("Eng faol tyutor: ", size=9.5, color=MUTED),
                                _run(f"{leader['name']} — {leader['total']} ta talaba", bold=True, size=9.5),
                                after=100))  # fmt: skip
            parts.append(_tutors(tutor_data))
            section += 1

    parts.append(_heading("Savollar bo'yicha natijalar", number=_roman(section)))
    section += 1
    number = 0
    for block in data["blocks"]:
        if block.get("section"):
            parts.append(_p(_run(block["question"].title.upper(), bold=True, size=9, color=TEAL), before=260, after=20,
                            keep=True))  # fmt: skip
            continue
        number += 1
        parts.append(_question_block(number, block, total))

    club_rows = clubs.overview(survey)
    if club_rows:
        parts.append(_heading("Tuzilgan klublar", number=_roman(section)))
        parts.append(_clubs(club_rows))

    parts.append(
        _p(
            _run(
                f"Hisobotni tayyorladi: {prepared_by or '________________'}   ____________ (imzo)",
                size=9.5,
                color=MUTED,
            ),
            before=480,
        )  # fmt: skip
    )
    parts.append(_p(_run(f"Sana: {now:%d.%m.%Y}", size=9.5, color=MUTED), before=80))
    return package(
        "".join(parts),
        landscape=False,
        title=f"{survey.title} — hisobot",
        author=institution,
        footer=f"{institution} · so'rovnoma natijalari hisoboti",
    )


def _roman(n):
    return ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII"][n] if n < 9 else str(n)
