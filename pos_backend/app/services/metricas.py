"""Resumen de las métricas de rendimiento para el panel del administrador."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core import metricas as nucleo
from app.core.timezone import get_colombia_time
from app.db.models import MetricaHttp

# Petición «lenta» y límites usados por el diagnóstico.
LENTA_MS = nucleo.UMBRAL_LENTA_MS
INACTIVIDAD_FRIA_S = 600.0
MUCHAS_CONSULTAS = 30
MAX_FILAS = 50_000
MAX_RUTAS = 25
MAX_LENTAS = 15
_PARAMETRO = re.compile(r"\{[^}]+\}")


def percentil(valores: List[float], p: float) -> float:
    """Percentil por interpolación lineal; 0 si no hay datos."""
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    if len(ordenados) == 1:
        return round(ordenados[0], 1)
    posicion = (len(ordenados) - 1) * p
    bajo = int(posicion)
    alto = min(bajo + 1, len(ordenados) - 1)
    fraccion = posicion - bajo
    return round(ordenados[bajo] + (ordenados[alto] - ordenados[bajo]) * fraccion, 1)


def _clave_ruta(metodo: str, ruta: str) -> str:
    return f"{metodo} {_PARAMETRO.sub('{id}', ruta)}"


def _pct(parte: int, total: int) -> float:
    return round(100.0 * parte / total, 1) if total else 0.0


def _diagnostico(
    servidor: List[Any], cliente: List[Any], rutas: List[Dict[str, Any]]
) -> List[str]:
    notas: List[str] = []
    if not servidor and not cliente:
        return [
            "Todavía no hay datos. Usa la app unos minutos (idealmente desde el "
            "celular) y vuelve a revisar."
        ]

    lentas = [f for f in servidor if f.ms_total >= LENTA_MS]
    if servidor:
        notas.append(
            f"{len(lentas)} de {len(servidor)} peticiones del servidor "
            f"({_pct(len(lentas), len(servidor))} %) tardaron {LENTA_MS / 1000:.0f} s o más."
        )
    if lentas:
        frias = [
            f
            for f in lentas
            if f.primera_tras_arranque
            or (f.inactivo_s is not None and f.inactivo_s >= INACTIVIDAD_FRIA_S)
        ]
        con_bd = [f for f in lentas if f.ms_total and f.ms_db / f.ms_total >= 0.6]
        nuevas = [f for f in lentas if f.conexiones_nuevas > 0]
        muchas = [f for f in lentas if f.consultas >= MUCHAS_CONSULTAS]
        if frias:
            notas.append(
                f"{_pct(len(frias), len(lentas))} % de las lentas fueron la primera "
                "petición tras un arranque o tras 10+ min sin tráfico: señal de "
                "arranque en frío del servicio (plan free de Render)."
            )
        if con_bd:
            notas.append(
                f"{_pct(len(con_bd), len(lentas))} % de las lentas pasaron 60 % o más "
                "de su tiempo en la base de datos: revisar esas consultas o la "
                "latencia hacia Neon."
            )
        if nuevas:
            notas.append(
                f"{_pct(len(nuevas), len(lentas))} % de las lentas abrieron una "
                "conexión nueva a la base de datos (handshake SSL / Neon dormido)."
            )
        if muchas:
            notas.append(
                f"{_pct(len(muchas), len(lentas))} % de las lentas hicieron "
                f"{MUCHAS_CONSULTAS}+ consultas: posible patrón N+1."
            )
        if not (frias or con_bd or nuevas or muchas):
            notas.append(
                "Las lentas no encajan con arranque en frío ni base de datos: el "
                "tiempo se va en el código de la aplicación (revisar la ruta más "
                "lenta de la tabla)."
            )
    elif servidor:
        notas.append(
            "Una vez que el servidor despierta, responde bien. Si el usuario sigue "
            "notando lentitud, mira las mediciones del navegador."
        )

    fallidas = [f for f in cliente if f.estado == 0]
    if cliente:
        notas.append(
            f"Navegador: {len(cliente)} peticiones medidas, {len(fallidas)} "
            "agotaron el tiempo o fallaron sin respuesta."
        )
    comparables = [r for r in rutas if r["cliente_p95"] is not None and r["n"] >= 3]
    atrasadas = [
        r for r in comparables if r["cliente_p95"] - r["p95"] >= 1000.0
    ]
    if atrasadas:
        peor = max(atrasadas, key=lambda r: r["cliente_p95"] - r["p95"])
        notas.append(
            f"El navegador espera bastante más que el servidor en {len(atrasadas)} "
            f"rutas (p. ej. {peor['ruta']}: {peor['cliente_p95']:.0f} ms vs "
            f"{peor['p95']:.0f} ms). La diferencia está fuera del código: red del "
            "dispositivo o servicio dormido que aún no alcanza a medirse."
        )
    return notas


def resumen(db: Session, horas: int = 24) -> Dict[str, Any]:
    desde = get_colombia_time() - timedelta(hours=horas)
    filas = (
        db.query(MetricaHttp)
        .filter(MetricaHttp.creado_en >= desde)
        .order_by(MetricaHttp.creado_en.desc())
        .limit(MAX_FILAS)
        .all()
    )
    servidor = [f for f in filas if f.origen == "servidor"]
    cliente = [f for f in filas if f.origen == "cliente"]

    grupos_srv: Dict[str, List[Any]] = defaultdict(list)
    for f in servidor:
        grupos_srv[_clave_ruta(f.metodo, f.ruta)].append(f)
    grupos_cli: Dict[str, List[Any]] = defaultdict(list)
    for f in cliente:
        grupos_cli[_clave_ruta(f.metodo, f.ruta)].append(f)

    rutas: List[Dict[str, Any]] = []
    for clave, items in grupos_srv.items():
        tiempos = [f.ms_total for f in items]
        del_cliente = grupos_cli.get(clave)
        suma_total = sum(tiempos)
        rutas.append(
            {
                "ruta": clave,
                "n": len(items),
                "p50": percentil(tiempos, 0.5),
                "p95": percentil(tiempos, 0.95),
                "max": round(max(tiempos), 1),
                "db_prom": round(sum(f.ms_db for f in items) / len(items), 1),
                "pct_db": round(100.0 * sum(f.ms_db for f in items) / suma_total, 1)
                if suma_total
                else 0.0,
                "consultas_prom": round(sum(f.consultas for f in items) / len(items), 1),
                "errores_5xx": sum(1 for f in items if f.estado >= 500),
                "cliente_p95": percentil([f.ms_total for f in del_cliente], 0.95)
                if del_cliente
                else None,
            }
        )
    rutas.sort(key=lambda r: r["p95"], reverse=True)

    por_hora: Dict[str, List[float]] = defaultdict(list)
    for f in servidor:
        por_hora[f.creado_en.strftime("%Y-%m-%d %H:00")].append(f.ms_total)
    linea = [
        {"hora": hora, "n": len(v), "p50": percentil(v, 0.5), "p95": percentil(v, 0.95)}
        for hora, v in sorted(por_hora.items())
    ]

    lentas = sorted(
        (f for f in servidor if f.ms_total >= LENTA_MS),
        key=lambda f: f.ms_total,
        reverse=True,
    )[:MAX_LENTAS]

    tiempos_srv = [f.ms_total for f in servidor]
    tiempos_cli = [f.ms_total for f in cliente if f.estado != 0]
    suma_srv = sum(tiempos_srv)
    proceso = nucleo.estado_proceso()

    return {
        "horas": horas,
        "generado": get_colombia_time(),
        "proceso": proceso,
        "servidor": {
            "n": len(servidor),
            "p50": percentil(tiempos_srv, 0.5),
            "p95": percentil(tiempos_srv, 0.95),
            "max": round(max(tiempos_srv), 1) if tiempos_srv else 0.0,
            "pct_lentas": _pct(
                sum(1 for t in tiempos_srv if t >= LENTA_MS), len(tiempos_srv)
            ),
            "pct_db": round(100.0 * sum(f.ms_db for f in servidor) / suma_srv, 1)
            if suma_srv
            else 0.0,
            "arranques_en_frio": sum(1 for f in servidor if f.primera_tras_arranque),
            "tras_inactividad": sum(
                1
                for f in servidor
                if f.inactivo_s is not None and f.inactivo_s >= INACTIVIDAD_FRIA_S
            ),
            "conexiones_nuevas": sum(f.conexiones_nuevas for f in servidor),
            "errores_5xx": sum(1 for f in servidor if f.estado >= 500),
        },
        "cliente": {
            "n": len(cliente),
            "p50": percentil(tiempos_cli, 0.5),
            "p95": percentil(tiempos_cli, 0.95),
            "max": round(max(tiempos_cli), 1) if tiempos_cli else 0.0,
            "fallidas": sum(1 for f in cliente if f.estado == 0),
        },
        "diagnostico": _diagnostico(servidor, cliente, rutas),
        "rutas": rutas[:MAX_RUTAS],
        "por_hora": linea,
        "lentas": [
            {
                "creado_en": f.creado_en,
                "metodo": f.metodo,
                "ruta": f.ruta,
                "estado": f.estado,
                "ms_total": f.ms_total,
                "ms_db": f.ms_db,
                "consultas": f.consultas,
                "conexiones_nuevas": f.conexiones_nuevas,
                "inactivo_s": f.inactivo_s,
                "primera_tras_arranque": f.primera_tras_arranque,
            }
            for f in lentas
        ],
    }
