"""Rate limiting en memoria (ventana deslizante).

Suficiente para una instancia única (el MVP corre así). Si se escala a varias
instancias o workers, hay que sustituir el almacén en memoria por Redis.

No añade dependencias: usa `collections.deque` con un candado.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import (
    LOGIN_MAX_ATTEMPTS,
    LOGIN_WINDOW_SECONDS,
    GLOBAL_MAX_REQUESTS,
    GLOBAL_WINDOW_SECONDS,
)


class RateLimiter:
    """Ventana deslizante por clave (por ejemplo, la IP del cliente)."""

    def __init__(self) -> None:
        self._accesos: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def permitir(self, clave: str, maximo: int, ventana_segundos: int) -> tuple[bool, int]:
        """Devuelve (permitido, segundos_para_reintentar)."""
        ahora = time.monotonic()
        limite = ahora - ventana_segundos
        with self._lock:
            cola = self._accesos[clave]
            while cola and cola[0] < limite:
                cola.popleft()
            if len(cola) >= maximo:
                reintentar = max(1, int(cola[0] + ventana_segundos - ahora) + 1)
                return False, reintentar
            cola.append(ahora)
            return True, 0

    def limpiar(self) -> None:
        with self._lock:
            self._accesos.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    """IP real del cliente, respetando proxies (Render/X-Forwarded-For)."""
    reenviado = request.headers.get("x-forwarded-for")
    if reenviado:
        return reenviado.split(",")[0].strip()
    cliente = request.client
    return cliente.host if cliente is not None else "desconocido"


def limite_login(request: Request) -> None:
    """Dependencia para proteger el endpoint de login contra fuerza bruta."""
    ip = client_ip(request)
    permitido, reintentar = limiter.permitir(
        f"login:{ip}", LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_SECONDS
    )
    if not permitido:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de inicio de sesión. Intenta de nuevo más tarde.",
            headers={"Retry-After": str(reintentar)},
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Tope global de peticiones por IP (defensa en profundidad)."""

    async def dispatch(self, request: Request, call_next):
        ip = client_ip(request)
        permitido, reintentar = limiter.permitir(
            f"global:{ip}", GLOBAL_MAX_REQUESTS, GLOBAL_WINDOW_SECONDS
        )
        if not permitido:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Demasiadas solicitudes. Intenta de nuevo más tarde."},
                headers={"Retry-After": str(reintentar)},
            )
        return await call_next(request)
