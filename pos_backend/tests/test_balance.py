"""Pruebas del balance general operativo y de las cuentas por pagar."""
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


def _cerrar_caja(client, token, turno_id, efectivo, banco):
    resp = client.put(
        f"/api/caja/{turno_id}/cerrar",
        headers=auth(token),
        json={
            "saldo_final_real_efectivo": efectivo,
            "saldo_final_real_banco": banco,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _crear_producto(
    client, token, codigo, nombre, precio, stock=0
):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={
            "codigo": codigo,
            "nombre": nombre,
            "precio": precio,
            "stock_inicial": stock,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _ingreso(client, token, forma_pago, total, items, proveedor=None):
    resp = client.post(
        "/api/ingresos/",
        headers=auth(token),
        json={
            "proveedor": proveedor,
            "forma_pago": forma_pago,
            "total": total,
            "items": items,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _vender(client, token, producto_id, cantidad=1):
    resp = client.post(
        "/api/facturas/",
        headers=auth(token),
        json={"detalles": [{"producto_id": producto_id, "cantidad": cantidad}]},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_balance_valora_inventario_promedio_y_respaldo(client, token_admin):
    turno_id = _abrir_caja(client, token_admin, efectivo=100000, banco=100000)
    producto = _crear_producto(
        client, token_admin, "BAL1", "Producto con costo", 10000
    )
    producto_sin_costo = _crear_producto(
        client, token_admin, "BAL2", "Producto sin costo", 8000, stock=5
    )

    # Compra de contado: 10 unidades a 6.000.
    _ingreso(
        client,
        token_admin,
        "Efectivo",
        60000,
        [
            {
                "tipo": "Producto",
                "producto_id": producto["id"],
                "cantidad": 10,
                "costo_unitario": 6000,
            }
        ],
        proveedor="Proveedor contado",
    )
    # Compra a crédito: 10 unidades a 8.000. Costo promedio = 7.000.
    credito = _ingreso(
        client,
        token_admin,
        "Crédito",
        80000,
        [
            {
                "tipo": "Producto",
                "producto_id": producto["id"],
                "cantidad": 10,
                "costo_unitario": 8000,
            }
        ],
        proveedor="Proveedor crédito",
    )
    assert credito["pagado"] is False
    assert credito["estado_pago"] == "Pendiente"

    factura_a = _vender(client, token_admin, producto["id"], cantidad=5)
    _vender(client, token_admin, producto_sin_costo["id"], cantidad=1)
    dia = factura_a["fecha"][:10]

    balance = client.get(
        f"/api/balance?desde={dia}&hasta={dia}", headers=auth(token_admin)
    )
    assert balance.status_code == 200, balance.text
    datos = balance.json()

    # Caja: 100.000 inicial - 60.000 de la compra de contado.
    assert datos["caja"]["efectivo"] == 40000
    assert datos["caja"]["banco"] == 100000
    assert datos["caja"]["abierta"] is True
    assert datos["caja"]["turno_id"] == turno_id

    # Inventario: 15 * 7.000 + 4 * 8.000 (respaldo a precio de venta).
    assert datos["activos"]["inventario"] == 137000
    assert datos["productos_sin_costo"] == 1
    assert datos["valor_inventario_precio_venta"] == 32000
    assert datos["activos"]["cartera"] == 58000
    assert datos["activos"]["total"] == 335000
    assert datos["pasivos"]["cuentas_por_pagar"] == 80000
    assert datos["patrimonio"]["total"] == 255000
    assert datos["compras_credito_pendientes"] == 1
    assert [c["ingreso_id"] for c in datos["cuentas_por_pagar"]] == [credito["id"]]
    assert datos["cuentas_por_pagar"][0]["proveedor"] == "Proveedor crédito"

    item_a = next(
        i for i in datos["inventario"] if i["producto_id"] == producto["id"]
    )
    assert item_a["stock"] == 15
    assert item_a["costo_unitario"] == 7000
    assert item_a["valor"] == 105000
    assert item_a["origen"] == "Costo promedio"

    item_b = next(
        i
        for i in datos["inventario"]
        if i["producto_id"] == producto_sin_costo["id"]
    )
    assert item_b["stock"] == 4
    assert item_b["costo_unitario"] == 8000
    assert item_b["origen"] == "Precio de venta"

    # Resultados: 58.000 vendidos; costo 5*7.000 + 1*8.000 = 43.000.
    assert datos["resultados"]["ventas_netas"] == 58000
    assert datos["resultados"]["costo_ventas"] == 43000
    assert datos["resultados"]["utilidad_bruta"] == 15000
    assert datos["resultados"]["gastos"] == 0
    assert datos["resultados"]["utilidad"] == 15000
    assert datos["resultados"]["facturas"] == 2
    assert datos["resultados"]["productos_vendidos_sin_costo"] == 1


def test_pagar_compra_credito_descuenta_caja_y_quita_pasivo(client, token_admin):
    turno_id = _abrir_caja(client, token_admin, efectivo=0, banco=100000)
    producto = _crear_producto(client, token_admin, "BAL3", "Producto", 10000)
    credito = _ingreso(
        client,
        token_admin,
        "Crédito",
        80000,
        [
            {
                "tipo": "Producto",
                "producto_id": producto["id"],
                "cantidad": 10,
                "costo_unitario": 8000,
            }
        ],
        proveedor="Proveedor crédito",
    )

    pago = client.post(
        f"/api/ingresos/{credito['id']}/pagar",
        headers=auth(token_admin),
        json={"forma_pago": "Transferencia"},
    )
    assert pago.status_code == 200, pago.text
    actualizado = pago.json()
    assert actualizado["pagado"] is True
    assert actualizado["estado_pago"] == "Pagado"
    assert actualizado["forma_pago_pago"] == "Transferencia"
    assert actualizado["pagado_por_id"] is not None

    movimientos = client.get(
        f"/api/caja/{turno_id}/movimientos", headers=auth(token_admin)
    ).json()
    salidas = [m for m in movimientos if m["tipo"] == "Salida"]
    assert len(salidas) == 1
    assert salidas[0]["referencia"] == f"Pago ingreso #{credito['id']}"
    assert salidas[0]["monto"] == 80000
    assert salidas[0]["forma_pago"] == "Transferencia"

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["caja"]["banco"] == 20000
    assert balance["pasivos"]["cuentas_por_pagar"] == 0
    assert balance["compras_credito_pendientes"] == 0
    # El pago no es un gasto: la utilidad no cambia por pagar una deuda.
    assert balance["resultados"]["gastos"] == 0
    assert balance["resultados"]["utilidad"] == 0

    # No se puede pagar dos veces.
    repetido = client.post(
        f"/api/ingresos/{credito['id']}/pagar",
        headers=auth(token_admin),
        json={"forma_pago": "Efectivo"},
    )
    assert repetido.status_code == 400
    assert "pagado" in repetido.json()["detail"].lower()

    # Tampoco se puede editar después de pagado.
    editar = client.put(
        f"/api/ingresos/{credito['id']}",
        headers=auth(token_admin),
        json={"proveedor": "Otro proveedor"},
    )
    assert editar.status_code == 400
    assert "pagado" in editar.json()["detail"].lower()


def test_pago_rechaza_no_credito_y_forma_invalida(client, token_admin):
    _abrir_caja(client, token_admin)
    producto = _crear_producto(client, token_admin, "BAL4", "Producto", 10000)
    contado = _ingreso(
        client,
        token_admin,
        "Efectivo",
        10000,
        [
            {
                "tipo": "Producto",
                "producto_id": producto["id"],
                "cantidad": 1,
                "costo_unitario": 10000,
            }
        ],
    )
    resp = client.post(
        f"/api/ingresos/{contado['id']}/pagar",
        headers=auth(token_admin),
        json={"forma_pago": "Efectivo"},
    )
    assert resp.status_code == 400
    assert "crédito" in resp.json()["detail"].lower()

    credito = _ingreso(
        client,
        token_admin,
        "Crédito",
        10000,
        [
            {
                "tipo": "Producto",
                "producto_id": producto["id"],
                "cantidad": 1,
                "costo_unitario": 10000,
            }
        ],
    )
    resp = client.post(
        f"/api/ingresos/{credito['id']}/pagar",
        headers=auth(token_admin),
        json={"forma_pago": "Tarjeta"},
    )
    assert resp.status_code == 400
    assert "efectivo o transferencia" in resp.json()["detail"].lower()


def test_pago_exige_caja_abierta(client, token_admin):
    turno_id = _abrir_caja(client, token_admin, efectivo=0, banco=50000)
    producto = _crear_producto(client, token_admin, "BAL5", "Producto", 10000)
    credito = _ingreso(
        client,
        token_admin,
        "Crédito",
        20000,
        [
            {
                "tipo": "Producto",
                "producto_id": producto["id"],
                "cantidad": 2,
                "costo_unitario": 10000,
            }
        ],
    )
    _cerrar_caja(client, token_admin, turno_id, 0, 50000)

    resp = client.post(
        f"/api/ingresos/{credito['id']}/pagar",
        headers=auth(token_admin),
        json={"forma_pago": "Efectivo"},
    )
    assert resp.status_code == 400
    assert "caja" in resp.json()["detail"].lower()

    # Sin caja abierta, el balance usa el saldo real del último cierre.
    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["caja"]["abierta"] is False
    assert balance["caja"]["efectivo"] == 0
    assert balance["caja"]["banco"] == 50000
    assert "Último cierre" in balance["caja"]["origen"]


def test_balance_exige_permiso_y_pago_lo_puede_hacer_cajero(
    client, token_admin, token_cajero, token_mesero
):
    # El cajero no tiene balance.ver por defecto.
    assert (
        client.get("/api/balance", headers=auth(token_cajero)).status_code == 403
    )
    assert (
        client.get(
            "/api/balance/exportar?formato=excel", headers=auth(token_cajero)
        ).status_code
        == 403
    )

    # El cajero sí puede pagar una compra a crédito (permiso ingresos.pagar).
    _abrir_caja(client, token_admin, efectivo=0, banco=50000)
    producto = _crear_producto(client, token_admin, "BAL6", "Producto", 10000)
    credito = _ingreso(
        client,
        token_admin,
        "Crédito",
        10000,
        [
            {
                "tipo": "Producto",
                "producto_id": producto["id"],
                "cantidad": 1,
                "costo_unitario": 10000,
            }
        ],
    )
    pago = client.post(
        f"/api/ingresos/{credito['id']}/pagar",
        headers=auth(token_cajero),
        json={"forma_pago": "Efectivo"},
    )
    assert pago.status_code == 200, pago.text
    assert pago.json()["pagado"] is True

    # El mesero no tiene ingresos.pagar.
    assert (
        client.post(
            "/api/ingresos/1/pagar",
            headers=auth(token_mesero),
            json={"forma_pago": "Efectivo"},
        ).status_code
        == 403
    )


def test_balance_no_cuenta_devoluciones_ni_pagos_como_gastos(
    client, token_admin
):
    turno_id = _abrir_caja(client, token_admin, efectivo=100000)
    producto = _crear_producto(
        client, token_admin, "BAL7", "Producto devolución", 10000, stock=1
    )

    factura = _vender(client, token_admin, producto["id"], cantidad=1)
    pago = client.post(
        f"/api/facturas/{factura['id']}/pagos",
        headers=auth(token_admin),
        json={"valor": 10000, "forma_pago": "Efectivo"},
    )
    assert pago.status_code == 200, pago.text

    anular = client.post(
        f"/api/facturas/{factura['id']}/anular",
        headers=auth(token_admin),
        json={"motivo": "Prueba de balance"},
    )
    assert anular.status_code == 200, anular.text

    # Gasto manual de caja: sí es un gasto.
    gasto = client.post(
        "/api/caja/movimientos",
        headers=auth(token_admin),
        json={
            "tipo": "Salida",
            "referencia": "Papelería",
            "forma_pago": "Efectivo",
            "monto": 3000,
        },
    )
    assert gasto.status_code == 200, gasto.text
    assert gasto.json()["turno_caja_id"] == turno_id

    # Compra a crédito de un ítem "Otros": es gasto del período y cuenta por
    # pagar, pero todavía no mueve la caja.
    credito = _ingreso(
        client,
        token_admin,
        "Crédito",
        4000,
        [{"tipo": "Otros", "concepto": "Flete", "valor": 4000}],
        proveedor="Transportes",
    )
    assert credito["pagado"] is False

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["caja"]["efectivo"] == 97000
    # La anulación devolvió la unidad al inventario; sin costo de compra se
    # valoriza a precio de venta.
    assert balance["activos"]["inventario"] == 10000
    assert balance["activos"]["cartera"] == 0
    assert balance["pasivos"]["cuentas_por_pagar"] == 4000
    assert balance["resultados"]["ventas_netas"] == 0
    assert balance["resultados"]["costo_ventas"] == 0
    assert balance["resultados"]["gastos_caja"] == 3000
    assert balance["resultados"]["gastos_otros"] == 4000
    assert balance["resultados"]["gastos"] == 7000
    assert balance["resultados"]["utilidad"] == -7000

    # Pagar la deuda mueve la caja, pero no vuelve a ser un gasto.
    pago_credito = client.post(
        f"/api/ingresos/{credito['id']}/pagar",
        headers=auth(token_admin),
        json={"forma_pago": "Efectivo"},
    )
    assert pago_credito.status_code == 200, pago_credito.text

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["caja"]["efectivo"] == 93000
    assert balance["activos"]["total"] == 103000
    assert balance["pasivos"]["cuentas_por_pagar"] == 0
    assert balance["patrimonio"]["total"] == 103000
    assert balance["resultados"]["gastos_caja"] == 3000
    assert balance["resultados"]["gastos_otros"] == 4000
    assert balance["resultados"]["gastos"] == 7000
    assert balance["resultados"]["utilidad"] == -7000


def test_balance_exporta_excel_y_pdf(client, token_admin):
    resp = client.get(
        "/api/balance/exportar?formato=excel", headers=auth(token_admin)
    )
    assert resp.status_code == 200, resp.text
    assert "spreadsheet" in resp.headers["content-type"]
    assert len(resp.content) > 1000

    resp = client.get(
        "/api/balance/exportar?formato=pdf", headers=auth(token_admin)
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")

    resp = client.get(
        "/api/balance/exportar?formato=csv", headers=auth(token_admin)
    )
    assert resp.status_code == 400
    assert "formato" in resp.json()["detail"].lower()
