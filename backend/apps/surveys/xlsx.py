"""Kichik Excel (.xlsx) yozuvchi: tashqi kutubxonasiz, toza OOXML.

Imkoniyatlari: bir nechta varaq, tayyor uslublar (sarlavha, jadval boshi, zebra qatorlar, foiz), ustun kengligi,
birlashtirilgan kataklar, qotirilgan qatorlar va avtofiltr.
"""

import io
import zipfile
from xml.sax.saxutils import escape

DARK, TEAL, CHART, LIGHT, TINT, ACCENT = "062D3B", "0E5A73", "008CA6", "F3F6F7", "E2F0F4", "FFF6E0"
INK, MUTED, LINE, PALE = "0B1D24", "5F747C", "DCE5E8", "C9DDE2"
FONT = "Arial"

# Uslub nomi -> cellXfs tartib raqami (pastdagi STYLES_XML bilan bir xil tartibda)
STYLE = {
    "default": 0,
    "title": 1,
    "subtitle": 2,
    "head": 3,
    "text": 4,
    "text_z": 5,
    "num": 6,
    "num_z": 7,
    "bold": 8,
    "bold_z": 9,
    "section": 10,
    "pct": 11,
    "bar": 12,
    "note": 13,
    "kpi_label": 14,
    "kpi_value": 15,
    "pct_z": 16,
    "bar_z": 17,
}

_FONTS = [
    (10, False, False, INK),
    (16, True, False, "FFFFFF"),
    (10, False, False, PALE),
    (10, True, False, "FFFFFF"),
    (10, True, False, INK),
    (11, True, False, TEAL),
    (10, False, False, CHART),
    (9, False, True, MUTED),
]
_FILLS = [None, "gray125", DARK, TEAL, LIGHT, TINT, ACCENT]
# (shrift, fon, chegara, gorizontal, vertikal, qator ko'chishi, raqam formati)
_XFS = [
    (0, 0, 0, None, None, False, 0),
    (1, 2, 0, None, "center", False, 0),
    (2, 2, 0, None, "center", False, 0),
    (3, 3, 1, "center", "center", True, 0),
    (0, 0, 1, None, "top", True, 0),
    (0, 4, 1, None, "top", True, 0),
    (0, 0, 1, "center", "top", False, 0),
    (0, 4, 1, "center", "top", False, 0),
    (4, 0, 1, None, "top", True, 0),
    (4, 4, 1, None, "top", True, 0),
    (5, 5, 0, None, "center", False, 0),
    (0, 0, 1, "center", "center", False, 9),
    (6, 0, 1, None, "center", False, 0),
    (7, 0, 0, None, "top", True, 0),
    (4, 6, 1, None, "center", False, 0),
    (5, 6, 1, "center", "center", False, 0),
    (0, 4, 1, "center", "center", False, 9),
    (6, 4, 1, None, "center", False, 0),
]


def _styles_xml():
    fonts = "".join(
        f'<font>{"<b/>" if bold else ""}{"<i/>" if italic else ""}<sz val="{size}"/><color rgb="FF{color}"/>'
        f'<name val="{FONT}"/></font>'
        for size, bold, italic, color in _FONTS
    )
    fills = []
    for fill in _FILLS:
        if fill is None:
            fills.append('<fill><patternFill patternType="none"/></fill>')
        elif fill == "gray125":
            fills.append('<fill><patternFill patternType="gray125"/></fill>')
        else:
            fills.append(
                f'<fill><patternFill patternType="solid"><fgColor rgb="FF{fill}"/>'
                '<bgColor indexed="64"/></patternFill></fill>'
            )
    side = f'style="thin"><color rgb="FF{LINE}"/>'
    borders = (
        "<border><left/><right/><top/><bottom/><diagonal/></border>"
        f"<border><left {side}</left><right {side}</right><top {side}</top><bottom {side}</bottom><diagonal/></border>"
    )
    xfs = []
    for font, fill, border, horizontal, vertical, wrap, numfmt in _XFS:
        attrs = f'numFmtId="{numfmt}" fontId="{font}" fillId="{fill}" borderId="{border}" xfId="0"'
        attrs += ' applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"'
        if numfmt:
            attrs += ' applyNumberFormat="1"'
        align = []
        if horizontal:
            align.append(f'horizontal="{horizontal}"')
        if vertical:
            align.append(f'vertical="{vertical}"')
        if wrap:
            align.append('wrapText="1"')
        xfs.append(f"<xf {attrs}><alignment {' '.join(align)}/></xf>")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<fonts count="{len(_FONTS)}">{fonts}</fonts><fills count="{len(_FILLS)}">{"".join(fills)}</fills>'
        f'<borders count="2">{borders}</borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        f'<cellXfs count="{len(xfs)}">{"".join(xfs)}</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def col_name(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    name = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


class Sheet:
    def __init__(self, name, *, tab_color=TEAL, landscape=True):
        for ch in "[]:*?/\\":
            name = name.replace(ch, " ")
        self.name = name[:31]
        self.tab_color = tab_color
        self.landscape = landscape
        self.rows = []  # (cells, height)
        self.widths = []
        self.merges = []
        self.freeze = None
        self.filter = None

    @property
    def next_row(self) -> int:
        return len(self.rows) + 1

    def add(self, cells, height=None):
        """cells: (qiymat, uslub) yoki None (bo'sh katak). Qator raqamini qaytaradi."""
        self.rows.append((cells, height))
        return len(self.rows)

    def blank(self, height=8):
        return self.add([], height)

    def merge(self, row, first_col, last_col):
        self.merges.append(f"{col_name(first_col)}{row}:{col_name(last_col)}{row}")

    def _cell(self, ref, value, style):
        s = STYLE[style]
        if value is None or value == "":
            return f'<c r="{ref}" s="{s}"/>'
        if isinstance(value, bool):
            value = "Ha" if value else "Yo'q"
        if isinstance(value, (int, float)):
            return f'<c r="{ref}" s="{s}"><v>{value}</v></c>'
        text = escape(str(value)).replace("\r", "")
        return f'<c r="{ref}" s="{s}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'

    def xml(self, index):
        rows = []
        width = max([len(cells) for cells, _ in self.rows] + [1])
        for number, (cells, height) in enumerate(self.rows, 1):
            attrs = f' ht="{height}" customHeight="1"' if height else ""
            body = "".join(
                self._cell(f"{col_name(i)}{number}", *(cell if cell else ("", "default")))
                for i, cell in enumerate(cells)
            )
            rows.append(f'<row r="{number}"{attrs}>{body}</row>')
        cols = "".join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>' for i, w in enumerate(self.widths, 1))
        pane = ""
        if self.freeze:
            row, col = self.freeze
            top_left = f"{col_name(col)}{row + 1}"
            attrs = (f'xSplit="{col}" ' if col else "") + (f'ySplit="{row}" ' if row else "")
            active = "bottomRight" if row and col else ("bottomLeft" if row else "topRight")
            pane = (
                f'<pane {attrs}topLeftCell="{top_left}" activePane="{active}" state="frozen"/>'
                f'<selection pane="{active}" activeCell="{top_left}" sqref="{top_left}"/>'
            )
        selected = ' tabSelected="1"' if index == 0 else ""
        merge_refs = "".join(f'<mergeCell ref="{m}"/>' for m in self.merges)
        merges = f'<mergeCells count="{len(self.merges)}">{merge_refs}</mergeCells>' if self.merges else ""
        auto = f'<autoFilter ref="{self.filter}"/>' if self.filter else ""
        orientation = "landscape" if self.landscape else "portrait"
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheetPr><tabColor rgb="FF{self.tab_color}"/><pageSetUpPr fitToPage="1"/></sheetPr>'
            f'<dimension ref="A1:{col_name(width - 1)}{max(len(self.rows), 1)}"/>'
            f'<sheetViews><sheetView showGridLines="0" workbookViewId="0"{selected}>{pane}</sheetView></sheetViews>'
            '<sheetFormatPr defaultRowHeight="18"/>'
            f"{'<cols>' + cols + '</cols>' if cols else ''}<sheetData>{''.join(rows)}</sheetData>{auto}{merges}"
            '<pageMargins left="0.4" right="0.4" top="0.5" bottom="0.5" header="0.3" footer="0.3"/>'
            f'<pageSetup paperSize="9" orientation="{orientation}" fitToWidth="1" fitToHeight="0"/>'
            "</worksheet>"
        )


def absolute(ref: str) -> str:
    """A4:K20 -> $A$4:$K$20."""
    parts = []
    for part in ref.split(":"):
        letters = "".join(ch for ch in part if ch.isalpha())
        parts.append(f"${letters}${part[len(letters) :]}")
    return ":".join(parts)


def workbook(sheets, *, title="", author="") -> bytes:
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    sheet_entries = "".join(
        f'<sheet name="{escape(s.name, {chr(34): "&quot;"})}" sheetId="{i}" r:id="rId{i}"/>'
        for i, s in enumerate(sheets, 1)
    )
    names = "".join(
        f'<definedName name="_xlnm._FilterDatabase" localSheetId="{i}" hidden="1">'
        f"'{escape(s.name)}'!{absolute(s.filter)}</definedName>"
        for i, s in enumerate(sheets)
        if s.filter
    )
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for i in range(1, len(sheets) + 1)
            )
            + '<Override PartName="/docProps/core.xml" '
            'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
            'Target="docProps/core.xml"/></Relationships>'
        ),
        "docProps/core.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f"<dc:title>{escape(title)}</dc:title><dc:creator>{escape(author)}</dc:creator></cp:coreProperties>"
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="{rel}">'
            f'<bookViews><workbookView activeTab="0"/></bookViews><sheets>{sheet_entries}</sheets>'
            f"{'<definedNames>' + names + '</definedNames>' if names else ''}</workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(
                f'<Relationship Id="rId{i}" Type="{rel}/worksheet" Target="worksheets/sheet{i}.xml"/>'
                for i in range(1, len(sheets) + 1)
            )
            + f'<Relationship Id="rId{len(sheets) + 1}" Type="{rel}/styles" Target="styles.xml"/></Relationships>'
        ),
        "xl/styles.xml": _styles_xml(),
    }
    for i, sheet in enumerate(sheets):
        files[f"xl/worksheets/sheet{i + 1}.xml"] = sheet.xml(i)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def title_block(sheet, title, subtitle, width):
    """Varaq boshidagi to'q rangli sarlavha (ikki qator) va bo'sh oraliq."""
    row = sheet.add([(title, "title")] + [("", "title")] * (width - 1), height=32)
    sheet.merge(row, 0, width - 1)
    row = sheet.add([(subtitle, "subtitle")] + [("", "subtitle")] * (width - 1), height=20)
    sheet.merge(row, 0, width - 1)
    sheet.blank()


def bar(share: float, length=20) -> str:
    """Katak ichidagi gorizontal ustun: 0..1 ulush."""
    filled = round(max(0.0, min(1.0, share)) * length)
    return "█" * filled + "░" * (length - filled) if share else ""
