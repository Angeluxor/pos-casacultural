"""Pruebas del estado de facturas (Abierta/Crédito), cliente eventual y cierre de caja."""
from .conftest import auth


def _abrir_caja(client, token):
    resp = client.post(
        "/api/caja/abrir",
        headers=auth(token),
        json={"saldo_inicial_efectivo": 0, "saldo_inicial_banco": 0},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _crear_producto(client, token, codigo="P200", nombre="Cerveza", precio=5000, stock=10):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={"codigo": codigo, "nombre": nombre, "precio": precio, "stock_inicial": stock},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _crear_cliente(client, token, nombre="Ana Pérez"):
    resp = client.post("/api/clientes/", headers=auth(token), json={"nombre": nombre})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _vender(client, token, producto_id, cantidad=1, cliente_id=None, nombre_eventual=None):
    resp = client.post(
        "/api/facturas/",
        headers=auth(token),
        json={
            "cliente_id": cliente_id,
            "nombre_eventual": nombre_eventual,
            "detalles": [{"producto_id": producto_id, "cantidad": cantidad}],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _cerrar(client, token, turno_id):
    return client.put(
        f"/api/caja/{turno_id}/cerrar",
        headers=auth(token),
        json={"saldo_final_real_efectivo": 0, "saldo_final_real_banco": 0},
    )


def test_venta_sin_cliente_usa_cliente_eventual(client, token_cajero):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero)

    factura = _vender(client, token_cajero, producto["id"])

    assert factura["estado"] == "Abierta"
    assert factura["turno_caja_id"] is not None
    assert factura["cliente_id"] is not None
    assert factura["cliente_nombre"] == "Cliente eventual"
    assert factura["nombre_eventual"] is None


def test_venta_con_nombre_eventual_lo_guarda(client, token_cajero):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero)

    factura = _vender(client, token_cajero, producto["id"], nombre_eventual="Señor de la mesa 3")

    assert factura["nombre_eventual"] == "Señor de la mesa 3"
    assert factura["cliente_nombre"] == "Señor de la mesa 3"


def test_cierre_pasa_factura_de_cliente_real_a_credito(client, token_cajero):
    turno_id = _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero)
    cliente = _crear_cliente(client, token_cajero)
    factura = _vender(client, token_cajero, producto["id"], cliente_id=cliente["id"])

    resp = _cerrar(client, token_cajero, turno_id)
    assert resp.status_code == 200, resp.text

    actualizada = client.get(f"/api/facturas/{factura['id']}", headers=auth(token_cajero)).json()
    assert actualizada["estado"] == "Crédito"


def test_cierre_bloqueado_por_factura_de_cliente_eventual(client, token_cajero):
    turno_id = _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero)
    factura = _vender(client, token_cajero, producto["id"])

    pendientes = client.get(
        f"/api/caja/{turno_id}/pendientes", headers=auth(token_cajero)
    ).json()
    assert len(pendientes) == 1
    assert pendientes[0]["es_eventual"] is True

    resp = _cerrar(client, token_cajero, turno_id)
    assert resp.status_code == 400
    assert "eventual" in resp.json()["detail"].lower()

    # La factura sigue abierta y la caja sigue abierta.
    actualizada = client.get(f"/api/facturas/{factura['id']}", headers=auth(token_cajero)).json()
    assert actualizada["estado"] == "Abierta"
    activa = client.get("/api/caja/activa", headers=auth(token_cajero))
    assert activa.status_code == 200


def test_cierre_permite_factura_eventual_ya_pagada(client, token_cajero):
    turno_id = _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero)
    factura = _vender(client, token_cajero, producto["id"])

    pago = client.post(
        f"/api/facturas/{factura['id']}/pagos",
        headers=auth(token_cajero),
        json={"valor": factura["total"], "forma_pago": "Efectivo"},
    )
    assert pago.status_code == 200, pago.text
    assert pago.json()["estado"] == "Pagada"

    resp = _cerrar(client, token_cajero, turno_id)
    assert resp.status_code == 200, resp.text


def test_asignar_cliente_real_destraba_cierre(client, token_cajero):
    turno_id = _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero)
    cliente = _crear_cliente(client, token_cajero)
    factura = _vender(client, token_cajero, producto["id"], nombre_eventual="Mesa 5")

    resp = client.put(
        f"/api/facturas/{factura['id']}/cliente",
        headers=auth(token_cajero),
        json={"cliente_id": cliente["id"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["cliente_id"] == cliente["id"]
    assert resp.json()["nombre_eventual"] is None
    assert resp.json()["cliente_nombre"] == "Ana Pérez"

    cierre = _cerrar(client, token_cajero, turno_id)
    assert cierre.status_code == 200, cierre.text
    actualizada = client.get(f"/api/facturas/{factura['id']}", headers=auth(token_cajero)).json()
    assert actualizada["estado"] == "Crédito"


def test_filtro_facturas_por_estado(client, token_cajero):
    turno_id = _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero)
    cliente = _crear_cliente(client, token_cajero)

    _vender(client, token_cajero, producto["id"])  # eventual -> Abierta
    factura_real = _vender(
        client, token_cajero, producto["id"], cliente_id=cliente["id"]
    )  # Abierta

    # Pagar la factura eventual para poder cerrar sin bloqueo.
    eventual = client.get("/api/facturas/", headers=auth(token_cajero)).json()["items"]
    factura_eventual = next(f for f in eventual if f["id"] != factura_real["id"])
    client.post(
        f"/api/facturas/{factura_eventual['id']}/pagos",
        headers=auth(token_cajero),
        json={"valor": factura_eventual["total"], "forma_pago": "Efectivo"},
    )

    _cerrar(client, token_cajero, turno_id)

    abiertas = client.get(
        "/api/facturas/?estado=Abierta", headers=auth(token_cajero)
    ).json()
    assert abiertas["total"] == 0

    credito = client.get(
        "/api/facturas/?estado=Cr%C3%A9dito", headers=auth(token_cajero)
    ).json()
    assert credito["total"] == 1

    # La factura eventual pagada... en este caso quedó abierta y bloqueó; solo
    # validamos el filtro. Revisamos estados devueltos:
    estados = {f["estado"] for f in credito["items"]}
    assert estados == {"Crédito"}


def test_pago_combinado_registra_varios_medios(client, token_cajero):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero, codigo="P210", nombre="Michelada", precio=5000)
    factura = _vender(client, token_cajero, producto["id"], cantidad=2)
    total = factura["total"]

    resp = client.post(
        f"/api/facturas/{factura['id']}/pagos",
        headers=auth(token_cajero),
        json=[
            {"valor": total / 2, "forma_pago": "Efectivo"},
            {"valor": total / 2, "forma_pago": "Transferencia"},
        ],
    )
    assert resp.status_code == 200, resp.text
    actualizada = resp.json()
    assert actualizada["estado"] == "Pagada"
    assert actualizada["saldo"] == 0
    assert len(actualizada["pagos"]) == 2
    assert {p["forma_pago"] for p in actualizada["pagos"]} == {"Efectivo", "Transferencia"}


def test_pago_combinado_que_excede_el_saldo_es_rechazado(client, token_cajero):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero, codigo="P211", nombre="Michelada doble")
    factura = _vender(client, token_cajero, producto["id"])

    resp = client.post(
        f"/api/facturas/{factura['id']}/pagos",
        headers=auth(token_cajero),
        json=[
            {"valor": factura["total"], "forma_pago": "Efectivo"},
            {"valor": 1000, "forma_pago": "Tarjeta"},
        ],
    )
    assert resp.status_code == 400

    actualizada = client.get(f"/api/facturas/{factura['id']}", headers=auth(token_cajero)).json()
    assert actualizada["estado"] == "Abierta"


def test_factura_pagada_no_permite_bajar_cantidad_ni_retirar(client, token_cajero):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero, codigo="P212", nombre="Michelada triple")
    factura = _vender(client, token_cajero, producto["id"], cantidad=3)
    detalle_id = factura["detalles"][0]["id"]

    client.post(
        f"/api/facturas/{factura['id']}/pagos",
        headers=auth(token_cajero),
        json={"valor": factura["total"], "forma_pago": "Efectivo"},
    )

    bajar = client.put(
        f"/api/facturas/{factura['id']}/items/{detalle_id}",
        headers=auth(token_cajero),
        json={"cantidad": 2},
    )
    assert bajar.status_code == 400

    retirar = client.delete(
        f"/api/facturas/{factura['id']}/items/{detalle_id}", headers=auth(token_cajero)
    )
    assert retirar.status_code == 400


def test_factura_credito_solo_permite_aumentar(client, token_cajero):
    turno_id = _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero, codigo="P213", nombre="Michelada crédito")
    cliente = _crear_cliente(client, token_cajero, nombre="Cliente Crédito")
    factura = _vender(client, token_cajero, producto["id"], cantidad=2, cliente_id=cliente["id"])
    detalle_id = factura["detalles"][0]["id"]

    assert _cerrar(client, token_cajero, turno_id).status_code == 200

    bajar = client.put(
        f"/api/facturas/{factura['id']}/items/{detalle_id}",
        headers=auth(token_cajero),
        json={"cantidad": 1},
    )
    assert bajar.status_code == 400

    retirar = client.delete(
        f"/api/facturas/{factura['id']}/items/{detalle_id}", headers=auth(token_cajero)
    )
    assert retirar.status_code == 400

    aumentar = client.put(
        f"/api/facturas/{factura['id']}/items/{detalle_id}",
        headers=auth(token_cajero),
        json={"cantidad": 3},
    )
    assert aumentar.status_code == 200, aumentar.text
    assert aumentar.json()["detalles"][0]["cantidad"] == 3
