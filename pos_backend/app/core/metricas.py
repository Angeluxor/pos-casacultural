"""Registro de métricas de rendimiento por petición HTTP.

Sirve para responder con datos a «el servidor está lento». Por cada petición
guarda el tiempo total, cuánto se fue en la base de datos, cuántas consultas y
conexiones nuevas hizo, y cuánto llevaba el proceso sin recibir tráfico. Con
eso se distingue entre:

- arranque en frío del proceso (primera petición tras un arranque o una pausa
  larga),
- consultas lentas o demasiadas consultas (mucho ``ms_db``/``consultas``),
- código de la aplicación (``ms_total`` alto con ``ms_db`` bajo),
- red del usuario (las muestras ``cliente`` miden lo que ve el navegador y se
  comparan con las del servidor).

Diseño: la petición solo añade un dict a un búfer en memoria (sin tocar la
base de datos). Un hilo en segundo plano vuelca el búfer a la tabla
``metricas_http`` por lotes, así medir no añade latencia a la petición. Si la
escritura falla, se descarta: medir nunca debe romper la app.

Una sola instancia (plan free de Render) comparte el búfer; con varias
instancias cada una escribe sus propias filas y la tabla las junta.
"""
from __future__ import annotations

import contextvars
import logging
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import event

from app.core.timezone import get_colombia_time

logger = logging.getLogger("pos.metricas")

# Peticiones que no se registran: la sonda de salud (la llama un cron cada
# pocos minutos) y las propias métricas.
RUTAS_IGNORADAS = ("/api/health", "/api/metricas")
# Una petición más lenta que esto se escribe también en el log del hosting.
UMBRAL_LENTA_MS = 2000.0
MAX_BUFER = 5000
INTERVALO_VOLCADO_S = 20.0
RETENCION_DIAS = 30

_ID_NUMERICO = re.compile(r"/\d+(?=/|$)")

# Acumulador de la petición en curso; un dict mutable para que los hilos del
# pool (que reciben una copia del contexto) escriban en el mismo objeto.
_acumulador: contextvars.ContextVar[Optional[Dict[str, float]]] = (
    contextvars.ContextVar("metricas_acumulador", default=None)
)

_lock = threading.Lock()
_bufer: List[Dict[str, Any]] = []
_estado: Dict[str, Any] = {
    "proceso_desde": time.time(),
    "ultima_peticion": None,  # monotonic de la última petición registrable
    "primera_pendiente": True,
    "arranque_ms": None,
    "descartadas": 0,
}
_hilo: Optional[threading.Thread] = None
_parar = threading.Event()


def normalizar_ruta(ruta: str) -> str:
    """Agrupa rutas con ids: ``/api/facturas/12/pagos`` -> ``.../{id}/pagos``."""
    return _ID_NUMERICO.sub("/{id}", ruta)


def es_ignorada(ruta: str) -> bool:
    return ruta.startswith(RUTAS_IGNORADAS)


def iniciar_peticion() -> contextvars.Token:
    return _acumulador.set({"ms_db": 0.0, "consultas": 0, "conexiones": 0})


def terminar_peticion(token: contextvars.Token) -> Dict[str, float]:
    datos = _acumulador.get() or {}
    _acumulador.reset(token)
    return datos


def registrar_arranque(ms: float) -> None:
    _estado["arranque_ms"] = round(ms, 1)
    logger.info("Arranque completado en %.0f ms", ms)


def _contexto_inactividad() -> tuple[Optional[float], bool]:
    """Segundos desde la petición anterior y si es la primera tras el arranque."""
    ahora = time.monotonic()
    ultima = _estado["ultima_peticion"]
    _estado["ultima_peticion"] = ahora
    primera = bool(_estado["primera_pendiente"])
    _estado["primera_pendiente"] = False
    inactivo = None if ultima is None else ahora - ultima
    return inactivo, primera


def registrar_peticion(
    metodo: str,
    ruta: str,
    estado: int,
    ms_total: float,
    acumulado: Dict[str, float],
) -> None:
    """Añade una muestra del servidor al búfer (no toca la base de datos)."""
    if es_ignorada(ruta):
        return
    with _lock:
        inactivo, primera = _contexto_inactividad()
        fila = {
            "creado_en": get_colombia_time(),
            "origen": "servidor",
            "metodo": metodo[:8],
            "ruta": ruta[:160],
            "estado": int(estado),
            "ms_total": round(ms_total, 1),
            "ms_db": round(float(acumulado.get("ms_db", 0.0)), 1),
            "consultas": int(acumulado.get("consultas", 0)),
            "conexiones_nuevas": int(acumulado.get("conexiones", 0)),
            "inactivo_s": None if inactivo is None else round(inactivo, 1),
            "primera_tras_arranque": primera,
            "conexion": None,
        }
        _agregar(fila)
    if ms_total >= UMBRAL_LENTA_MS:
        logger.warning(
            "Petición lenta %s %s -> %s en %.0f ms (BD %.0f ms, %d consultas, "
            "%d conexiones nuevas, inactivo %s s, primera tras arranque: %s)",
            metodo,
            ruta,
            estado,
            ms_total,
            fila["ms_db"],
            fila["consultas"],
            fila["conexiones_nuevas"],
            fila["inactivo_s"],
            primera,
        )


def registrar_muestras_cliente(muestras: List[Dict[str, Any]]) -> None:
    """Guarda lo que midió el navegador (incluye red y arranques en frío)."""
    with _lock:
        for m in muestras:
            conexion = m.get("conexion")
            _agregar(
                {
                    "creado_en": get_colombia_time(),
                    "origen": "cliente",
                    "metodo": str(m.get("metodo", ""))[:8],
                    "ruta": normalizar_ruta(str(m.get("ruta", "")))[:160],
                    "estado": int(m.get("estado", 0)),
                    "ms_total": round(float(m.get("ms", 0.0)), 1),
                    "ms_db": 0.0,
                    "consultas": 0,
                    "conexiones_nuevas": 0,
                    "inactivo_s": None,
                    "primera_tras_arranque": False,
                    "conexion": str(conexion)[:16] if conexion else None,
                }
            )


def _agregar(fila: Dict[str, Any]) -> None:
    # Llamar con _lock tomado.
    if len(_bufer) >= MAX_BUFER:
        _estado["descartadas"] += 1
        return
    _bufer.append(fila)


def volcar() -> int:
    """Escribe el búfer en la base de datos. Devuelve cuántas filas guardó."""
    from app.db.models import MetricaHttp
    from app.db.session import SessionLocal

    with _lock:
        pendientes = _bufer[:]
        _bufer.clear()
    if not pendientes:
        return 0
    db = SessionLocal()
    try:
        db.bulk_insert_mappings(MetricaHttp, pendientes)
        db.commit()
        return len(pendientes)
    except Exception:  # noqa: BLE001 - medir nunca debe romper la app
        db.rollback()
        logger.warning(
            "No se pudieron guardar %d métricas", len(pendientes), exc_info=True
        )
        return 0
    finally:
        db.close()


def purgar_antiguas() -> None:
    from app.db.models import MetricaHttp
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        limite = get_colombia_time() - timedelta(days=RETENCION_DIAS)
        db.query(MetricaHttp).filter(MetricaHttp.creado_en < limite).delete(
            synchronize_session=False
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.warning("No se pudieron purgar métricas antiguas", exc_info=True)
    finally:
        db.close()


def _bucle() -> None:
    ultima_purga = 0.0
    while not _parar.wait(INTERVALO_VOLCADO_S):
        volcar()
        if time.monotonic() - ultima_purga > 3600:
            ultima_purga = time.monotonic()
            purgar_antiguas()


def iniciar_volcado() -> None:
    """Arranca el hilo que vuelca las métricas (idempotente)."""
    global _hilo
    if _hilo is not None and _hilo.is_alive():
        return
    _parar.clear()
    _hilo = threading.Thread(target=_bucle, name="volcado-metricas", daemon=True)
    _hilo.start()


def detener_volcado() -> None:
    _parar.set()
    volcar()


def estado_proceso() -> Dict[str, Any]:
    return {
        "proceso_desde": datetime.fromtimestamp(_estado["proceso_desde"]).astimezone(),
        "arranque_ms": _estado["arranque_ms"],
        "en_bufer": len(_bufer),
        "descartadas": _estado["descartadas"],
    }


def instrumentar_motor(engine) -> None:
    """Cuenta consultas, tiempo en BD y conexiones nuevas de cada petición."""

    @event.listens_for(engine, "before_cursor_execute")
    def _antes(conn, cursor, statement, parameters, context, executemany):
        if context is not None:
            context._inicio_metrica = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _despues(conn, cursor, statement, parameters, context, executemany):
        acum = _acumulador.get()
        inicio = getattr(context, "_inicio_metrica", None)
        if acum is not None and inicio is not None:
            acum["ms_db"] += (time.perf_counter() - inicio) * 1000.0
            acum["consultas"] += 1

    @event.listens_for(engine, "connect")
    def _conexion_nueva(dbapi_connection, connection_record):
        acum = _acumulador.get()
        if acum is not None:
            acum["conexiones"] += 1


class MetricasMiddleware:
    """Middleware ASGI puro: mide cada petición sin envolver el cuerpo."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        inicio = time.perf_counter()
        token = iniciar_peticion()
        estado = {"codigo": 500}

        async def _send(mensaje):
            if mensaje["type"] == "http.response.start":
                estado["codigo"] = mensaje["status"]
            await send(mensaje)

        try:
            await self.app(scope, receive, _send)
        finally:
            acumulado = terminar_peticion(token)
            try:
                ruta_objeto = scope.get("route")
                ruta = getattr(ruta_objeto, "path", None) or normalizar_ruta(
                    scope.get("path", "")
                )
                registrar_peticion(
                    scope.get("method", ""),
                    ruta,
                    estado["codigo"],
                    (time.perf_counter() - inicio) * 1000.0,
                    acumulado,
                )
            except Exception:  # noqa: BLE001
                logger.debug("No se pudo registrar la métrica", exc_info=True)
