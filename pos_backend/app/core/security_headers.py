"""Cabeceras HTTP de seguridad (equivalente ligero a `helmet`)."""
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import ENABLE_HSTS

_CABECERAS_BASE = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    # API JSON pura: no necesita cargar recursos. (El frontend se sirve aparte.)
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for nombre, valor in _CABECERAS_BASE.items():
            response.headers.setdefault(nombre, valor)
        if ENABLE_HSTS:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response
