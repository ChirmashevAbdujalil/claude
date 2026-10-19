"""Login va parollar ro'yxatini Word (.docx) faylga yozish: tashqi kutubxonasiz, toza OOXML.

Ikki ko'rinish:
- table: fakultetlar bo'yicha guruhlangan jadval (albom varaq), «Oldim» imzosi ustuni bilan;
- cards: har bir talaba uchun qirqib beriladigan kartochka (kitob varaq, 2 ustun).
"""

import io
import zipfile
from xml.sax.saxutils import escape

DARK = "062D3B"
TEAL = "0E5A73"
LIGHT = "F3F6F7"
LINE = "DCE5E8"
ACCENT = "FFF6E0"
MUTED = "5F747C"
FONT = "Arial"
MONO = "Consolas"

OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE = "http://schemas.openxmlformats.org/package/2006"
WORD_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml"

W_NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
)


def _run(text, *, bold=False, size=10, color=None, font=None, italic=False):
    props = [f'<w:rFonts w:ascii="{font or FONT}" w:hAnsi="{font or FONT}" w:cs="{font or FONT}"/>']
    if bold:
        props.append("<w:b/>")
    if italic:
        props.append("<w:i/>")
    if color:
        props.append(f'<w:color w:val="{color}"/>')
    props.append(f'<w:sz w:val="{int(size * 2)}"/><w:szCs w:val="{int(size * 2)}"/>')
    return f'<w:r><w:rPr>{"".join(props)}</w:rPr><w:t xml:space="preserve">{escape(str(text))}</w:t></w:r>'


def _p(*runs, align="left", before=0, after=0, keep=False):
    jc = {"left": "left", "center": "center", "right": "right"}[align]
    keep_xml = "<w:keepNext/>" if keep else ""
    return (
        f'<w:p><w:pPr>{keep_xml}<w:spacing w:before="{before}" w:after="{after}" w:line="264" w:lineRule="auto"/>'
        f'<w:jc w:val="{jc}"/></w:pPr>{"".join(runs)}</w:p>'
    )


def _borders(color=LINE, size=4, style="single"):
    sides = "".join(
        f'<w:{side} w:val="{style}" w:sz="{size}" w:space="0" w:color="{color}"/>'
        for side in ("top", "left", "bottom", "right")
    )
    return f"<w:tcBorders>{sides}</w:tcBorders>"


def _cell(content, width, *, fill=None, span=1, borders="", valign="center", margins=None):
    shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
    grid = f'<w:gridSpan w:val="{span}"/>' if span > 1 else ""
    mar = ""
    if margins:
        top, left, bottom, right = margins
        mar = (
            f'<w:tcMar><w:top w:w="{top}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/>'
            f'<w:bottom w:w="{bottom}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>'
        )
    return (
        f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{grid}{borders}{shd}{mar}'
        f'<w:vAlign w:val="{valign}"/></w:tcPr>{content}</w:tc>'
    )


def _row(cells, *, header=False, height=None, cant_split=True):
    props = []
    if header:
        props.append("<w:tblHeader/>")
    if cant_split:
        props.append("<w:cantSplit/>")
    if height:
        props.append(f'<w:trHeight w:val="{height}" w:hRule="atLeast"/>')
    return f"<w:tr><w:trPr>{''.join(props)}</w:trPr>{''.join(cells)}</w:tr>"


def _table(rows, widths, *, borders=True):
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    edge = (
        "".join(
            f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="{LINE}"/>'
            for side in ("top", "left", "bottom", "right", "insideH", "insideV")
        )
        if borders
        else "".join(f'<w:{side} w:val="nil"/>' for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
    )
    return (
        f'<w:tbl><w:tblPr><w:tblW w:w="{sum(widths)}" w:type="dxa"/><w:tblLayout w:type="fixed"/>'
        f"<w:tblBorders>{edge}</w:tblBorders>"
        f'<w:tblCellMar><w:top w:w="60" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
        f'<w:bottom w:w="60" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr>'
        f"<w:tblGrid>{grid}</w:tblGrid>{''.join(rows)}</w:tbl>"
    )


def _banner(title, subtitle, width):
    content = _p(_run(title, bold=True, size=17, color="FFFFFF"), after=40) + _p(
        _run(subtitle, size=9.5, color="C9DDE2")
    )
    cell = _cell(content, width, fill=DARK, margins=(220, 260, 220, 260), borders=_borders(DARK))
    return _table([_row([cell])], [width], borders=False)


def _note(text, width):
    cell = _cell(
        _p(_run(text, size=9, color="7A4A0B")),
        width,
        fill=ACCENT,
        margins=(110, 200, 110, 200),
        borders=_borders(ACCENT),
    )
    return _table([_row([cell])], [width], borders=False)


def _footer():
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr {W_NS}>'
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
        + _run("Maxfiy: faqat talabaning o'ziga topshiring · ", size=8, color=MUTED)
        + _run("sahifa ", size=8, color=MUTED)
        + f'<w:r><w:rPr><w:color w:val="{MUTED}"/><w:sz w:val="16"/></w:rPr>'
        '<w:fldChar w:fldCharType="begin"/></w:r>'
        f'<w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
        '<w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:fldChar w:fldCharType="end"/></w:r>'
        "</w:p></w:ftr>"
    )


def _section(landscape):
    w, h = (16838, 11906) if landscape else (11906, 16838)
    orient = ' w:orient="landscape"' if landscape else ""
    return (
        f'<w:sectPr><w:footerReference w:type="default" r:id="rIdFooter"/>'
        f'<w:pgSz w:w="{w}" w:h="{h}"{orient}/>'
        '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="360" w:footer="360" w:gutter="0"/>'
        "</w:sectPr>"
    )


# ---------------------------------------------------------------- ko'rinishlar


def _table_body(rows, meta):
    widths = [520, 3500, 2900, 800, 1250, 2550, 1900, 1978]  # albom: jami 15398
    total = sum(widths)
    parts = [
        _banner("Talabalar uchun login va parollar", meta["subtitle"], total),
        _p(after=120),
        _note(meta["note"], total),
        _p(after=120),
    ]
    head = ["№", "Familiya, ism", "Fakultet", "Kurs", "Guruh", "Login", "Parol", "Oldim (imzo)"]
    table_rows = [
        _row(
            [
                _cell(_p(_run(h, bold=True, size=9, color="FFFFFF")), w, fill=TEAL)
                for h, w in zip(head, widths, strict=True)
            ],
            header=True,
            height=420,
        )
    ]
    current = None
    for index, row in enumerate(rows, 1):
        if row["faculty"] != current:
            current = row["faculty"]
            label = _p(_run(current or "Fakultet ko'rsatilmagan", bold=True, size=9.5, color=TEAL), keep=True)
            table_rows.append(_row([_cell(label, total, fill="E2F0F4", span=len(widths))], height=360))
        fill = LIGHT if index % 2 == 0 else None
        password = (
            _run(row["password"], bold=True, size=10.5, font=MONO, color=DARK)
            if row["password"]
            else _run("talaba kirgan", italic=True, size=8.5, color=MUTED)
        )
        cells = [
            _p(_run(index, size=9, color=MUTED), align="center"),
            _p(_run(row["name"], bold=True, size=10))
            + (_p(_run(row["phone"], size=8, color=MUTED)) if row["phone"] else ""),
            _p(_run(row["faculty_short"] or "—", size=9)),
            _p(_run(row["course"] or "—", size=9), align="center"),
            _p(_run(row["group"] or "—", size=9)),
            _p(_run(row["login"], bold=True, size=10.5, font=MONO, color=DARK)),
            _p(password),
            _p(_run("", size=9)),
        ]
        table_rows.append(_row([_cell(c, w, fill=fill) for c, w in zip(cells, widths, strict=True)], height=440))
    parts.append(_table(table_rows, widths))
    parts.append(_p(_run(meta["signature"], size=9, color=MUTED), before=240))
    return "".join(parts), True


def _card(row, meta, width):
    lines = [
        _p(_run(meta["institution"], bold=True, size=8, color=TEAL), after=40),
        _p(_run(row["name"], bold=True, size=13, color=DARK), after=20),
        _p(
            _run(
                " · ".join(
                    filter(None, [row["faculty_short"], f"{row['course']}-kurs" if row["course"] else "", row["group"]])
                )
                or " ",
                size=8.5,
                color=MUTED,
            ),
            after=120,
        ),
    ]
    creds = _table(
        [
            _row(
                [
                    _cell(_p(_run("Login", size=8, color=MUTED)), 1100, fill=LIGHT),
                    _cell(_p(_run(row["login"], bold=True, size=12, font=MONO, color=DARK)), width - 1500, fill=LIGHT),
                ]
            ),
            _row(
                [
                    _cell(_p(_run("Parol", size=8, color=MUTED)), 1100, fill=ACCENT),
                    _cell(
                        _p(
                            _run(
                                row["password"] or "talaba kirgan",
                                bold=bool(row["password"]),
                                size=12 if row["password"] else 9,
                                font=MONO if row["password"] else None,
                                color=DARK if row["password"] else MUTED,
                                italic=not row["password"],
                            )
                        ),
                        width - 1500,
                        fill=ACCENT,
                    ),
                ]
            ),
        ],
        [1100, width - 1500],
        borders=False,
    )
    tail = _p(
        _run("Kirish: ", size=8, color=MUTED), _run(meta["site"], bold=True, size=8, color=TEAL), before=100
    ) + _p(_run("Birinchi kirishda o'zingizning yangi parolingizni o'rnatasiz.", size=7.5, color=MUTED, italic=True))
    return "".join(lines) + creds + tail


def _cards_body(rows, meta):
    total = 10466  # kitob varaq
    col = total // 2
    parts = [
        _banner("Login va parollar: kartochkalar", meta["subtitle"], total),
        _p(after=100),
        _note("Kartochkalarni punktir chiziq bo'ylab qirqing va har bir talabaga o'zinikini topshiring.", total),
        _p(after=120),
    ]
    dashed = _borders("9FB3BA", size=6, style="dashed")
    table_rows = []
    for i in range(0, len(rows), 2):
        pair = rows[i : i + 2]
        cells = [
            _cell(_card(r, meta, col - 400), col, borders=dashed, valign="top", margins=(200, 200, 200, 200))
            for r in pair
        ]
        if len(pair) == 1:
            cells.append(_cell(_p(_run("")), col, borders=_borders("FFFFFF", style="nil")))
        table_rows.append(_row(cells))
    parts.append(_table(table_rows, [col, total - col], borders=False))
    return "".join(parts), False


def render(rows, *, layout, institution, site, subtitle, signature) -> bytes:
    meta = {
        "institution": institution,
        "site": site,
        "subtitle": subtitle,
        "signature": signature,
        "note": (
            f"Talaba {site} manziliga kirib, shu login va parol bilan tizimga kiradi va birinchi kirishda o'z parolini "
            "o'rnatadi. Ro'yxat maxfiy: har bir talabaga faqat o'z ma'lumotini bering."
        ),
    }
    body, landscape = (_cards_body if layout == "cards" else _table_body)(rows, meta)
    document = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W_NS}><w:body>'
        f"{body}{_section(landscape)}</w:body></w:document>"
    )
    styles = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {W_NS}><w:docDefaults><w:rPrDefault><w:rPr>'
        f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}" w:eastAsia="{FONT}"/><w:sz w:val="20"/>'
        '<w:lang w:val="uz-Latn-UZ"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="0"/></w:pPr>'
        "</w:pPrDefault></w:docDefaults></w:styles>"
    )
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '<Override PartName="/word/footer1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
            '<Override PartName="/docProps/core.xml" '
            'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{OFFICE_REL}/officeDocument" '
            'Target="word/document.xml"/>'
            f'<Relationship Id="rId2" Type="{PACKAGE}/relationships/metadata/core-properties" '
            'Target="docProps/core.xml"/></Relationships>'
        ),
        "word/_rels/document.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rIdStyles" Type="{OFFICE_REL}/styles" '
            'Target="styles.xml"/>'
            f'<Relationship Id="rIdFooter" Type="{OFFICE_REL}/footer" '
            'Target="footer1.xml"/></Relationships>'
        ),
        "docProps/core.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f"<dc:title>Login va parollar</dc:title><dc:creator>{escape(institution)}</dc:creator></cp:coreProperties>"
        ),
        "word/document.xml": document,
        "word/styles.xml": styles,
        "word/footer1.xml": _footer(),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()
