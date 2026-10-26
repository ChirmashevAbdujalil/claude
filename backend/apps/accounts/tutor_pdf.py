"""Tyutorlarning kabinetga kirish login-parollari: PDF (A4). Dizayni Word fayl bilan bir xil."""

import io
from xml.sax.saxutils import escape

from apps.profiles.resume import _register_fonts

DARK = "#062d3b"
TEAL = "#0e5a73"
LIGHT = "#f3f6f7"
ACCENT = "#fff6e0"
MUTED = "#5f747c"
DASH = "#9fb3ba"
NO_FACULTY = "Fakultet ko'rsatilmagan"
MONO = "Courier-Bold"  # login va parol faqat lotin harf va raqamlardan iborat


def render(rows, *, institution, site, subtitle) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    _register_fonts()
    color = colors.HexColor
    base = ParagraphStyle("base", fontName="DejaVu", fontSize=9, leading=12, textColor=color(DARK))
    small = ParagraphStyle("small", parent=base, fontSize=7.5, leading=10, textColor=color(MUTED))
    bold = ParagraphStyle("bold", parent=base, fontName="DejaVu-Bold")
    login_url, cabinet_url = f"{site}/login/", f"{site}/tyutor/"
    width = A4[0] - 24 * mm

    def p(text, style=base, **kw):
        return Paragraph(text, ParagraphStyle(f"s{id(text)}", parent=style, **kw) if kw else style)

    def box(content, widths, styles):
        table = Table(content, colWidths=widths)
        table.setStyle(TableStyle(styles))
        return table

    story = [
        box(
            [[p("Tyutorlar kabineti: login va parollar", bold, fontSize=17, leading=22, textColor=colors.white)],
             [p(escape(subtitle), base, fontSize=9.5, textColor=color("#c9dde2"))]],
            [width],
            [("BACKGROUND", (0, 0), (-1, -1), color(DARK)), ("LEFTPADDING", (0, 0), (-1, -1), 14),
             ("TOPPADDING", (0, 0), (0, 0), 12), ("BOTTOMPADDING", (0, -1), (-1, -1), 12)],
        ),
        Spacer(1, 10),
        p("Kabinetga qanday kiriladi", bold, fontSize=11, leading=14, spaceAfter=5),
    ]  # fmt: skip
    steps = [
        ("Saytni oching", f"Brauzerda {login_url} manzilini oching"),
        ("Tizimga kiring", "Kartochkadagi login va parolni yozing"),
        ("Parolni almashtiring", "Birinchi kirishda o'zingiz biladigan yangi parol o'rnatasiz"),
        ("Kabinetga o'ting", "Menyudagi «Tyutor kabineti» bo'limini bosing"),
    ]
    step_cells = [
        [p(str(n), bold, fontSize=18, leading=22, textColor=color(TEAL)), p(escape(title), bold, fontSize=9),
         p(escape(text), small, fontSize=8, leading=10.5)]
        for n, (title, text) in enumerate(steps, 1)
    ]  # fmt: skip
    story += [
        box(
            [step_cells],
            [width / 4] * 4,
            [("BACKGROUND", (0, 0), (-1, -1), color(LIGHT)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("GRID", (0, 0), (-1, -1), 3, colors.white), ("TOPPADDING", (0, 0), (-1, -1), 8),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 9)],
        ),
        Spacer(1, 7),
        p("<b>Kabinetda:</b> " + escape(
            "guruhingiz talabalarining so'rovnoma javoblari, ularning login-parollari (Word), talabaga yangi parol "
            "berish, so'rovnomaning shaxsiy havolasi va QR-kodi: shu havola orqali javob bergan talaba avtomatik "
            "sizga biriktiriladi."), small, fontSize=8.5, leading=11.5, textColor=color(MUTED)),
        Spacer(1, 7),
        box(
            [[p(escape("Kartochkalarni punktir chiziq bo'ylab qirqing va har bir tyutorga faqat o'zinikini topshiring. "
                       "Parolni Telegram guruhlarga tashlamang."), base, fontSize=8.5, textColor=color("#7a4a0b"))]],
            [width],
            [("BACKGROUND", (0, 0), (-1, -1), color(ACCENT)), ("LEFTPADDING", (0, 0), (-1, -1), 10),
             ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)],
        ),
        Spacer(1, 6),
    ]  # fmt: skip

    col = width / 2
    inner = col - 20

    def card(row):
        place = row["faculty_short"] or row["faculty"] or "—"
        creds = box(
            [[p("Login", small), p(escape(row["login"]), base, fontName=MONO, fontSize=11, leading=13)],
             [p("Parol", small), p(escape(row["password"]), base, fontName=MONO, fontSize=11, leading=13)]],
            [16 * mm, inner - 16 * mm],
            [("BACKGROUND", (0, 0), (-1, 0), color(LIGHT)), ("BACKGROUND", (0, 1), (-1, 1), color(ACCENT)),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 5)],
        )  # fmt: skip
        return [
            p(escape(institution), bold, fontSize=7.5, leading=10, textColor=color(TEAL)),
            p(escape(row["name"]), bold, fontSize=12.5, leading=16),
            p(escape(f"Tyutor · {place}"), small, spaceAfter=5),
            creds,
            Spacer(1, 5),
            p(f"Kirish: <font color='{TEAL}'><b>{escape(login_url)}</b></font>", small),
            p(f"Kabinet: <font color='{TEAL}'><b>{escape(cabinet_url)}</b></font>", small),
        ]

    groups = []
    for row in rows:
        if not groups or groups[-1][0] != row["faculty"]:
            groups.append((row["faculty"], []))
        groups[-1][1].append(row)
    for faculty, items in groups:
        heading = p(
            escape(f"{faculty or NO_FACULTY} · {len(items)} nafar"),
            bold, fontSize=10, leading=13, textColor=color(TEAL), spaceBefore=8, spaceAfter=4,
        )  # fmt: skip
        pairs = [items[i : i + 2] for i in range(0, len(items), 2)]
        for number, pair in enumerate(pairs):
            cells = [card(r) for r in pair] + ([""] if len(pair) == 1 else [])
            dashed = [("BOX", (i, 0), (i, 0), 0.7, color(DASH), None, (3, 2)) for i in range(len(pair))]
            table = box(
                [cells],
                [col, col],
                [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                 ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 9),
                 ("BOTTOMPADDING", (0, 0), (-1, -1), 9), *dashed],
            )  # fmt: skip
            story.append(KeepTogether([heading, table]) if number == 0 else table)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("DejaVu", 7.5)
        canvas.setFillColor(color(MUTED))
        canvas.drawCentredString(A4[0] / 2, 8 * mm, f"Maxfiy: faqat tyutorning o'ziga topshiring · sahifa {doc.page}")
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=15 * mm,
        title="Tyutorlar: login va parollar",
        author=institution,
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
