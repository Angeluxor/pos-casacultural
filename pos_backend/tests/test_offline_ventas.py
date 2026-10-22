"""Sincronización de ventas y cobros creados sin conexión.

Una venta offline se guarda primero en el dispositivo y se envía al servidor
cuando vuelve la red. Debe conservar la fecha, el turno y los precios que se
cobraron realmente, y no puede rechazarse solo porque el stock local estaba
desactualizado.
"""
from app.db.models import Factura, Pago
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


def _cerrar_caja(client, token, turno_id):
    resp = client.put(
        f"/api/caja/{turno_id}/cerrar",
        headers=auth(token),
        json={"saldo_final_real_efectivo": 0, "saldo_final_real_banco": 0},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _crear_producto(client, token, codigo="OFF1", precio=5000, stock=10):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={
            "codigo": codigo,
            "nombre": "Producto offline",
            "precio": precio,
            "stock_inicial": stock,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _vender_offline(
    client,
    token,
    producto_id,
    turno_id,
    cantidad=2,
    precio_unitario=4000,
    fecha="2026-10-20T15:00:00-05:00",
    clave="venta-offline-1",
):
    headers = auth(token)
    headers["Idempotency-Key"] = clave
    return client.post(
        "/api/facturas/",
        headers=headers,
        json={
            "nombre_eventual": "Cliente offline",
            "fecha": fecha,
            "turno_caja_id": turno_id,
            "origen_offline": True,
            "detalles": [
                {
                    "producto_id": producto_id,
                    "cantidad": cantidad,
                    "precio_unitario": precio_unitario,
                }
            ],
        },
    )


def test_venta_offline_conserva_fecha_turno_y_precio(client, token_cajero):
    turno_id = _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero, precio=5000, stock=10)

    resp = _vender_offline(
        client, token_cajero, producto["id"], turno_id, cantidad=2, precio_unitario=4000
    )

    assert resp.status_code == 200, resp.text
    factura = resp.json()
    assert factura["total"] == 8000
    assert factura["fecha"].startswith("2026-10-20")
    assert factura["turno_caja_id"] == turno_id
    assert factura["origen"] == "offline"
    assert factura["requiere_revision"] is False
    assert factura["detalles"][0]["precio_unitario"] == 4000

    actualizado = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_cajero)
    ).json()
    assert actualizado["stock"] == 8


def test_venta_offline_permite_stock_negativo_y_marca_revision(
    client, token_cajero
):
    turno_id = _abrir_caja(client, token_cajero)
    producto = _crear_producto(
        client, token_cajero, codigo="OFF2", precio=5000, stock=1
    )

    resp = _vender_offline(
        client, token_cajero, producto["id"], turno_id, cantidad=3, precio_unitario=5000
    )

    assert resp.status_code == 200, resp.text
    factura = resp.json()
    assert factura["total"] == 15000
    assert factura["requiere_revision"] is True
    assert "Stock insuficiente" in factura["nota_revision"]

    actualizado = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_cajero)
    ).json()
    assert actualizado["stock"] == -2


def test_venta_online_ignora_el_precio_enviado_por_el_cliente(
    client, token_cajero
):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(
        client, token_cajero, codigo="OFF3", precio=5000, stock=10
    )

    resp = client.post(
        "/api/facturas/",
        headers=auth(token_cajero),
        json={
            "nombre_eventual": "Cliente online",
            "detalles": [
                {
                    "producto_id": producto["id"],
                    "cantidad": 1,
                    "precio_unitario": 1000,
                }
            ],
        },
    )

    assert resp.status_code == 200, resp.text
    factura = resp.json()
    assert factura["total"] == 5000
    assert factura["origen"] == "online"
    assert factura["requiere_revision"] is False
    assert factura["detalles"][0]["precio_unitario"] == 5000


def test_pago_offline_conserva_fecha_y_turno(client, token_cajero):
    turno_id = _abrir_caja(client, token_cajero)
    producto = _crear_producto(
        client, token_cajero, codigo="OFF4", precio=5000, stock=10
    )
    factura = client.post(
        "/api/facturas/",
        headers=auth(token_cajero),
        json={
            "nombre_eventual": "Cliente offline",
            "detalles": [{"producto_id": producto["id"], "cantidad": 1}],
        },
    ).json()

    headers = auth(token_cajero)
    headers["Idempotency-Key"] = "pago-offline-1"
    headers["X-Turno-Caja-Id"] = str(turno_id)
    resp = client.post(
        f"/api/facturas/{factura['id']}/pagos",
        headers=headers,
        json={
            "valor": factura["total"],
            "forma_pago": "Efectivo",
            "fecha": "2026-10-20T15:30:00-05:00",
        },
    )

    assert resp.status_code == 200, resp.text
    pagada = resp.json()
    assert pagada["estado"] == "Pagada"
    assert pagada["pagos"][0]["fecha"].startswith("2026-10-20")

    movimientos = client.get(
        f"/api/caja/{turno_id}/movimientos", headers=auth(token_cajero)
    ).json()
    abono = next(m for m in movimientos if m["referencia"] == f"Abono a Factura #{factura['id']}")
    assert abono["fecha"].startswith("2026-10-20")
    assert abono["turno_caja_id"] == turno_id

    db = SessionLocal()
    try:
        pago = db.query(Pago).filter(Pago.factura_id == factura["id"]).one()
        assert pago.fecha.strftime("%Y-%m-%d") == "2026-10-20"
    finally:
        db.close()


def test_venta_offline_en_turno_cerrado_se_marca_y_no_permite_cobrar(
    client, token_cajero
):
    turno_id = _abrir_caja(client, token_cajero)
    _cerrar_caja(client, token_cajero, turno_id)
    producto = _crear_producto(
        client, token_cajero, codigo="OFF5", precio=5000, stock=10
    )

    venta = _vender_offline(
        client,
        token_cajero,
        producto["id"],
        turno_id,
        cantidad=1,
        precio_unitario=5000,
        clave="venta-offline-cerrada",
    )
    assert venta.status_code == 200, venta.text
    factura = venta.json()
    assert factura["requiere_revision"] is True
    assert "turno" in factura["nota_revision"].lower()

    headers = auth(token_cajero)
    headers["X-Turno-Caja-Id"] = str(turno_id)
    cobro = client.post(
        f"/api/facturas/{factura['id']}/pagos",
        headers=headers,
        json={"valor": factura["total"], "forma_pago": "Efectivo"},
    )

    assert cobro.status_code == 400, cobro.text
    assert "cerrado" in cobro.json()["detail"].lower()

    db = SessionLocal()
    try:
        assert db.query(Pago).filter(Pago.factura_id == factura["id"]).count() == 0
        assert db.query(Factura).filter(Factura.id == factura["id"]).one().saldo == 5000
    finally:
        db.close()


def test_venta_online_ignora_fecha_y_turno_enviados_por_el_cliente(
    client, token_cajero
):
    turno_id = _abrir_caja(client, token_cajero)
    producto = _crear_producto(
        client, token_cajero, codigo="OFF6", precio=5000, stock=10
    )

    resp = client.post(
        "/api/facturas/",
        headers=auth(token_cajero),
        json={
            "nombre_eventual": "Cliente online",
            "fecha": "2026-10-20T15:00:00-05:00",
            # Un turno inexistente solo debe ignorarse en ventas online.
            "turno_caja_id": 999999,
            "detalles": [{"producto_id": producto["id"], "cantidad": 1}],
        },
    )

    assert resp.status_code == 200, resp.text
    factura = resp.json()
    assert not factura["fecha"].startswith("2026-10-20")
    assert factura["turno_caja_id"] == turno_id
    assert factura["origen"] == "online"
