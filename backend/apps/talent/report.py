"""Rektorat uchun hisobot: «Iqtidorli talabalar bilan ishlash holati». PDF (A4) va CSV."""

import csv
import io
from xml.sax.saxutils import escape

from django.utils import timezone

from apps.profiles.resume import _register_fonts

from .tracks import label

INK = "#0b2530"
MUTED = "#5f747c"
ACCENT = "#0e5a73"
LINE = "#dbe4e7"
SOFT = "#eef4f6"


def _d(value) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


def render_pdf(data: dict, institution) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    _register_fonts()
    base = ParagraphStyle("base", fontName="DejaVu", fontSize=9, leading=12, textColor=colors.HexColor(INK))
    small = ParagraphStyle("small", parent=base, fontSize=8, leading=10, textColor=colors.HexColor(MUTED))
    title = ParagraphStyle("title", parent=base, fontName="DejaVu-Bold", fontSize=15, leading=19, alignment=TA_CENTER)
    subtitle = ParagraphStyle("subtitle", parent=small, alignment=TA_CENTER, fontSize=9, leading=12)
    h2 = ParagraphStyle("h2", parent=base, fontName="DejaVu-Bold", fontSize=11, leading=14, spaceBefore=10,
                        spaceAfter=4, textColor=colors.HexColor(ACCENT))  # fmt: skip
    cell = ParagraphStyle("cell", parent=base, fontSize=8.5, leading=11)
    head = ParagraphStyle("head", parent=cell, fontName="DejaVu-Bold", textColor=colors.white)

    def p(text, style=cell):
        return Paragraph(escape(str(text)), style)

    def table(header, rows, widths, empty="Ma'lumot yo'q"):
        if not rows:
            return Paragraph(escape(empty), small)
        body = [[p(h, head) for h in header]] + [[p(c) for c in r] for r in rows]
        t = Table(body, colWidths=[w * mm for w in widths], repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(ACCENT)),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(SOFT)]),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor(LINE)),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return t

    totals = data["totals"]
    story = [
        Paragraph(escape(institution.name.upper()), subtitle),
        Spacer(1, 4),
        Paragraph("Iqtidorli talabalar bilan ishlash holati to'g'risida<br/>HISOBOT", title),
        Spacer(1, 4),
        Paragraph(
            escape(
                f"Davr: {_d(data['start'])} – {_d(data['end'])} · "
                f"Tuzilgan: {timezone.localtime(data['generated_at']):%d.%m.%Y %H:%M}"
            ),  # fmt: skip
            subtitle,
        ),
        Spacer(1, 10),
    ]

    kpis = [
        ("Reyestrda", totals["registry"], f"+{totals['new']} shu davrda"),
        ("Mentor biriktirilgan", totals["mentored"], f"{totals['mentored_pct']}%"),
        ("Rejasi bor", totals["planned"], f"{totals['planned_pct']}%"),
        ("Natijalar", totals["results"], f"{totals['result_students']} talaba"),
    ]
    kpi_style = ParagraphStyle("kpi", parent=base, fontName="DejaVu-Bold", fontSize=16, leading=19,
                               alignment=TA_CENTER, textColor=colors.HexColor(ACCENT))  # fmt: skip
    kpi_label = ParagraphStyle("kpil", parent=small, alignment=TA_CENTER)
    kpi_table = Table(
        [
            [Paragraph(str(v), kpi_style) for _, v, _ in kpis],
            [Paragraph(f"{escape(n)}<br/>{escape(d)}", kpi_label) for n, _, d in kpis],
        ],
        colWidths=[44 * mm] * 4,
    )
    kpi_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(LINE)),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor(LINE)),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(SOFT)),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(kpi_table)
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            escape(
                f"Rivojlanish rejalari: shu davrda {totals['goals_done']} ta maqsad bajarildi, "
                f"{totals['goals_open']} tasi jarayonda, shundan {totals['goals_overdue']} tasining muddati o'tgan. "
                f"Mentorsiz iqtidorlar: {totals['unattended']} nafar."
            ),
            base,
        )
    )

    story.append(Paragraph("1. Holat zanjiri", h2))
    story.append(table(["Holat", "Talabalar"], [[s["label"], s["count"]] for s in data["by_status"]], [120, 56]))

    story.append(Paragraph("2. Fakultetlar kesimida", h2))
    story.append(
        table(
            ["Fakultet", "Reyestr", "Mentorli", "Rejali", "Natijali"],
            [
                [r["name"], r["total"], f"{r['mentored']} ({r['mentored_pct']}%)", r["planned"], r["results"]]
                for r in data["by_faculty"]
            ],  # fmt: skip
            [76, 22, 30, 24, 24],
        )
    )

    story.append(Paragraph("3. Iqtidor yo'nalishlari", h2))
    story.append(
        table(
            ["Yo'nalish", "Reyestr", "Mentorli", "Natijali"],
            [[label(r["track"]), r["total"], r["mentored"], r["results"]] for r in data["by_track"]],
            [100, 26, 26, 24],
        )
    )

    story.append(Paragraph("4. Mentorlar faoliyati", h2))
    story.append(
        table(
            ["Mentor", "Shogirdlar", "Maqsadlar", "Bajarilgan", "Muddati o'tgan"],
            [[m["name"], m["mentees"], m["goals"], m["done"], m["overdue"]] for m in data["mentors"]],
            [70, 26, 26, 26, 28],
            "Hali mentor biriktirilmagan",
        )
    )

    story.append(Paragraph("5. Davr natijalari (olimpiada, hakaton, maqola, patent)", h2))
    story.append(
        table(
            ["Sana", "Talaba", "Fakultet", "Turi", "Natija"],
            [
                [
                    _d(r.achieved_on),
                    str(r.user),
                    r.user.faculty.short_name if r.user.faculty else "",
                    r.get_kind_display(),
                    r.title,
                ]
                for r in data["results"]
            ],  # fmt: skip
            [23, 38, 19, 26, 70],
            "Bu davrda tasdiqlangan natija yo'q",
        )
    )

    if data["unattended"]:
        story.append(
            KeepTogether(
                [
                    Paragraph("6. E'tibor talab qiladi: mentorsiz iqtidorlar", h2),
                    table(
                        ["Talaba", "Fakultet", "Yo'nalish", "Reyestrda"],
                        [
                            [
                                str(p.student),
                                p.student.faculty.short_name if p.student.faculty else "",
                                label(p.track),
                                _d(timezone.localdate(p.created_at)),
                            ]
                            for p in data["unattended"][:40]
                        ],  # fmt: skip
                        [60, 30, 56, 30],
                    ),
                ]
            )
        )

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("DejaVu", 7)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(18 * mm, 10 * mm, f"{institution.short_name} · Talent Hub · iqtidorlar reyestri")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}-bet")
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=17 * mm, rightMargin=17 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
        title="Iqtidorli talabalar bilan ishlash holati", author=institution.name,
    )  # fmt: skip
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def render_csv(data: dict) -> str:
    out = io.StringIO()
    out.write("﻿")
    w = csv.writer(out)
    t = data["totals"]
    w.writerow(["Iqtidorli talabalar bilan ishlash holati", f"{_d(data['start'])} – {_d(data['end'])}"])
    w.writerow([])
    w.writerow(["Ko'rsatkich", "Qiymat"])
    for name, key in [
        ("Reyestrda", "registry"), ("Shu davrda qo'shilgan", "new"), ("Mentor biriktirilgan", "mentored"),
        ("Rejasi bor", "planned"), ("Natijaga erishgan", "achieved"), ("Davr natijalari", "results"),
        ("Bajarilgan maqsadlar", "goals_done"), ("Muddati o'tgan maqsadlar", "goals_overdue"),
        ("Mentorsiz", "unattended"),
    ]:  # fmt: skip
        w.writerow([name, t[key]])
    w.writerow([])
    w.writerow(["Fakultet", "Reyestr", "Mentorli", "Rejali", "Natijali"])
    for r in data["by_faculty"]:
        w.writerow([r["name"], r["total"], r["mentored"], r["planned"], r["results"]])
    w.writerow([])
    w.writerow(["Mentor", "Shogirdlar", "Maqsadlar", "Bajarilgan", "Muddati o'tgan"])
    for m in data["mentors"]:
        w.writerow([m["name"], m["mentees"], m["goals"], m["done"], m["overdue"]])
    w.writerow([])
    w.writerow(["Sana", "Talaba", "Fakultet", "Turi", "Natija"])
    for r in data["results"]:
        w.writerow([_d(r.achieved_on), str(r.user), r.user.faculty.name if r.user.faculty else "",
                    r.get_kind_display(), r.title])  # fmt: skip
    return out.getvalue()
