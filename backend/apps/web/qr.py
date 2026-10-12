"""Internetsiz QR kod: reportlab kodlovchisi bilan ixcham SVG (bitta <path>)."""

from django.utils.html import format_html
from reportlab.graphics.barcode import qrencoder


def qr_svg(text: str, size: int = 240, label: str = "QR kod") -> str:
    qr = qrencoder.QRCode(None, qrencoder.QRErrorCorrectLevel.M)
    qr.addData(text)
    qr.make()
    count = qr.getModuleCount()
    quiet = 4  # skanerlar uchun atrofdagi oq hoshiya (modul soni)
    path = "".join(
        f"M{col + quiet} {row + quiet}h1v1h-1z" for row in range(count) for col in range(count) if qr.isDark(row, col)
    )
    full = count + 2 * quiet
    return format_html(
        '<svg class="qr-svg" width="{}" height="{}" viewBox="0 0 {} {}" role="img" aria-label="{}" '
        'shape-rendering="crispEdges"><rect width="100%" height="100%" fill="#fff"/><path d="{}" fill="#000"/></svg>',
        size,
        size,
        full,
        full,
        label,
        path,
    )
