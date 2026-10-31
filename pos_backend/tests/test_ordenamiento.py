"""Pruebas del ordenamiento de listados paginados (Requerimiento 8).

Se valida que el parámetro `orden` ordene todo el conjunto (no solo la página
visible) y que una clave desconocida caiga en el orden por defecto sin romper.
"""
from .conftest import auth


def _producto(client, token, codigo, nombre, precio, stock):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={"codigo": codigo, "nombre": nombre, "precio": precio, "stock_inicial": stock},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _codigos(respuesta):
    return [p["codigo"] for p in respuesta.json()["items"]]


def test_productos_ordenan_por_precio_descendente(client, token_admin):
    _producto(client, token_admin, "P001", "Café", 5000, 1)
    _producto(client, token_admin, "P002", "Té", 9000, 1)
    _producto(client, token_admin, "P003", "Azúcar", 3000, 1)

    resp = client.get(
        "/api/productos/?orden=precio&direccion=desc", headers=auth(token_admin)
    )
    assert resp.status_code == 200
    assert _codigos(resp) == ["P002", "P001", "P003"]


def test_productos_ordenan_por_nombre_ascendente(client, token_admin):
    _producto(client, token_admin, "P001", "Zanahoria", 1000, 1)
    _producto(client, token_admin, "P002", "Arroz", 1000, 1)

    resp = client.get("/api/productos/?orden=nombre", headers=auth(token_admin))
    assert _codigos(resp) == ["P002", "P001"]


def test_orden_invalido_usa_el_orden_por_defecto(client, token_admin):
    _producto(client, token_admin, "P001", "Zanahoria", 1000, 1)
    _producto(client, token_admin, "P002", "Arroz", 1000, 1)

    resp = client.get("/api/productos/?orden=drop_table", headers=auth(token_admin))
    assert resp.status_code == 200
    # Por defecto: nombre ascendente.
    assert _codigos(resp) == ["P002", "P001"]


def test_orden_abarque_todas_las_paginas(client, token_admin):
    for i in range(5):
        _producto(client, token_admin, f"P{i:03d}", f"Producto {i}", (i + 1) * 1000, 1)

    # Página de 2 sin ordenar: solo comprobamos que el orden se aplica al conjunto.
    resp = client.get(
        "/api/productos/?limit=2&orden=precio&direccion=desc", headers=auth(token_admin)
    )
    cuerpo = resp.json()
    assert cuerpo["total"] == 5
    # Los dos primeros de la página son los precios más altos de TODO el conjunto.
    assert [p["precio"] for p in cuerpo["items"]] == [5000, 4000]


def test_usuarios_ordenan_por_rol(client, token_admin, token_cajero):
    resp = client.get(
        "/api/usuarios/?orden=rol&direccion=desc", headers=auth(token_admin)
    )
    assert resp.status_code == 200
    roles = [u["rol"] for u in resp.json()["items"]]
    assert roles == sorted(roles, reverse=True)


def test_facturas_ordenan_por_total_descendente(client, token_cajero):
    client.post(
        "/api/caja/abrir",
        headers=auth(token_cajero),
        json={"saldo_inicial_efectivo": 0, "saldo_inicial_banco": 0},
    )
    barato = _producto(client, token_cajero, "PF1", "Barato", 1000, 10)
    caro = _producto(client, token_cajero, "PF2", "Caro", 9000, 10)

    client.post(
        "/api/facturas/",
        headers=auth(token_cajero),
        json={"detalles": [{"producto_id": barato["id"], "cantidad": 1}]},
    )
    client.post(
        "/api/facturas/",
        headers=auth(token_cajero),
        json={"detalles": [{"producto_id": caro["id"], "cantidad": 1}]},
    )

    resp = client.get(
        "/api/facturas/?orden=total&direccion=desc", headers=auth(token_cajero)
    )
    assert resp.status_code == 200
    totales = [f["total"] for f in resp.json()["items"]]
    assert totales == sorted(totales, reverse=True)
    assert totales[0] == 9000

    # Ordenar por cliente implica unir la tabla y usar el nombre eventual.
    resp_cliente = client.get(
        "/api/facturas/?orden=cliente&direccion=asc", headers=auth(token_cajero)
    )
    assert resp_cliente.status_code == 200
    nombres = [f["cliente_nombre"] or "" for f in resp_cliente.json()["items"]]
    assert nombres == sorted(nombres, key=str.lower)


def test_lineas_de_factura_mantienen_su_orden_al_cambiar_cantidad(
    client, token_cajero
):
    """Las líneas no deben saltar de sitio al editar una cantidad.

    PostgreSQL no garantiza el orden de un SELECT sin ORDER BY. Al cambiar la
    cantidad de una línea se reescribe su tupla, así que podía aparecer al
    final de la tabla y descolocar la venta mientras el cajero la editaba.
    """
    client.post(
        "/api/caja/abrir",
        headers=auth(token_cajero),
        json={"saldo_inicial_efectivo": 0, "saldo_inicial_banco": 0},
    )
    productos = [
        _producto(client, token_cajero, f"PO{i}", f"Producto {i}", 1000, 10)
        for i in range(3)
    ]

    resp = client.post(
        "/api/facturas/",
        headers=auth(token_cajero),
        json={
            "detalles": [
                {"producto_id": p["id"], "cantidad": 1} for p in productos
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    factura = resp.json()
    orden_original = [d["id"] for d in factura["detalles"]]
    assert orden_original == sorted(orden_original)

    # Se cambia la cantidad de la línea del medio, la que más sufre al reordenar.
    resp = client.put(
        f"/api/facturas/{factura['id']}/items/{orden_original[1]}",
        headers=auth(token_cajero),
        json={"cantidad": 5},
    )
    assert resp.status_code == 200, resp.text
    assert [d["id"] for d in resp.json()["detalles"]] == orden_original

    resp = client.get(f"/api/facturas/{factura['id']}", headers=auth(token_cajero))
    assert resp.status_code == 200, resp.text
    assert [d["id"] for d in resp.json()["detalles"]] == orden_original


def test_relacion_de_detalles_declara_orden_por_id():
    """La relación debe ordenar en SQL, no depender del orden físico de la tabla."""
    from app.db.models import Factura

    assert Factura.detalles.property.order_by
