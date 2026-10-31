"""Prueba de carga: agregar productos y cambiar cantidades en facturas abiertas.

Simula cajeros/meseros concurrentes en un evento. Cada worker abre una factura
(una mesa) y repite durante la duración indicada:
  - agregar un producto  (POST /api/facturas/{id}/items)
  - cambiar una cantidad (PUT  /api/facturas/{id}/items/{detalle_id})

Reporta latencias p50/p95/p99/máx y tasa de errores por tipo de acción.

USO (solo contra una base de datos de PRUEBA: crea facturas y mueve stock):

    python scripts/prueba_carga_factura.py \
        --base-url http://localhost:8000 \
        --usuario admin --clave <clave> \
        --workers 10 --duracion 60

Las credenciales también pueden venir de POS_USUARIO y POS_CLAVE.
"""
from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import httpx


@dataclass
class Muestras:
    tiempos: dict[str, list[float]] = field(default_factory=dict)
    errores: dict[str, int] = field(default_factory=dict)
    codigos: dict[str, dict[int, int]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def registrar(self, accion: str, segundos: float, status: int) -> None:
        with self.lock:
            self.tiempos.setdefault(accion, []).append(segundos)
            por_codigo = self.codigos.setdefault(accion, {})
            por_codigo[status] = por_codigo.get(status, 0) + 1
            if status >= 400 or status == 0:
                self.errores[accion] = self.errores.get(accion, 0) + 1


def login(base_url: str, usuario: str, clave: str) -> str:
    resp = httpx.post(
        f"{base_url}/api/auth/login",
        data={"username": usuario, "password": clave},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def crear_productos(cliente: httpx.Client, cantidad: int) -> list[int]:
    ids: list[int] = []
    sufijo = uuid.uuid4().hex[:6].upper()
    for i in range(cantidad):
        resp = cliente.post(
            "/api/productos/",
            json={
                "codigo": f"CARGA-{sufijo}-{i}",
                "nombre": f"Producto carga {i}",
                "precio": 10000 + i * 500,
                "stock_inicial": 1_000_000,
            },
        )
        resp.raise_for_status()
        ids.append(resp.json()["id"])
    return ids


def medir(muestras: Muestras, accion: str, fn) -> httpx.Response | None:
    inicio = time.perf_counter()
    try:
        resp = fn()
    except httpx.HTTPError:
        muestras.registrar(accion, time.perf_counter() - inicio, 0)
        return None
    muestras.registrar(accion, time.perf_counter() - inicio, resp.status_code)
    return resp


def worker(
    base_url: str,
    token: str,
    productos: list[int],
    duracion: float,
    muestras: Muestras,
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=base_url, headers=headers, timeout=60) as cliente:
        apertura = medir(
            muestras,
            "abrir_factura",
            lambda: cliente.post(
                "/api/facturas/",
                json={"detalles": [{"producto_id": productos[0], "cantidad": 1}]},
            ),
        )
        if apertura is None or apertura.status_code >= 400:
            return
        factura = apertura.json()
        factura_id = factura["id"]
        detalle_id = factura["detalles"][0]["id"]

        fin = time.perf_counter() + duracion
        while time.perf_counter() < fin:
            producto = random.choice(productos)
            resp = medir(
                muestras,
                "agregar_producto",
                lambda: cliente.post(
                    f"/api/facturas/{factura_id}/items",
                    json={"producto_id": producto, "cantidad": 1},
                ),
            )
            if resp is not None and resp.status_code < 400:
                # Usa un detalle real de la factura para el cambio de cantidad.
                lineas = resp.json()["detalles"]
                detalle_id = random.choice(lineas)["id"]
            medir(
                muestras,
                "cambiar_cantidad",
                lambda: cliente.put(
                    f"/api/facturas/{factura_id}/items/{detalle_id}",
                    json={"cantidad": random.randint(1, 5)},
                ),
            )


def percentil(valores: list[float], p: float) -> float:
    if len(valores) == 1:
        return valores[0]
    return statistics.quantiles(valores, n=100, method="inclusive")[int(p) - 1]


def imprimir(muestras: Muestras, duracion: float) -> None:
    print()
    print(f"{'acción':<18}{'n':>7}{'p50 ms':>10}{'p95 ms':>10}{'p99 ms':>10}{'máx ms':>10}{'errores':>9}")
    for accion, tiempos in sorted(muestras.tiempos.items()):
        ms = [t * 1000 for t in tiempos]
        print(
            f"{accion:<18}{len(ms):>7}"
            f"{percentil(ms, 50):>10.0f}{percentil(ms, 95):>10.0f}{percentil(ms, 99):>10.0f}"
            f"{max(ms):>10.0f}{muestras.errores.get(accion, 0):>9}"
        )
    total = sum(len(v) for v in muestras.tiempos.values())
    print(f"\nTotal de peticiones: {total} en {duracion:.0f} s ({total / duracion:.1f} req/s)")
    for accion, codigos in sorted(muestras.codigos.items()):
        detalle = ", ".join(f"{c}: {n}" for c, n in sorted(codigos.items()))
        print(f"  {accion}: {detalle}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # acentos en la consola de Windows
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--usuario", default=os.environ.get("POS_USUARIO"))
    parser.add_argument("--clave", default=os.environ.get("POS_CLAVE"))
    parser.add_argument("--workers", type=int, default=10, help="facturas abiertas en paralelo")
    parser.add_argument("--duracion", type=float, default=60, help="segundos de carga")
    parser.add_argument("--productos", type=int, default=5)
    args = parser.parse_args()

    if not args.usuario or not args.clave:
        print("Faltan credenciales: usa --usuario/--clave o POS_USUARIO/POS_CLAVE.", file=sys.stderr)
        return 2

    token = login(args.base_url, args.usuario, args.clave)
    with httpx.Client(
        base_url=args.base_url, headers={"Authorization": f"Bearer {token}"}, timeout=60
    ) as admin:
        productos = crear_productos(admin, args.productos)

    print(f"Carga: {args.workers} facturas en paralelo durante {args.duracion:.0f} s contra {args.base_url}")
    muestras = Muestras()
    inicio = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for _ in range(args.workers):
            pool.submit(worker, args.base_url, token, productos, args.duracion, muestras)
    duracion_real = time.perf_counter() - inicio
    imprimir(muestras, duracion_real)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
