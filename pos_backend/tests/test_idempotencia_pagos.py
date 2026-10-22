"""Idempotencia del registro de pagos.

Un cobro parcial puede perderse en la red después de guardarse. Sin una clave
de idempotencia, el reintento del navegador insertaría el abono dos veces. El
backend reserva la clave en ``pagos_idempotentes`` y devuelve la factura ya
cobrada sin duplicar pagos ni movimientos de caja.
"""
from app.db.models import Pago, RegistroCaja
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


def _crear_producto(client, token, codigo="IP1", precio=5000, stock=10):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={
            "codigo": codigo,
            "nombre": "Producto para pagos",
            "precio": precio,
            "stock_inicial": stock,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _vender(client, token, producto_id, cantidad=2):
    resp = client.post(
        "/api/facturas/",
        headers=auth(token),
        json={
            "nombre_eventual": "Cliente de prueba",
            "detalles": [{"producto_id": producto_id, "cantidad": cantidad}],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _pagar(client, token, factura_id, valor, clave=None, forma_pago="Efectivo"):
    headers = auth(token)
    if clave is not None:
        headers["Idempotency-Key"] = clave
    return client.post(
        f"/api/facturas/{factura_id}/pagos",
        headers=headers,
        json={"valor": valor, "forma_pago": forma_pago},
    )


def _conteos(factura_id):
    db = SessionLocal()
    try:
        pagos = db.query(Pago).filter(Pago.factura_id == factura_id).count()
        movimientos = (
            db.query(RegistroCaja)
            .filter(RegistroCaja.referencia == f"Abono a Factura #{factura_id}")
            .count()
        )
        return pagos, movimientos
    finally:
        db.close()


def test_reintento_de_un_abono_parcial_no_lo_duplica(client, token_cajero):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero)
    factura = _vender(client, token_cajero, producto["id"], cantidad=2)

    primera = _pagar(
        client, token_cajero, factura["id"], 3000, clave="pago-parcial-1"
    )
    segunda = _pagar(
        client, token_cajero, factura["id"], 3000, clave="pago-parcial-1"
    )

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["id"] == factura["id"]
    assert segunda.json()["saldo"] == 7000
    assert segunda.json()["estado"] == "Pagado Parcial"
    assert len(segunda.json()["pagos"]) == 1

    assert _conteos(factura["id"]) == (1, 1)

    actualizada = client.get(
        f"/api/facturas/{factura['id']}", headers=auth(token_cajero)
    ).json()
    assert actualizada["saldo"] == 7000
    assert len(actualizada["pagos"]) == 1


def test_reintento_con_otro_cuerpo_devuelve_el_pago_original(client, token_cajero):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero, codigo="IP2")
    factura = _vender(client, token_cajero, producto["id"])

    _pagar(client, token_cajero, factura["id"], 3000, clave="pago-original")
    reintento = _pagar(
        client,
        token_cajero,
        factura["id"],
        8000,
        clave="pago-original",
        forma_pago="Transferencia",
    )

    assert reintento.status_code == 200, reintento.text
    assert reintento.json()["saldo"] == 7000
    assert len(reintento.json()["pagos"]) == 1
    assert reintento.json()["pagos"][0]["valor"] == 3000
    assert reintento.json()["pagos"][0]["forma_pago"] == "Efectivo"


def test_reintento_despues_de_pagar_todo_devuelve_la_factura_pagada(
    client, token_cajero
):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero, codigo="IP3")
    factura = _vender(client, token_cajero, producto["id"])

    primera = _pagar(
        client, token_cajero, factura["id"], factura["total"], clave="pago-total"
    )
    segunda = _pagar(
        client, token_cajero, factura["id"], factura["total"], clave="pago-total"
    )

    assert primera.status_code == 200, primera.text
    # Sin idempotencia este segundo intento respondería 400 ("ya está pagada").
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["estado"] == "Pagada"
    assert segunda.json()["saldo"] == 0
    assert len(segunda.json()["pagos"]) == 1
    assert _conteos(factura["id"]) == (1, 1)


def test_la_clave_de_pago_no_se_puede_reutilizar_en_otra_factura(
    client, token_cajero
):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero, codigo="IP4")
    primera = _vender(client, token_cajero, producto["id"])
    segunda = _vender(client, token_cajero, producto["id"])

    ok = _pagar(client, token_cajero, primera["id"], 3000, clave="pago-cruzado")
    ajena = _pagar(client, token_cajero, segunda["id"], 3000, clave="pago-cruzado")

    assert ok.status_code == 200, ok.text
    assert ajena.status_code == 409, ajena.text
    assert "otra factura" in ajena.json()["detail"].lower()

    sin_cobrar = client.get(
        f"/api/facturas/{segunda['id']}", headers=auth(token_cajero)
    ).json()
    assert sin_cobrar["saldo"] == segunda["total"]
    assert sin_cobrar["pagos"] == []


def test_sin_clave_se_mantienen_los_abonos_normales(client, token_cajero):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero, codigo="IP5")
    factura = _vender(client, token_cajero, producto["id"])

    _pagar(client, token_cajero, factura["id"], 3000)
    segunda = _pagar(client, token_cajero, factura["id"], 3000)

    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["saldo"] == 4000
    assert len(segunda.json()["pagos"]) == 2
    assert _conteos(factura["id"]) == (2, 2)


def test_clave_de_pago_demasiado_larga_se_rechaza(client, token_cajero):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero, codigo="IP6")
    factura = _vender(client, token_cajero, producto["id"])

    respuesta = _pagar(
        client, token_cajero, factura["id"], 3000, clave="x" * 65
    )

    assert respuesta.status_code == 400, respuesta.text
    assert "64" in respuesta.json()["detail"]
    assert _conteos(factura["id"]) == (0, 0)
