"""Resumen de ventas del turno para el cierre de caja.

La caja se calcula solo con movimientos reales, así que una venta a crédito
nunca sumó. Para que el cierre lo refleje, el resumen del turno muestra las
ventas facturadas, resta la parte a crédito (no cobrada) y deja el total cobrado.
"""
from .conftest import auth


def _abrir(client, token):
    resp = client.post(
        "/api/caja/abrir",
        headers=auth(token),
        json={"saldo_inicial_efectivo": 0, "saldo_inicial_banco": 0},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _producto(client, token, precio=10000, stock=50):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={"codigo": "PV1", "nombre": "Producto venta", "precio": precio, "stock_inicial": stock},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _cliente(client, token):
    resp = client.post(
        "/api/clientes/",
        headers=auth(token),
        json={"nombre": "Cliente Cierre", "celular": "3000000000"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _vender(client, token, producto_id, cantidad, cliente_id=None):
    resp = client.post(
        "/api/facturas/",
        headers=auth(token),
        json={
            "cliente_id": cliente_id,
            "detalles": [{"producto_id": producto_id, "cantidad": cantidad}],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _pagar(client, token, factura_id, valor):
    resp = client.post(
        f"/api/facturas/{factura_id}/pagos",
        headers=auth(token),
        json={"valor": valor, "forma_pago": "Efectivo"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _resumen(client, token, turno_id):
    resp = client.get(f"/api/caja/{turno_id}/resumen-ventas", headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_resumen_ventas_resta_el_credito(client, token_cajero):
    turno = _abrir(client, token_cajero)
    p = _producto(client, token_cajero)
    c = _cliente(client, token_cajero)

    # Pagada: 30.000 cobrados.
    pagada = _vender(client, token_cajero, p["id"], 3, c["id"])
    _pagar(client, token_cajero, pagada["id"], 30000)
    # Pagado parcial: 30.000 facturados, 10.000 cobrados (20.000 quedan a crédito).
    parcial = _vender(client, token_cajero, p["id"], 3, c["id"])
    _pagar(client, token_cajero, parcial["id"], 10000)
    # Sin pagar: 10.000 a crédito.
    _vender(client, token_cajero, p["id"], 1, c["id"])

    r = _resumen(client, token_cajero, turno)
    assert r["ventas"] == 70000
    assert r["creditos"] == 30000
    assert r["cobrado"] == 40000


def test_resumen_ventas_excluye_facturas_anuladas(client, token_admin):
    turno = _abrir(client, token_admin)
    p = _producto(client, token_admin, stock=50)
    c = _cliente(client, token_admin)

    vendida = _vender(client, token_admin, p["id"], 3, c["id"])
    _pagar(client, token_admin, vendida["id"], 30000)

    anulada = _vender(client, token_admin, p["id"], 2, c["id"])
    resp = client.post(
        f"/api/facturas/{anulada['id']}/anular",
        headers=auth(token_admin),
        json={"motivo": "Prueba"},
    )
    assert resp.status_code == 200, resp.text

    r = _resumen(client, token_admin, turno)
    assert r["ventas"] == 30000
    assert r["creditos"] == 0
    assert r["cobrado"] == 30000
