"""Pruebas del módulo de ingresos de inventario."""
from .conftest import auth


def _abrir_caja(client, token):
    resp = client.post(
        "/api/caja/abrir",
        headers=auth(token),
        json={"saldo_inicial_efectivo": 0, "saldo_inicial_banco": 0},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _crear_producto(client, token, codigo="P100", nombre="Cerveza", precio=5000, stock=0):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={"codigo": codigo, "nombre": nombre, "precio": precio, "stock_inicial": stock},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_ingreso_requiere_caja_abierta(client, token_cajero):
    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_cajero),
        json={"forma_pago": "Efectivo", "total": 100, "items": []},
    )
    assert resp.status_code == 400
    assert "caja" in resp.json()["detail"].lower()


def test_ingreso_completo_mueve_stock_y_caja(client, token_cajero):
    turno_id = _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero)

    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_cajero),
        json={
            "proveedor": "Distribuidora La Fría",
            "forma_pago": "Efectivo",
            "total": 50000,
            "items": [
                {"tipo": "Producto", "producto_id": producto["id"], "cantidad": 10, "costo_unitario": 5000}
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    ingreso = resp.json()
    assert ingreso["estado"] == "Completo"
    assert ingreso["suma_items"] == 50000
    assert ingreso["turno_caja_id"] == turno_id

    detalle = client.get(f"/api/productos/{producto['id']}", headers=auth(token_cajero)).json()
    assert detalle["stock"] == 10

    movs = client.get(f"/api/caja/{turno_id}/movimientos", headers=auth(token_cajero)).json()
    salidas = [m for m in movs if m["tipo"] == "Salida"]
    assert len(salidas) == 1
    assert salidas[0]["monto"] == 50000
    assert salidas[0]["forma_pago"] == "Efectivo"
    # La compra es dinero que sale: nunca debe quedar como entrada.
    assert [m for m in movs if m["tipo"] == "Entrada"] == []


def test_ingreso_producto_nuevo_genera_codigo(client, token_cajero):
    turno_id = _abrir_caja(client, token_cajero)
    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_cajero),
        json={
            "forma_pago": "Transferencia",
            "total": 30000,
            "items": [
                {"tipo": "Producto nuevo", "concepto": "Vino tinto", "precio": 30000, "cantidad": 3, "costo_unitario": 10000}
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    ingreso = resp.json()
    assert ingreso["estado"] == "Completo"
    producto_id = ingreso["items"][0]["producto_id"]
    assert producto_id is not None

    producto = client.get(f"/api/productos/{producto_id}", headers=auth(token_cajero)).json()
    assert producto["nombre"] == "Vino tinto"
    assert producto["codigo"].startswith("INV")
    assert producto["stock"] == 3

    # Transferencia: sale del bolsillo banco del turno.
    movs = client.get(f"/api/caja/{turno_id}/movimientos", headers=auth(token_cajero)).json()
    salidas = [m for m in movs if m["tipo"] == "Salida"]
    assert len(salidas) == 1
    assert salidas[0]["forma_pago"] == "Transferencia"
    assert salidas[0]["monto"] == 30000


def test_credito_no_mueve_caja(client, token_cajero):
    turno_id = _abrir_caja(client, token_cajero)
    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_cajero),
        json={
            "forma_pago": "Crédito",
            "total": 20000,
            "items": [{"tipo": "Otros", "concepto": "Flete", "valor": 20000}],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "Completo"

    movs = client.get(f"/api/caja/{turno_id}/movimientos", headers=auth(token_cajero)).json()
    assert [m for m in movs if m["tipo"] in ("Entrada", "Salida")] == []


def test_ingreso_parcial_al_faltar_costo(client, token_cajero):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero, codigo="P200", nombre="Agua")
    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_cajero),
        json={
            "forma_pago": "Donación",
            "total": 20000,
            "items": [{"tipo": "Producto", "producto_id": producto["id"], "cantidad": 4}],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "Parcial"


def test_resolver_inconsistente_solo_admin(client, token_cajero, token_admin):
    _abrir_caja(client, token_cajero)
    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_cajero),
        json={
            "forma_pago": "Donación",
            "total": 1000,
            "items": [
                {"tipo": "Otros", "concepto": "Varios", "valor": 5000}
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    ingreso = resp.json()
    assert ingreso["estado"] == "Inconsistente"

    negado = client.post(
        f"/api/ingresos/{ingreso['id']}/resolver",
        headers=auth(token_cajero),
        json={"justificacion": "intento"},
    )
    assert negado.status_code == 403

    resuelto = client.post(
        f"/api/ingresos/{ingreso['id']}/resolver",
        headers=auth(token_admin),
        json={"justificacion": "Se ajustó contra la factura física"},
    )
    assert resuelto.status_code == 200, resuelto.text
    assert resuelto.json()["estado"] == "Completo"
    assert resuelto.json()["justificacion"].startswith("Se ajustó")