"""Abono al saldo total de un cliente (ticket de feedback #11).

Un cliente con varias facturas pendientes paga de una sola vez; el dinero se
reparte de la factura más antigua a la más reciente.
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


def _cliente(client, token, nombre="Cliente Deudor"):
    resp = client.post("/api/clientes/", headers=auth(token), json={"nombre": nombre})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _producto(client, token):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={"codigo": "AB1", "nombre": "Producto", "precio": 1000, "stock_inicial": 100},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _vender(client, token, cliente_id, producto_id, cantidad):
    resp = client.post(
        "/api/facturas/",
        headers=auth(token),
        json={
            "cliente_id": cliente_id,
            "detalles": [{"producto_id": producto_id, "cantidad": cantidad}],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _abonar(client, token, cliente_id, pagos, clave=None):
    headers = auth(token)
    if clave:
        headers["Idempotency-Key"] = clave
    return client.post(
        "/api/facturas/abono-cliente",
        headers=headers,
        json={"cliente_id": cliente_id, "pagos": pagos},
    )


def _escenario(client, token):
    """Cliente con tres facturas de 1000, 2000 y 3000 (en ese orden)."""
    _abrir_caja(client, token)
    cliente = _cliente(client, token)
    producto = _producto(client, token)
    facturas = [_vender(client, token, cliente, producto, n) for n in (1, 2, 3)]
    return cliente, facturas


def _factura(client, token, factura_id):
    resp = client.get(f"/api/facturas/{factura_id}", headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_consulta_saldo_pendiente_del_cliente(client, token_cajero):
    cliente, facturas = _escenario(client, token_cajero)

    resp = client.get(f"/api/facturas/saldo-cliente/{cliente}", headers=auth(token_cajero))

    assert resp.status_code == 200, resp.text
    datos = resp.json()
    assert datos["saldo_total"] == 6000
    assert [f["id"] for f in datos["facturas"]] == facturas


def test_abono_total_salda_todas_las_facturas(client, token_cajero):
    cliente, facturas = _escenario(client, token_cajero)

    resp = _abonar(client, token_cajero, cliente, [{"valor": 6000, "forma_pago": "Efectivo"}])

    assert resp.status_code == 200, resp.text
    datos = resp.json()
    assert datos["total_abonado"] == 6000
    assert datos["saldo_restante"] == 0
    assert datos["facturas_pagadas"] == 3
    for fid in facturas:
        f = _factura(client, token_cajero, fid)
        assert f["saldo"] == 0
        assert f["estado"] == "Pagada"


def test_abono_parcial_paga_primero_la_mas_antigua(client, token_cajero):
    cliente, facturas = _escenario(client, token_cajero)

    resp = _abonar(client, token_cajero, cliente, [{"valor": 2500, "forma_pago": "Efectivo"}])

    assert resp.status_code == 200, resp.text
    assert resp.json()["saldo_restante"] == 3500
    assert resp.json()["facturas_pagadas"] == 1
    primera, segunda, tercera = (_factura(client, token_cajero, f) for f in facturas)
    assert (primera["saldo"], primera["estado"]) == (0, "Pagada")
    assert (segunda["saldo"], segunda["estado"]) == (500, "Pagado Parcial")
    assert tercera["saldo"] == 3000


def test_medios_de_pago_combinados_se_reparten_y_registran_caja(client, token_cajero):
    cliente, facturas = _escenario(client, token_cajero)

    resp = _abonar(
        client,
        token_cajero,
        cliente,
        [
            {"valor": 1500, "forma_pago": "Efectivo"},
            {"valor": 4500, "forma_pago": "Transferencia"},
        ],
    )

    assert resp.status_code == 200, resp.text
    db = SessionLocal()
    try:
        pagos = db.query(Pago).filter(Pago.factura_id.in_(facturas)).all()
        movimientos = (
            db.query(RegistroCaja)
            .filter(RegistroCaja.referencia.in_([f"Abono a Factura #{f}" for f in facturas]))
            .all()
        )
        # Lo cobrado en cada medio coincide con lo entregado.
        por_medio = {}
        for p in pagos:
            por_medio[p.forma_pago.value] = por_medio.get(p.forma_pago.value, 0) + p.valor
        assert por_medio == {"Efectivo": 1500, "Transferencia": 4500}
        assert round(sum(m.monto for m in movimientos), 2) == 6000
    finally:
        db.close()


def test_abono_mayor_al_saldo_se_rechaza_sin_cobrar(client, token_cajero):
    cliente, facturas = _escenario(client, token_cajero)

    resp = _abonar(client, token_cajero, cliente, [{"valor": 6001, "forma_pago": "Efectivo"}])

    assert resp.status_code == 400
    assert all(_factura(client, token_cajero, f)["saldo"] > 0 for f in facturas)


def test_reintento_con_la_misma_clave_no_duplica(client, token_cajero):
    cliente, facturas = _escenario(client, token_cajero)
    pagos = [{"valor": 2500, "forma_pago": "Efectivo"}]

    primera = _abonar(client, token_cajero, cliente, pagos, clave="abono-1")
    segunda = _abonar(client, token_cajero, cliente, pagos, clave="abono-1")

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["total_abonado"] == 0
    assert segunda.json()["saldo_restante"] == 3500
    db = SessionLocal()
    try:
        assert db.query(Pago).filter(Pago.factura_id.in_(facturas)).count() == 2
    finally:
        db.close()


def test_sin_caja_abierta_no_se_puede_abonar(client, token_cajero):
    cliente = _cliente(client, token_cajero)

    resp = _abonar(client, token_cajero, cliente, [{"valor": 100, "forma_pago": "Efectivo"}])

    assert resp.status_code == 400
    assert "caja" in resp.json()["detail"].lower()


def test_cliente_sin_saldo_pendiente(client, token_cajero):
    _abrir_caja(client, token_cajero)
    cliente = _cliente(client, token_cajero)

    resp = _abonar(client, token_cajero, cliente, [{"valor": 100, "forma_pago": "Efectivo"}])

    assert resp.status_code == 400
    assert "saldo pendiente" in resp.json()["detail"]
