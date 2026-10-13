from .context import request_scope


class AuditMiddleware:
    """So'rovni jurnal kontekstiga qo'yadi.

    Foydalanuvchi yozuv paytida aniqlanadi: API'da JWT middleware'dan keyin tekshiriladi.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with request_scope(request):
            return self.get_response(request)
