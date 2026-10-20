"""Catálogo de permisos por rol.

Los permisos se agrupan por módulo y aplican a los roles ``Cajero`` y
``Mesero``. El rol ``Admin`` siempre tiene todos los permisos y no se puede
editar.

Los permisos **por defecto** viven en código (``PERMISOS_POR_DEFECTO``). Cuando
un Admin guarda cambios para un rol se escribe una fila en ``permisos_rol`` con
la lista exacta, que pasa a reemplazar al default (aunque quede vacía). Así se
puede distinguir "sin configurar" de "configurado sin permisos".
"""
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.db.models import PermisoRol, RolUsuario


# (módulo, [(clave, etiqueta), ...]); el orden es el que ve el Admin en la UI.
CATALOGO: List[Tuple[str, List[Tuple[str, str]]]] = [
    ("Dashboard", [("dashboard.ver", "Ver el tablero")]),
    (
        "Productos",
        [
            ("productos.ver", "Ver productos"),
            ("productos.crear", "Crear productos"),
            ("productos.editar", "Editar productos"),
            ("productos.ajustar", "Ajustar inventario (kardex)"),
        ],
    ),
    (
        "Costos",
        [
            ("costos.ver", "Ver costos, recetas e históricos"),
            ("costos.editar", "Registrar costos manuales y editar recetas"),
        ],
    ),
    (
        "Clientes",
        [
            ("clientes.ver", "Ver clientes"),
            ("clientes.crear", "Crear clientes"),
            ("clientes.editar", "Editar clientes"),
            ("clientes.eliminar", "Eliminar clientes"),
            ("clientes.fusionar", "Fusionar clientes duplicados"),
        ],
    ),
    (
        "Ventas",
        [
            ("ventas.ver", "Ver facturas"),
            ("ventas.crear", "Crear facturas"),
            ("ventas.editar", "Editar ítems y cliente de la factura"),
            ("ventas.cobrar", "Registrar pagos"),
            ("ventas.anular", "Anular facturas"),
        ],
    ),
    (
        "Caja",
        [
            ("caja.ver", "Ver la caja y sus movimientos"),
            ("caja.operar", "Abrir/cerrar caja y registrar movimientos"),
        ],
    ),
    (
        "Ingresos",
        [
            ("ingresos.ver", "Ver ingresos de inventario"),
            ("ingresos.crear", "Registrar ingresos"),
            ("ingresos.editar", "Editar ingresos"),
            ("ingresos.resolver", "Resolver productos nuevos de un ingreso"),
            ("ingresos.pagar", "Pagar compras a crédito"),
        ],
    ),
    (
        "Proveedores",
        [
            ("proveedores.ver", "Ver proveedores"),
            ("proveedores.crear", "Crear proveedores"),
            ("proveedores.editar", "Editar proveedores"),
            ("proveedores.eliminar", "Eliminar proveedores"),
        ],
    ),
    ("Reportes", [("reportes.ver", "Ver y exportar reportes")]),
    (
        "Balance",
        [
            ("balance.ver", "Ver y exportar el balance general"),
            (
                "balance.editar",
                "Crear bolsillos y apartar/liberar dinero para gastos vitales",
            ),
        ],
    ),
    (
        "Feedback",
        [
            ("feedback.crear", "Enviar comentarios, ideas y reportes de error"),
            ("feedback.gestionar", "Revisar y gestionar el feedback del equipo"),
        ],
    ),
    ("Usuarios", [("usuarios.gestionar", "Gestionar usuarios")]),
    (
        "Nómina",
        [("nomina.descontar", "Descontar nómina y consultar historial/reporte")],
    ),
    ("Permisos", [("permisos.gestionar", "Gestionar permisos por rol")]),
]

# Todas las claves, en orden de catálogo.
TODOS: List[str] = [clave for _, permisos in CATALOGO for clave, _ in permisos]

# Etiqueta legible de cada clave (para mensajes si hiciera falta).
ETIQUETAS: Dict[str, str] = {
    clave: etiqueta for _, permisos in CATALOGO for clave, etiqueta in permisos
}

# Roles configurables (Admin queda fuera: siempre tiene todo).
ROLES_CONFIGURABLES: List[RolUsuario] = [RolUsuario.CAJERO, RolUsuario.MESERO]

# Permisos por defecto. Buscan reproducir el comportamiento previo:
# el Cajero hacía todo salvo lo que era exclusivo del Admin (editar productos,
# eliminar clientes, anular facturas, resolver ingresos, reportes, usuarios).
PERMISOS_POR_DEFECTO: Dict[RolUsuario, List[str]] = {
    RolUsuario.CAJERO: [
        "dashboard.ver",
        "productos.ver",
        "productos.crear",
        "productos.ajustar",
        "clientes.ver",
        "clientes.crear",
        "clientes.editar",
        "ventas.ver",
        "ventas.crear",
        "ventas.editar",
        "ventas.cobrar",
        "caja.ver",
        "caja.operar",
        "ingresos.ver",
        "ingresos.crear",
        "ingresos.editar",
        "ingresos.pagar",
        "proveedores.ver",
        "proveedores.crear",
        "proveedores.editar",
        "feedback.crear",
    ],
    # Mesero: toma pedidos, cobra, gestiona clientes y ve la caja (solo lectura).
    RolUsuario.MESERO: [
        "productos.ver",
        "clientes.ver",
        "clientes.crear",
        "clientes.editar",
        "ventas.ver",
        "ventas.crear",
        "ventas.editar",
        "ventas.cobrar",
        "caja.ver",
        "feedback.crear",
    ],
}


def _normalizar(claves) -> List[str]:
    """Deja solo claves válidas, sin repetir y en orden de catálogo."""
    validas = set(claves or [])
    return [clave for clave in TODOS if clave in validas]


def permisos_efectivos(db: Session, rol: RolUsuario) -> List[str]:
    """Permisos vigentes de un rol (configurados o por defecto)."""
    if rol == RolUsuario.ADMIN:
        return list(TODOS)
    fila = db.query(PermisoRol).filter(PermisoRol.rol == rol).first()
    if fila is not None:
        return _normalizar(fila.permisos)
    return list(PERMISOS_POR_DEFECTO.get(rol, []))


def tiene_permiso(db: Session, rol: RolUsuario, clave: str) -> bool:
    return clave in permisos_efectivos(db, rol)


def guardar_permisos(db: Session, rol: RolUsuario, claves) -> List[str]:
    """Crea o reemplaza los permisos de un rol configurable."""
    normalizadas = _normalizar(claves)
    fila = db.query(PermisoRol).filter(PermisoRol.rol == rol).first()
    if fila is None:
        fila = PermisoRol(rol=rol, permisos=normalizadas)
        db.add(fila)
    else:
        fila.permisos = normalizadas
    db.commit()
    return normalizadas
