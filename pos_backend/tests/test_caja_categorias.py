"""Pruebas de las categorías de los movimientos de caja."""
from .conftest import auth


def _abrir_caja(client, token, efectivo=100000):
    resp = client.post(
        "/api/caja/abrir",
        headers=auth(token),
        json={"saldo_inicial_efectivo": efectivo, "saldo_inicial_banco": 0},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _movimiento(client, token, **datos):
    cuerpo = {
        "tipo": "Entrada",
        "referencia": "Prueba",
        "forma_pago": "Efectivo",
        "monto": 1000,
    }
    cuerpo.update(datos)
    return client.post(
        "/api/caja/movimientos", headers=auth(token), json=cuerpo
    )


def test_categorias_manuales_validan_filtran_y_por_defecto(client, token_admin):
    turno_id = _abrir_caja(client, token_admin)

    aporte = _movimiento(
        client,
        token_admin,
        tipo="Entrada",
        categoria="Aporte cultural",
        referencia="Aporte cultural – Evento de octubre",
        monto=20000,
    )
    assert aporte.status_code == 200, aporte.text
    assert aporte.json()["categoria"] == "Aporte cultural"

    sin_categoria = _movimiento(
        client, token_admin, tipo="Entrada", referencia="Ingreso varios"
    )
    assert sin_categoria.status_code == 200, sin_categoria.text
    assert sin_categoria.json()["categoria"] == "Otro ingreso"

    arriendo = _movimiento(
        client,
        token_admin,
        tipo="Salida",
        categoria="Arriendo",
        referencia="Arriendo de octubre",
        monto=15000,
    )
    assert arriendo.status_code == 200, arriendo.text
    assert arriendo.json()["categoria"] == "Arriendo"

    # Una categoría de entrada no sirve para una salida.
    invalida = _movimiento(
        client,
        token_admin,
        tipo="Salida",
        categoria="Aporte cultural",
        referencia="Categoría equivocada",
    )
    assert invalida.status_code == 400
    assert "categoría inválida" in invalida.json()["detail"].lower()

    # Los tipos automáticos no se registran a mano.
    apertura = _movimiento(
        client, token_admin, tipo="Apertura", referencia="Apertura manual"
    )
    assert apertura.status_code == 400
    assert "entradas y salidas" in apertura.json()["detail"].lower()

    movimientos = client.get(
        f"/api/caja/{turno_id}/movimientos", headers=auth(token_admin)
    ).json()
    categorias = {m["categoria"] for m in movimientos}
    assert {"Apertura", "Aporte cultural", "Otro ingreso", "Arriendo"} <= categorias

    filtrados = client.get(
        f"/api/caja/{turno_id}/movimientos?categoria=Aporte cultural",
        headers=auth(token_admin),
    ).json()
    assert len(filtrados) == 1
    assert filtrados[0]["referencia"] == "Aporte cultural – Evento de octubre"

    # El aporte cultural es dinero que entra, pero no es una venta ni utilidad.
    dashboard = client.get("/api/dashboard/", headers=auth(token_admin)).json()
    assert dashboard["kpis"]["ventas_hoy_total"] == 0
    assert dashboard["kpis"]["ventas_mes_total"] == 0
    assert all(m["total"] == 0 for m in dashboard["ventas_ultimos_12_meses"])

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["resultados"]["ventas_netas"] == 0
    assert balance["resultados"]["gastos_caja"] == 15000  # solo el arriendo
    assert balance["resultados"]["utilidad"] == -15000
    assert balance["activos"]["efectivo"] == 106000  # 100k + 20k + 1k - 15k
    assert balance["patrimonio"]["total"] == 106000


def test_movimientos_automaticos_quedan_categorizados(client, token_admin):
    turno_id = _abrir_caja(client, token_admin)

    producto = client.post(
        "/api/productos/",
        headers=auth(token_admin),
        json={
            "codigo": "CAT1",
            "nombre": "Producto categoría",
            "precio": 10000,
            "stock_inicial": 1,
        },
    )
    assert producto.status_code == 200, producto.text
    producto = producto.json()

    factura = client.post(
        "/api/facturas/",
        headers=auth(token_admin),
        json={"detalles": [{"producto_id": producto["id"], "cantidad": 1}]},
    )
    assert factura.status_code == 200, factura.text
    factura = factura.json()
    pago = client.post(
        f"/api/facturas/{factura['id']}/pagos",
        headers=auth(token_admin),
        json={"valor": factura["total"], "forma_pago": "Efectivo"},
    )
    assert pago.status_code == 200, pago.text

    ingreso = client.post(
        "/api/ingresos/",
        headers=auth(token_admin),
        json={
            "proveedor": "Proveedor categoría",
            "forma_pago": "Efectivo",
            "total": 6000,
            "items": [
                {
                    "tipo": "Producto",
                    "producto_id": producto["id"],
                    "cantidad": 1,
                    "costo_unitario": 6000,
                }
            ],
        },
    )
    assert ingreso.status_code == 200, ingreso.text

    movimientos = client.get(
        f"/api/caja/{turno_id}/movimientos", headers=auth(token_admin)
    ).json()
    por_referencia = {m["referencia"]: m["categoria"] for m in movimientos}
    assert por_referencia[f"Abono a Factura #{factura['id']}"] == "Ventas"
    assert por_referencia[f"Ingreso #{ingreso.json()['id']}"] == "Compra de inventario"
    assert por_referencia["Apertura de caja"] == "Apertura"
