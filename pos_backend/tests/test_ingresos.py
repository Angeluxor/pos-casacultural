"""Pruebas del módulo de ingresos de inventario."""
from .conftest import auth


def _abrir_caja(client, token, efectivo=0, banco=0):
    resp = client.post(
        "/api/caja/abrir",
        headers=auth(token),
        json={
            "saldo_inicial_efectivo": efectivo,
            "saldo_inicial_banco": banco,
        },
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
    assert "balance general" in resp.json()["detail"].lower()


def test_ingreso_caja_activa_credito_tambien_requiere_caja(client, token_cajero):
    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_cajero),
        json={
            "fuente_pago": "Caja activa",
            "forma_pago": "Crédito",
            "total": 100,
            "items": [{"tipo": "Otros", "concepto": "Flete", "valor": 100}],
        },
    )
    assert resp.status_code == 400
    assert "caja" in resp.json()["detail"].lower()


def test_ingreso_balance_efectivo_no_exige_caja_ni_mueve_caja(client, token_admin):
    producto = _crear_producto(client, token_admin, codigo="BAL-EF", nombre="Harina")

    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_admin),
        json={
            "proveedor": "Proveedor externo",
            "fuente_pago": "Balance general",
            "forma_pago": "Efectivo",
            "total": 10000,
            "items": [
                {
                    "tipo": "Producto",
                    "producto_id": producto["id"],
                    "cantidad": 2,
                    "costo_unitario": 5000,
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    ingreso = resp.json()
    assert ingreso["fuente_pago"] == "Balance general"
    assert ingreso["turno_caja_id"] is None
    assert ingreso["pagado"] is True
    assert ingreso["estado_pago"] == "Pagado"
    assert ingreso["forma_pago_pago"] == "Efectivo"

    detalle = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_admin)
    ).json()
    assert detalle["stock"] == 2

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["caja"]["abierta"] is False
    assert balance["caja"]["efectivo"] == 0
    assert balance["caja"]["banco"] == 0
    assert balance["activos"]["inventario"] == 10000
    assert balance["activos"]["total"] == 10000
    assert balance["pasivos"]["cuentas_por_pagar"] == 0
    # La compra ya pagada por fuera entra como activo; la contrapartida queda
    # en el patrimonio residual.
    assert balance["patrimonio"]["total"] == 10000
    assert balance["resultados"]["gastos"] == 0


def test_ingreso_balance_credito_genera_pasivo_y_se_paga_desde_caja(
    client, token_admin
):
    producto = _crear_producto(client, token_admin, codigo="BAL-CR", nombre="Aceite")

    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_admin),
        json={
            "proveedor": "Proveedor crédito externo",
            "fuente_pago": "Balance general",
            "forma_pago": "Crédito",
            "total": 20000,
            "items": [
                {
                    "tipo": "Producto",
                    "producto_id": producto["id"],
                    "cantidad": 2,
                    "costo_unitario": 10000,
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    ingreso = resp.json()
    assert ingreso["fuente_pago"] == "Balance general"
    assert ingreso["turno_caja_id"] is None
    assert ingreso["pagado"] is False
    assert ingreso["estado_pago"] == "Pendiente"

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["caja"]["abierta"] is False
    assert balance["activos"]["inventario"] == 20000
    assert balance["pasivos"]["cuentas_por_pagar"] == 20000
    assert balance["patrimonio"]["total"] == 0
    assert balance["compras_credito_pendientes"] == 1
    assert balance["cuentas_por_pagar"][0]["ingreso_id"] == ingreso["id"]

    # Aunque el ingreso se cargó al balance, el pago posterior sí sale de la
    # caja abierta.
    _abrir_caja(client, token_admin, efectivo=50000)
    pago = client.post(
        f"/api/ingresos/{ingreso['id']}/pagar",
        headers=auth(token_admin),
        json={"forma_pago": "Efectivo"},
    )
    assert pago.status_code == 200, pago.text
    assert pago.json()["pagado"] is True

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["caja"]["efectivo"] == 30000
    assert balance["activos"]["inventario"] == 20000
    assert balance["activos"]["total"] == 50000
    assert balance["pasivos"]["cuentas_por_pagar"] == 0
    assert balance["patrimonio"]["total"] == 50000
    assert balance["resultados"]["gastos"] == 0
    assert balance["resultados"]["utilidad"] == 0


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
    assert ingreso["fuente_pago"] == "Caja activa"
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