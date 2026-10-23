"""Pruebas del módulo de ingresos de inventario."""
import pytest

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
    # El detalle debe mostrar el nombre del producto, no «Producto #id».
    assert ingreso["items"][0]["producto_nombre"] == "Harina"
    assert ingreso["items"][0]["concepto"] is None

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


def _crear_ingreso_efectivo(client, token, producto, total=50000, cantidad=10, costo=5000):
    resp = client.post(
        "/api/ingresos/",
        headers=auth(token),
        json={
            "proveedor": "Distribuidora La Fría",
            "forma_pago": "Efectivo",
            "total": total,
            "items": [
                {
                    "tipo": "Producto",
                    "producto_id": producto["id"],
                    "cantidad": cantidad,
                    "costo_unitario": costo,
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_editar_forma_pago_actualiza_la_salida_de_caja(client, token_admin):
    turno_id = _abrir_caja(client, token_admin, efectivo=100000)
    producto = _crear_producto(client, token_admin, codigo="EDIT-1")
    ingreso = _crear_ingreso_efectivo(client, token_admin, producto)

    resp = client.put(
        f"/api/ingresos/{ingreso['id']}",
        headers=auth(token_admin),
        json={"forma_pago": "Transferencia"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["forma_pago"] == "Transferencia"
    assert resp.json()["pagado"] is True
    assert resp.json()["forma_pago_pago"] == "Transferencia"

    movs = client.get(
        f"/api/caja/{turno_id}/movimientos", headers=auth(token_admin)
    ).json()
    salidas = [m for m in movs if m["tipo"] == "Salida"]
    assert len(salidas) == 1
    assert salidas[0]["forma_pago"] == "Transferencia"
    assert salidas[0]["monto"] == 50000


def test_editar_forma_pago_a_credito_quita_salida_y_deja_pendiente(
    client, token_admin
):
    turno_id = _abrir_caja(client, token_admin, efectivo=100000)
    producto = _crear_producto(client, token_admin, codigo="EDIT-2")
    ingreso = _crear_ingreso_efectivo(client, token_admin, producto)

    resp = client.put(
        f"/api/ingresos/{ingreso['id']}",
        headers=auth(token_admin),
        json={"forma_pago": "Crédito"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["forma_pago"] == "Crédito"
    assert data["pagado"] is False
    assert data["estado_pago"] == "Pendiente"

    movs = client.get(
        f"/api/caja/{turno_id}/movimientos", headers=auth(token_admin)
    ).json()
    assert [m for m in movs if m["tipo"] in ("Entrada", "Salida")] == []

    # Al quedar a crédito, se puede pagar después desde la caja abierta.
    pago = client.post(
        f"/api/ingresos/{ingreso['id']}/pagar",
        headers=auth(token_admin),
        json={"forma_pago": "Efectivo"},
    )
    assert pago.status_code == 200, pago.text
    assert pago.json()["pagado"] is True


def test_editar_fuente_pago_a_balance_quita_movimiento_de_caja(client, token_admin):
    turno_id = _abrir_caja(client, token_admin, efectivo=100000)
    producto = _crear_producto(client, token_admin, codigo="EDIT-3")
    ingreso = _crear_ingreso_efectivo(client, token_admin, producto)

    resp = client.put(
        f"/api/ingresos/{ingreso['id']}",
        headers=auth(token_admin),
        json={"fuente_pago": "Balance general"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["fuente_pago"] == "Balance general"
    assert resp.json()["turno_caja_id"] is None

    movs = client.get(
        f"/api/caja/{turno_id}/movimientos", headers=auth(token_admin)
    ).json()
    assert [m for m in movs if m["tipo"] in ("Entrada", "Salida")] == []


def test_editar_balance_a_caja_crea_el_movimiento(client, token_admin):
    producto = _crear_producto(client, token_admin, codigo="EDIT-4")
    creado = client.post(
        "/api/ingresos/",
        headers=auth(token_admin),
        json={
            "fuente_pago": "Balance general",
            "forma_pago": "Crédito",
            "total": 30000,
            "items": [
                {
                    "tipo": "Producto",
                    "producto_id": producto["id"],
                    "cantidad": 3,
                    "costo_unitario": 10000,
                }
            ],
        },
    )
    assert creado.status_code == 200, creado.text
    ingreso = creado.json()

    turno_id = _abrir_caja(client, token_admin, efectivo=100000)
    resp = client.put(
        f"/api/ingresos/{ingreso['id']}",
        headers=auth(token_admin),
        json={"fuente_pago": "Caja activa", "forma_pago": "Efectivo"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["fuente_pago"] == "Caja activa"
    assert data["turno_caja_id"] == turno_id
    assert data["pagado"] is True

    movs = client.get(
        f"/api/caja/{turno_id}/movimientos", headers=auth(token_admin)
    ).json()
    salidas = [m for m in movs if m["tipo"] == "Salida"]
    assert len(salidas) == 1
    assert salidas[0]["referencia"] == f"Ingreso #{ingreso['id']}"
    assert salidas[0]["monto"] == 30000


def test_anular_ingreso_revierte_stock_y_caja_y_no_cuenta_en_balance(
    client, token_admin
):
    _abrir_caja(client, token_admin, efectivo=100000)
    producto = _crear_producto(client, token_admin, codigo="ANUL-1")
    ingreso = _crear_ingreso_efectivo(client, token_admin, producto)

    resp = client.post(
        f"/api/ingresos/{ingreso['id']}/anular",
        headers=auth(token_admin),
        json={"motivo": "Se registró dos veces"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["anulada"] is True
    assert data["estado_pago"] == "No aplica"
    assert data["motivo_anulacion"] == "Se registró dos veces"
    assert data["anulada_por_nombre"]

    detalle = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_admin)
    ).json()
    assert detalle["stock"] == 0

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["caja"]["efectivo"] == 100000
    assert balance["activos"]["inventario"] == 0
    assert balance["resultados"]["gastos"] == 0

    repetido = client.post(
        f"/api/ingresos/{ingreso['id']}/anular",
        headers=auth(token_admin),
        json={"motivo": "otra vez"},
    )
    assert repetido.status_code == 400


def test_anular_credito_pendiente_no_exige_caja(client, token_admin):
    producto = _crear_producto(client, token_admin, codigo="ANUL-2")
    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_admin),
        json={
            "proveedor": "Proveedor crédito",
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

    anulado = client.post(
        f"/api/ingresos/{ingreso['id']}/anular",
        headers=auth(token_admin),
        json={"motivo": "Compra equivocada"},
    )
    assert anulado.status_code == 200, anulado.text
    assert anulado.json()["anulada"] is True

    detalle = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_admin)
    ).json()
    assert detalle["stock"] == 0
    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["pasivos"]["cuentas_por_pagar"] == 0


def test_anular_ingreso_requiere_permiso_de_anulacion(client, token_cajero):
    _abrir_caja(client, token_cajero, efectivo=100000)
    producto = _crear_producto(client, token_cajero, codigo="ANUL-3")
    ingreso = _crear_ingreso_efectivo(client, token_cajero, producto)

    resp = client.post(
        f"/api/ingresos/{ingreso['id']}/anular",
        headers=auth(token_cajero),
        json={"motivo": "error"},
    )
    assert resp.status_code == 403


def test_ingreso_por_caja_calcula_cantidad_y_costo_unitario(client, token_admin):
    turno_id = _abrir_caja(client, token_admin, efectivo=100000)
    producto = _crear_producto(client, token_admin, codigo="FORM-1", nombre="Jabón")

    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_admin),
        json={
            "forma_pago": "Efectivo",
            "total": 48,
            "items": [
                {
                    "tipo": "Producto",
                    "producto_id": producto["id"],
                    "cantidad": 24,
                    "cantidad_formatos": 2,
                    "unidades_por_formato": 12,
                    "costo_formato": 24,
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    ingreso = resp.json()
    item = ingreso["items"][0]
    assert item["cantidad"] == 24
    assert item["cantidad_formatos"] == 2
    assert item["unidades_por_formato"] == 12
    assert item["costo_formato"] == 24
    assert item["costo_unitario"] == 2
    assert item["valor"] == 48
    assert ingreso["estado"] == "Completo"
    assert ingreso["turno_caja_id"] == turno_id

    detalle = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_admin)
    ).json()
    assert detalle["stock"] == 24

    movs = client.get(
        f"/api/caja/{turno_id}/movimientos", headers=auth(token_admin)
    ).json()
    salidas = [m for m in movs if m["tipo"] == "Salida"]
    assert len(salidas) == 1
    assert salidas[0]["monto"] == 48


def test_producto_nuevo_por_caja_no_queda_como_misma_unidad(client, token_admin):
    _abrir_caja(client, token_admin, efectivo=100000)

    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_admin),
        json={
            "forma_pago": "Efectivo",
            "total": 45000,
            "items": [
                {
                    "tipo": "Producto nuevo",
                    "concepto": "Galletas",
                    "precio": 1000,
                    "cantidad_formatos": 3,
                    "unidades_por_formato": 10,
                    "costo_formato": 15000,
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["cantidad"] == 30
    assert item["costo_unitario"] == 1500
    assert item["valor"] == 45000

    producto = client.get(
        f"/api/productos/{item['producto_id']}", headers=auth(token_admin)
    ).json()
    assert producto["stock"] == 30
    assert producto["misma_unidad_compra_venta"] is False


def test_ingreso_por_caja_rechaza_formato_sin_unidades(client, token_admin):
    _abrir_caja(client, token_admin, efectivo=100000)
    producto = _crear_producto(client, token_admin, codigo="FORM-2")

    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_admin),
        json={
            "forma_pago": "Efectivo",
            "total": 10,
            "items": [
                {
                    "tipo": "Producto",
                    "producto_id": producto["id"],
                    "cantidad_formatos": 2,
                    "unidades_por_formato": 0,
                    "costo_formato": 10,
                }
            ],
        },
    )
    assert resp.status_code == 400
    assert "unidades" in resp.json()["detail"].lower()


def test_editar_costo_de_caja_recalcula_el_unitario(client, token_admin):
    _abrir_caja(client, token_admin, efectivo=100000)
    producto = _crear_producto(client, token_admin, codigo="FORM-3")

    creado = client.post(
        "/api/ingresos/",
        headers=auth(token_admin),
        json={
            "forma_pago": "Efectivo",
            "total": 48,
            "items": [
                {
                    "tipo": "Producto",
                    "producto_id": producto["id"],
                    "cantidad_formatos": 2,
                    "unidades_por_formato": 12,
                    "costo_formato": 24,
                }
            ],
        },
    )
    assert creado.status_code == 200, creado.text
    item = creado.json()["items"][0]

    resp = client.put(
        f"/api/ingresos/{creado.json()['id']}",
        headers=auth(token_admin),
        json={"items": [{"id": item["id"], "costo_formato": 36}]},
    )
    assert resp.status_code == 200, resp.text
    actualizado = resp.json()["items"][0]
    assert actualizado["costo_formato"] == 36
    assert actualizado["costo_unitario"] == 3
    assert actualizado["valor"] == 72


def test_costo_fraccionario_por_caja_no_desajusta_el_inventario(
    client, token_admin
):
    producto = _crear_producto(
        client, token_admin, codigo="FORM-DEC", nombre="Unidad suelta"
    )

    resp = client.post(
        "/api/ingresos/",
        headers=auth(token_admin),
        json={
            "fuente_pago": "Balance general",
            "forma_pago": "Efectivo",
            "total": 20,
            "items": [
                {
                    "tipo": "Producto",
                    "producto_id": producto["id"],
                    "cantidad_formatos": 2,
                    "unidades_por_formato": 12,
                    "costo_formato": 10,
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["cantidad"] == 24
    assert item["costo_unitario"] == pytest.approx(0.833333, abs=1e-6)
    assert item["valor"] == 20

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    fila = next(
        i for i in balance["inventario"] if i["producto_id"] == producto["id"]
    )
    assert fila["stock"] == 24
    assert fila["costo_unitario"] == pytest.approx(0.833333, abs=1e-6)
    assert fila["valor"] == 20

    costos = client.get("/api/costos/resumen", headers=auth(token_admin)).json()
    fila_costo = next(
        f for f in costos if f["producto_id"] == producto["id"]
    )
    assert fila_costo["costo_vigente"] == pytest.approx(0.833333, abs=1e-6)
