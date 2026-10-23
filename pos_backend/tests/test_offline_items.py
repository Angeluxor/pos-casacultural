"""Ítems agregados sin conexión a una factura ya existente.

El caso típico: la factura se creó con red y, cuando la mesa pide otro
servicio, el dispositivo quedó sin conexión. La operación se guarda localmente
y se sincroniza después sin duplicar el producto ni rechazar la venta por
stock desactualizado.
"""
from app.db.models import Factura, Kardex, Producto
from app.db.session import SessionLocal

from .conftest import auth


def _abrir_caja(client, token):
    resp = client.post(
        "/api/caja/abrir",
        headers=auth(token),
        json={"saldo_inicial_efectivo": 0, "saldo_inicial_banco": 0},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _crear_producto(client, token, codigo="OFFITEM1", precio=5000, stock=10):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={
            "codigo": codigo,
            "nombre": "Producto adicional",
            "precio": precio,
            "stock_inicial": stock,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _crear_factura(client, token, producto_id, cantidad=1):
    resp = client.post(
        "/api/facturas/",
        headers=auth(token),
        json={
            "nombre_eventual": "Mesa 4",
            "detalles": [{"producto_id": producto_id, "cantidad": cantidad}],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _agregar_offline(
    client,
    token,
    factura_id,
    producto_id,
    cantidad=1,
    precio=4000,
    clave="item-offline-1",
):
    headers = auth(token)
    if clave is not None:
        headers["Idempotency-Key"] = clave
    return client.post(
        f"/api/facturas/{factura_id}/items/offline",
        headers=headers,
        json={
            "producto_id": producto_id,
            "cantidad": cantidad,
            "precio_unitario": precio,
        },
    )


def test_item_offline_conserva_el_precio_y_actualiza_total_y_stock(
    client, token_cajero
):
    producto = _crear_producto(client, token_cajero, precio=5000, stock=10)
    factura = _crear_factura(client, token_cajero, producto["id"])

    resp = _agregar_offline(
        client,
        token_cajero,
        factura["id"],
        producto["id"],
        cantidad=1,
        precio=4000,
    )

    assert resp.status_code == 200, resp.text
    actualizada = resp.json()
    assert actualizada["id"] == factura["id"]
    assert actualizada["total"] == 9000
    assert actualizada["saldo"] == 9000
    assert actualizada["estado"] == "Abierta"
    assert len(actualizada["detalles"]) == 2
    assert sorted(d["precio_unitario"] for d in actualizada["detalles"]) == [4000, 5000]

    producto_actualizado = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_cajero)
    ).json()
    assert producto_actualizado["stock"] == 8


def test_reintento_con_la_misma_clave_no_duplica_el_item(client, token_cajero):
    producto = _crear_producto(client, token_cajero, codigo="OFFITEM2")
    factura = _crear_factura(client, token_cajero, producto["id"])

    primera = _agregar_offline(
        client,
        token_cajero,
        factura["id"],
        producto["id"],
        precio=5000,
        clave="item-retry",
    )
    segunda = _agregar_offline(
        client,
        token_cajero,
        factura["id"],
        producto["id"],
        precio=5000,
        clave="item-retry",
    )

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["total"] == 10000
    assert len(segunda.json()["detalles"]) == 1
    assert segunda.json()["detalles"][0]["cantidad"] == 2

    producto_actualizado = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_cajero)
    ).json()
    assert producto_actualizado["stock"] == 8

    db = SessionLocal()
    try:
        salidas = (
            db.query(Kardex)
            .filter(Kardex.referencia == f"Adición offline a Factura #{factura['id']}")
            .count()
        )
        assert salidas == 1
    finally:
        db.close()


def test_item_offline_permite_stock_negativo_y_marca_revision(
    client, token_cajero
):
    producto = _crear_producto(
        client, token_cajero, codigo="OFFITEM3", precio=5000, stock=1
    )
    factura = _crear_factura(client, token_cajero, producto["id"], cantidad=1)

    resp = _agregar_offline(
        client,
        token_cajero,
        factura["id"],
        producto["id"],
        cantidad=2,
        precio=5000,
    )

    assert resp.status_code == 200, resp.text
    actualizada = resp.json()
    assert actualizada["total"] == 15000
    assert actualizada["requiere_revision"] is True
    assert "Stock insuficiente" in actualizada["nota_revision"]

    producto_actualizado = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_cajero)
    ).json()
    assert producto_actualizado["stock"] == -2


def test_item_offline_en_factura_anulada_se_rechaza(client, token_admin):
    producto = _crear_producto(client, token_admin, codigo="OFFITEM4")
    factura = _crear_factura(client, token_admin, producto["id"])
    anulada = client.post(
        f"/api/facturas/{factura['id']}/anular",
        headers=auth(token_admin),
        json={"motivo": "Prueba"},
    )
    assert anulada.status_code == 200, anulada.text

    resp = _agregar_offline(
        client, token_admin, factura["id"], producto["id"], clave="item-anulada"
    )

    assert resp.status_code == 400, resp.text
    assert "anulada" in resp.json()["detail"].lower()


def test_la_clave_de_item_no_se_reutiliza_en_otra_factura(
    client, token_cajero
):
    producto = _crear_producto(client, token_cajero, codigo="OFFITEM5")
    primera = _crear_factura(client, token_cajero, producto["id"])
    segunda = _crear_factura(client, token_cajero, producto["id"])

    ok = _agregar_offline(
        client, token_cajero, primera["id"], producto["id"], clave="item-cruzado"
    )
    ajena = _agregar_offline(
        client, token_cajero, segunda["id"], producto["id"], clave="item-cruzado"
    )

    assert ok.status_code == 200, ok.text
    assert ajena.status_code == 409, ajena.text
    assert "otra operación" in ajena.json()["detail"].lower()

    sin_cambios = client.get(
        f"/api/facturas/{segunda['id']}", headers=auth(token_cajero)
    ).json()
    assert sin_cambios["total"] == segunda["total"]


def test_sin_clave_no_se_permite_agregar_item_offline(client, token_cajero):
    producto = _crear_producto(client, token_cajero, codigo="OFFITEM6")
    factura = _crear_factura(client, token_cajero, producto["id"])

    resp = _agregar_offline(
        client, token_cajero, factura["id"], producto["id"], clave=None
    )

    assert resp.status_code == 400, resp.text
    assert "idempotencia" in resp.json()["detail"].lower()


def test_item_offline_en_factura_pagada_genera_saldo_pendiente(
    client, token_cajero
):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero, codigo="OFFITEM7")
    factura = _crear_factura(client, token_cajero, producto["id"])

    pago = client.post(
        f"/api/facturas/{factura['id']}/pagos",
        headers=auth(token_cajero),
        json={"valor": factura["total"], "forma_pago": "Efectivo"},
    )
    assert pago.status_code == 200, pago.text
    assert pago.json()["estado"] == "Pagada"

    resp = _agregar_offline(
        client,
        token_cajero,
        factura["id"],
        producto["id"],
        cantidad=1,
        precio=5000,
    )

    assert resp.status_code == 200, resp.text
    actualizada = resp.json()
    assert actualizada["estado"] == "Pagado Parcial"
    assert actualizada["total"] == 10000
    assert actualizada["saldo"] == 5000

    db = SessionLocal()
    try:
        guardada = db.query(Factura).filter(Factura.id == factura["id"]).one()
        assert guardada.saldo == 5000
        assert db.query(Producto).filter(Producto.id == producto["id"]).one().stock == 8
    finally:
        db.close()
