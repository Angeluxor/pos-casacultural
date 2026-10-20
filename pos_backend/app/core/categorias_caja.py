"""Catálogo de categorías para los movimientos manuales de caja.

La categoría es una clasificación operativa, no una cuenta contable. Sirve
para encontrar rápido un aporte cultural, un arriendo o un gasto menor y para
resumir los movimientos del turno.

Los movimientos automáticos (ventas, compras de inventario, pagos a
proveedores, devoluciones, apertura y cierre) también guardan una categoría.
Las que no están en el catálogo manual no se ofrecen en el formulario.
"""
from typing import Dict, List, Optional

from app.db.models import TipoMovimientoCaja


CATEGORIAS_ENTRADA: List[str] = [
    "Aporte cultural",
    "Donación",
    "Evento",
    "Otro ingreso",
]

CATEGORIAS_SALIDA: List[str] = [
    "Arriendo",
    "Servicios",
    "Nómina",
    "Gasto menor",
    "Pago a proveedor",
    "Devolución",
    "Otro gasto",
]

CATEGORIAS_POR_TIPO: Dict[TipoMovimientoCaja, List[str]] = {
    TipoMovimientoCaja.ENTRADA: CATEGORIAS_ENTRADA,
    TipoMovimientoCaja.SALIDA: CATEGORIAS_SALIDA,
}

CATEGORIA_POR_DEFECTO: Dict[TipoMovimientoCaja, str] = {
    TipoMovimientoCaja.ENTRADA: "Otro ingreso",
    TipoMovimientoCaja.SALIDA: "Otro gasto",
}

# Categorías que el sistema asigna a los movimientos que no se registran a
# mano. No forman parte del selector del formulario.
CATEGORIA_VENTAS = "Ventas"
CATEGORIA_COMPRA_INVENTARIO = "Compra de inventario"
CATEGORIA_PAGO_PROVEEDOR = "Pago a proveedor"
CATEGORIA_DEVOLUCION = "Devolución"
CATEGORIA_APERTURA = "Apertura"
CATEGORIA_CIERRE = "Cierre"


def categorias_manuales(tipo: TipoMovimientoCaja) -> List[str]:
    """Categorías disponibles para un movimiento manual del tipo indicado."""
    return list(CATEGORIAS_POR_TIPO.get(tipo, []))


def normalizar_categoria(
    tipo: TipoMovimientoCaja, categoria: Optional[str]
) -> str:
    """Valida y normaliza la categoría de un movimiento manual.

    Si no se envía, usa la categoría «Otro ingreso» u «Otro gasto». Lanza
    ``ValueError`` si el tipo no admite categoría manual o si la categoría no
    pertenece al catálogo del tipo.
    """
    opciones = CATEGORIAS_POR_TIPO.get(tipo)
    if opciones is None:
        raise ValueError(
            "Solo las entradas y salidas manuales admiten categoría."
        )
    valor = (categoria or "").strip()
    if not valor:
        return CATEGORIA_POR_DEFECTO[tipo]
    if valor not in opciones:
        raise ValueError(
            f"Categoría inválida para {tipo.value}. Usa una de: "
            f"{', '.join(opciones)}."
        )
    return valor
