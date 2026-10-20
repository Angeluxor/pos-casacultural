"""Pruebas del módulo de costos, recetas y costos manuales."""
from .conftest import auth


def _crear_producto(
    client,
    token,
    codigo="P200",
    nombre="Producto",
    precio=10000,
    stock=0,
    misma_unidad=True,
):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={
            "codigo": codigo,
            "nombre": nombre,
            "precio": precio,
            "stock_inicial": stock,
            "misma_unidad_compra_venta": misma_unidad,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _ingreso(client, token, producto_id, cantidad, costo, proveedor="Proveedor"):
    resp = client.post(
        "/api/ingresos/",
        headers=auth(token),
        json={
            "proveedor": proveedor,
            "fuente_pago": "Balance general",
            "forma_pago": "Efectivo",
            "total": cantidad * costo,
            "items": [
                {
                    "tipo": "Producto",
                    "producto_id": producto_id,
                    "cantidad": cantidad,
                    "costo_unitario": costo,
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fila(resumen, producto_id):
    return next(f for f in resumen if f["producto_id"] == producto_id)


def test_costos_exige_permiso_y_cajero_no_entra_por_defecto(client, token_admin, token_cajero):
    assert client.get("/api/costos/resumen", headers=auth(token_cajero)).status_code == 403
    assert client.get("/api/costos/resumen", headers=auth(token_admin)).status_code == 200


def test_resumen_calcula_mejor_precio_variacion_y_cmv(client, token_admin):
    producto = _crear_producto(client, token_admin, codigo="CAF", nombre="Café", precio=10000)
    _ingreso(client, token_admin, producto["id"], 10, 4000, proveedor="Barato")
    _ingreso(client, token_admin, producto["id"], 10, 6000, proveedor="Caro")

    resumen = client.get("/api/costos/resumen", headers=auth(token_admin)).json()
    fila = _fila(resumen, producto["id"])

    assert fila["mejor_precio_6s"] == 4000
    assert fila["mejor_proveedor"] == "Barato"
    assert fila["mejor_origen"] == "Compra"
    assert fila["costo_vigente"] == 5000  # promedio ponderado
    assert fila["origen_costo"] == "Costo promedio"
    assert fila["variacion_6s"] == 50.0  # de 4000 a 6000
    assert fila["puntos_6s"] == 2
    assert fila["mostrar_cmv"] is True
    assert fila["cmv_pct"] == 50.0
    assert fila["margen"] == 5000
    assert fila["margen_pct"] == 50.0


def test_resumen_oculta_cmv_si_no_es_1a1(client, token_admin):
    producto = _crear_producto(
        client,
        token_admin,
        codigo="CAJA",
        nombre="Caja de cervezas",
        precio=10000,
        misma_unidad=False,
    )
    _ingreso(client, token_admin, producto["id"], 10, 4000)

    fila = _fila(
        client.get("/api/costos/resumen", headers=auth(token_admin)).json(),
        producto["id"],
    )
    assert fila["misma_unidad_compra_venta"] is False
    assert fila["mostrar_cmv"] is False
    assert fila["cmv_pct"] is None
    assert fila["costo_vigente"] == 4000


def test_costo_manual_reemplaza_promedio_y_aparece_en_historial(client, token_admin):
    producto = _crear_producto(client, token_admin, codigo="AZU", nombre="Azúcar", precio=8000)

    resp = client.post(
        "/api/costos/manuales",
        headers=auth(token_admin),
        json={"producto_id": producto["id"], "costo_unitario": 3000, "nota": "Estimado"},
    )
    assert resp.status_code == 200, resp.text
    manual = resp.json()
    assert manual["producto_nombre"] == "Azúcar"
    assert manual["costo_unitario"] == 3000

    fila = _fila(
        client.get("/api/costos/resumen", headers=auth(token_admin)).json(),
        producto["id"],
    )
    assert fila["costo_vigente"] == 3000
    assert fila["origen_costo"] == "Costo manual"
    # Sin compras en la ventana, el mejor precio cae al registro manual.
    assert fila["mejor_precio_6s"] == 3000
    assert fila["mejor_origen"] == "Manual"

    historial = client.get(
        f"/api/costos/productos/{producto['id']}/historial",
        headers=auth(token_admin),
    ).json()
    assert len(historial) == 1
    assert historial[0]["origen"] == "Manual"
    assert historial[0]["nota"] == "Estimado"


def test_receta_calcula_costo_y_alimenta_el_balance(client, token_admin):
    harina = _crear_producto(client, token_admin, codigo="HAR", nombre="Harina", precio=1000)
    queso = _crear_producto(client, token_admin, codigo="QUE", nombre="Queso", precio=2000)
    _ingreso(client, token_admin, harina["id"], 10, 1000)
    _ingreso(client, token_admin, queso["id"], 10, 2000)

    preparacion = _crear_producto(
        client, token_admin, codigo="ARE", nombre="Arepa", precio=6000, stock=4
    )

    resp = client.put(
        f"/api/costos/recetas/{preparacion['id']}",
        headers=auth(token_admin),
        json={
            "rendimiento": 2,
            "items": [
                {"producto_id": harina["id"], "cantidad": 2},
                {"producto_id": queso["id"], "cantidad": 1},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    receta = resp.json()
    assert receta["completo"] is True
    assert receta["costo_total"] == 4000  # 2*1000 + 1*2000
    assert receta["costo_unitario"] == 2000  # /2 rendimiento
    assert receta["cmv_pct"] == round(2000 / 6000 * 100, 2)
    assert len(receta["items"]) == 2

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    fila = next(
        i for i in balance["inventario"] if i["producto_id"] == preparacion["id"]
    )
    assert fila["origen"] == "Receta"
    assert fila["costo_unitario"] == 2000
    assert fila["valor"] == 8000  # 4 unidades * 2000


def test_receta_incompleta_marca_faltantes_y_no_cotiza(client, token_admin):
    insumo = _crear_producto(client, token_admin, codigo="SIN", nombre="Sin costo", precio=100)
    preparacion = _crear_producto(client, token_admin, codigo="PRE", nombre="Preparado", precio=5000)

    resp = client.put(
        f"/api/costos/recetas/{preparacion['id']}",
        headers=auth(token_admin),
        json={"rendimiento": 1, "items": [{"producto_id": insumo["id"], "cantidad": 1}]},
    )
    assert resp.status_code == 200, resp.text
    receta = resp.json()
    assert receta["completo"] is False
    assert receta["costo_unitario"] is None
    assert "Sin costo" in receta["faltantes"]

    fila = _fila(
        client.get("/api/costos/resumen", headers=auth(token_admin)).json(),
        preparacion["id"],
    )
    assert fila["tiene_receta"] is True
    assert fila["costo_completo"] is False
    assert fila["costo_vigente"] is None
    assert "Sin costo" in fila["faltantes"]


def test_receta_rechaza_ciclo_autoinsumo_y_duplicados(client, token_admin):
    a = _crear_producto(client, token_admin, codigo="A", nombre="A")
    b = _crear_producto(client, token_admin, codigo="B", nombre="B")

    resp = client.put(
        f"/api/costos/recetas/{b['id']}",
        headers=auth(token_admin),
        json={"rendimiento": 1, "items": [{"producto_id": a["id"], "cantidad": 1}]},
    )
    assert resp.status_code == 200, resp.text

    # A no puede depender de B porque B ya depende de A.
    resp = client.put(
        f"/api/costos/recetas/{a['id']}",
        headers=auth(token_admin),
        json={"rendimiento": 1, "items": [{"producto_id": b["id"], "cantidad": 1}]},
    )
    assert resp.status_code == 400
    assert "ciclo" in resp.json()["detail"].lower()

    # Autoinsumo.
    resp = client.put(
        f"/api/costos/recetas/{a['id']}",
        headers=auth(token_admin),
        json={"rendimiento": 1, "items": [{"producto_id": a["id"], "cantidad": 1}]},
    )
    assert resp.status_code == 400

    # Duplicados.
    resp = client.put(
        f"/api/costos/recetas/{a['id']}",
        headers=auth(token_admin),
        json={
            "rendimiento": 1,
            "items": [
                {"producto_id": b["id"], "cantidad": 1},
                {"producto_id": b["id"], "cantidad": 2},
            ],
        },
    )
    assert resp.status_code == 400


def test_costo_manual_rechaza_producto_con_receta(client, token_admin):
    insumo = _crear_producto(client, token_admin, codigo="I", nombre="Insumo")
    prep = _crear_producto(client, token_admin, codigo="PR", nombre="Preparación")
    client.put(
        f"/api/costos/recetas/{prep['id']}",
        headers=auth(token_admin),
        json={"rendimiento": 1, "items": [{"producto_id": insumo["id"], "cantidad": 1}]},
    )

    resp = client.post(
        "/api/costos/manuales",
        headers=auth(token_admin),
        json={"producto_id": prep["id"], "costo_unitario": 1000},
    )
    assert resp.status_code == 400
    assert "receta" in resp.json()["detail"].lower()


def test_recetas_anidadas_y_eliminar(client, token_admin):
    insumo = _crear_producto(client, token_admin, codigo="N1", nombre="Base", precio=1000)
    _ingreso(client, token_admin, insumo["id"], 10, 1000)
    sub = _crear_producto(client, token_admin, codigo="N2", nombre="Salsa", precio=3000)
    final = _crear_producto(client, token_admin, codigo="N3", nombre="Plato", precio=9000)

    client.put(
        f"/api/costos/recetas/{sub['id']}",
        headers=auth(token_admin),
        json={"rendimiento": 2, "items": [{"producto_id": insumo["id"], "cantidad": 4}]},
    )
    resp = client.put(
        f"/api/costos/recetas/{final['id']}",
        headers=auth(token_admin),
        json={"rendimiento": 1, "items": [{"producto_id": sub["id"], "cantidad": 1}]},
    )
    assert resp.status_code == 200, resp.text
    # Salsa: 4*1000 / 2 = 2000. Plato: 1*2000 / 1 = 2000.
    assert resp.json()["costo_unitario"] == 2000

    recetas = client.get("/api/costos/recetas", headers=auth(token_admin)).json()
    assert len(recetas) == 2

    resp = client.delete(
        f"/api/costos/recetas/{final['id']}", headers=auth(token_admin)
    )
    assert resp.status_code == 204
    assert len(
        client.get("/api/costos/recetas", headers=auth(token_admin)).json()
    ) == 1


def test_actualizar_receta_reemplaza_insumos(client, token_admin):
    a = _crear_producto(client, token_admin, codigo="U1", nombre="Insumo A", precio=1000)
    b = _crear_producto(client, token_admin, codigo="U2", nombre="Insumo B", precio=2000)
    _ingreso(client, token_admin, a["id"], 10, 1000)
    _ingreso(client, token_admin, b["id"], 10, 2000)
    prep = _crear_producto(client, token_admin, codigo="UP", nombre="Preparado", precio=5000)

    resp = client.put(
        f"/api/costos/recetas/{prep['id']}",
        headers=auth(token_admin),
        json={"rendimiento": 1, "items": [{"producto_id": a["id"], "cantidad": 1}]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["costo_unitario"] == 1000

    # Cambiar el insumo no debe chocar con la restricción única anterior.
    resp = client.put(
        f"/api/costos/recetas/{prep['id']}",
        headers=auth(token_admin),
        json={"rendimiento": 2, "items": [{"producto_id": b["id"], "cantidad": 3}]},
    )
    assert resp.status_code == 200, resp.text
    receta = resp.json()
    assert receta["rendimiento"] == 2
    assert len(receta["items"]) == 1
    assert receta["items"][0]["producto_id"] == b["id"]
    assert receta["costo_unitario"] == 3000  # 3*2000 / 2


def test_insumos_devuelven_costo_y_receta(client, token_admin):
    insumo = _crear_producto(client, token_admin, codigo="INS", nombre="Insumo", precio=1000)
    _ingreso(client, token_admin, insumo["id"], 10, 1500)
    prep = _crear_producto(client, token_admin, codigo="PRP", nombre="Preparado", precio=5000)
    client.put(
        f"/api/costos/recetas/{prep['id']}",
        headers=auth(token_admin),
        json={"rendimiento": 1, "items": [{"producto_id": insumo["id"], "cantidad": 1}]},
    )

    insumos = client.get("/api/costos/insumos", headers=auth(token_admin)).json()
    por_id = {i["producto_id"]: i for i in insumos}
    assert por_id[insumo["id"]]["costo"] == 1500
    assert por_id[insumo["id"]]["tiene_receta"] is False
    assert por_id[prep["id"]]["costo"] == 1500
    assert por_id[prep["id"]]["tiene_receta"] is True
