"""Regresión: editar items de una factura no debe mover la caja.

Editar cantidades es solo un ajuste de la venta (servicio a la mesa); no es un
evento de dinero. Antes se registraba un "reembolso" en efectivo cada vez que la
edición dejaba la factura sobrepagada, lo que generaba salidas fantasma en la
caja (acumulables) y, al anular, dobles devoluciones.
"""
from .conftest import auth


def _abrir(client, token):
    return client.post(
        "/api/caja/abrir",
        headers=auth(token),
        json={"saldo_inicial_efectivo": 0, "saldo_inicial_banco": 0},
    ).json()["id"]


def _producto(client, token, precio=10000, stock=50):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={"codigo": "PD1", "nombre": "Producto devolución", "precio": precio, "stock_inicial": stock},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _vender(client, token, producto_id, cantidad):
    resp = client.post(
        "/api/facturas/",
        headers=auth(token),
        json={"detalles": [{"producto_id": producto_id, "cantidad": cantidad}]},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _pagar(client, token, factura_id, valor, forma="Efectivo"):
    resp = client.post(
        f"/api/facturas/{factura_id}/pagos",
        headers=auth(token),
        json={"valor": valor, "forma_pago": forma},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fijar_cantidad(client, token, factura_id, detalle_id, cantidad):
    return client.put(
        f"/api/facturas/{factura_id}/items/{detalle_id}",
        headers=auth(token),
        json={"cantidad": cantidad},
    )


def _caja(client, token, turno_id):
    movs = client.get(f"/api/caja/{turno_id}/movimientos", headers=auth(token)).json()
    entradas = round(sum(m["monto"] for m in movs if m["tipo"] == "Entrada"), 2)
    salidas = round(sum(m["monto"] for m in movs if m["tipo"] == "Salida"), 2)
    return movs, entradas, salidas


def _pagado(factura):
    return round(sum(p["valor"] for p in factura["pagos"]), 2)


def test_bajar_cantidad_no_genera_movimiento_de_caja(client, token_cajero):
    turno = _abrir(client, token_cajero)
    p = _producto(client, token_cajero)  # 10000
    f = _vender(client, token_cajero, p["id"], 3)  # total 30000
    detalle_id = f["detalles"][0]["id"]
    _pagar(client, token_cajero, f["id"], 15000)

    baja = _fijar_cantidad(client, token_cajero, f["id"], detalle_id, 1)
    assert baja.status_code == 200, baja.text
    cuerpo = baja.json()
    # Queda cubierta por el pago: Pagada, saldo 0, y el exceso es saldo a favor.
    assert cuerpo["estado"] == "Pagada"
    assert cuerpo["saldo"] == 0
    assert _pagado(cuerpo) - cuerpo["total"] == 5000

    movs, entradas, salidas = _caja(client, token_cajero, turno)
    assert entradas == 15000
    assert salidas == 0, movs
    # Solo existe el movimiento del cobro real.
    assert [m["tipo"] for m in movs if m["tipo"] in ("Entrada", "Salida")] == ["Entrada"]


def test_alternar_cantidad_no_acumula_movimientos(client, token_cajero):
    turno = _abrir(client, token_cajero)
    p = _producto(client, token_cajero)
    f = _vender(client, token_cajero, p["id"], 3)
    detalle_id = f["detalles"][0]["id"]
    _pagar(client, token_cajero, f["id"], 15000)

    for _ in range(3):
        _fijar_cantidad(client, token_cajero, f["id"], detalle_id, 1)
        _fijar_cantidad(client, token_cajero, f["id"], detalle_id, 3)

    movs, entradas, salidas = _caja(client, token_cajero, turno)
    assert entradas == 15000
    assert salidas == 0, movs

    # La factura vuelve a deber el saldo pendiente.
    actual = client.get(f"/api/facturas/{f['id']}", headers=auth(token_cajero)).json()
    assert actual["saldo"] == 15000
    assert actual["estado"] == "Pagado Parcial"


def test_editar_items_nunca_usa_el_bolsillo_equivocado(client, token_cajero):
    turno = _abrir(client, token_cajero)
    p = _producto(client, token_cajero)
    f = _vender(client, token_cajero, p["id"], 3)
    detalle_id = f["detalles"][0]["id"]
    _pagar(client, token_cajero, f["id"], 15000, forma="Tarjeta")

    _fijar_cantidad(client, token_cajero, f["id"], detalle_id, 1)
    # Subir de nuevo tampoco debe inventar un ingreso.
    _fijar_cantidad(client, token_cajero, f["id"], detalle_id, 3)

    movs, entradas, salidas = _caja(client, token_cajero, turno)
    assert salidas == 0, movs
    tipos_formas = [(m["tipo"], m["forma_pago"]) for m in movs]
    assert tipos_formas == [("Entrada", "Tarjeta")]


def test_anular_tras_editar_devuelve_solo_lo_cobrado(client, token_admin):
    turno = _abrir(client, token_admin)
    p = _producto(client, token_admin)
    f = _vender(client, token_admin, p["id"], 3)
    detalle_id = f["detalles"][0]["id"]
    _pagar(client, token_admin, f["id"], 15000)

    _fijar_cantidad(client, token_admin, f["id"], detalle_id, 1)

    anular = client.post(
        f"/api/facturas/{f['id']}/anular",
        headers=auth(token_admin),
        json={"motivo": "Error de digitación"},
    )
    assert anular.status_code == 200, anular.text

    movs, entradas, salidas = _caja(client, token_admin, turno)
    # Se cobró 15000 y se devolvieron exactamente 15000: la caja queda en cero.
    assert entradas == 15000
    assert salidas == 15000, movs
