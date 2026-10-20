from django.http import HttpResponse

from . import files

PAGE = (
    '<!doctype html><html lang="uz"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
    '<title>Fayl juda katta</title><body style="font-family:system-ui;max-width:520px;margin:15vh auto;padding:0 16px">'
    f"<h1>Fayllar hajmi juda katta</h1><p>Bitta yuborishda jami {files.MAX_TOTAL_MB} MB gacha fayl yuklash mumkin. "
    "Orqaga qaytib, kichikroq fayl tanlang yoki rasmni siqib yuboring.</p>"
    '<p><a href="javascript:history.back()">← Orqaga</a></p></body></html>'
)


class UploadLimitMiddleware:
    """So'rovnoma sahifasiga juda katta POST so'rovini CSRF tekshiruvi tanani o'qishidan oldin to'xtatadi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path.startswith("/s/"):
            try:
                length = int(request.META.get("CONTENT_LENGTH") or 0)
            except ValueError:
                length = 0
            if length > files.MAX_REQUEST_BYTES:
                return HttpResponse(PAGE, status=413)
        return self.get_response(request)
