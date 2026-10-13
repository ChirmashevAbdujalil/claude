"""Joriy so'rov va manba: jurnal yozuvida «kim» va «qayerdan» uchun."""

from contextlib import contextmanager
from contextvars import ContextVar

_request = ContextVar("audit_request", default=None)
_source = ContextVar("audit_source", default="")


def current_request():
    return _request.get()


def current_source() -> str:
    return _source.get()


@contextmanager
def request_scope(request):
    token = _request.set(request)
    try:
        yield
    finally:
        _request.reset(token)


@contextmanager
def source(name: str):
    """Foydalanuvchisiz amallar uchun manba: «Payme», «Click», «Tizim: obuna nazorati»."""
    token = _source.set(name)
    try:
        yield
    finally:
        _source.reset(token)
