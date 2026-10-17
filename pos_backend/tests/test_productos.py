"""Pruebas del flujo básico de productos y kardex."""
from .conftest import auth


def test_crear_y_listar_producto(client, token_admin):
    resp = client.post(
        "/api/productos/",
        headers=auth(token_admin),
        json={"codigo": "P001", "nombre": "Café", "precio": 5000, "stock_inicial": 10},
    )
    assert resp.status_code == 200, resp.text
    producto = resp.json()
    assert producto["codigo"] == "P001"
    assert producto["stock"] == 10

    listado = client.get("/api/productos/", headers=auth(token_admin))
    assert listado.status_code == 200
    cuerpo = listado.json()
    assert cuerpo["total"] == 1
    assert cuerpo["items"][0]["codigo"] == "P001"


def test_no_permite_codigo_duplicado(client, token_admin):
    datos = {"codigo": "P001", "nombre": "Café", "precio": 5000, "stock_inicial": 0}
    assert client.post("/api/productos/", headers=auth(token_admin), json=datos).status_code == 200
    assert client.post("/api/productos/", headers=auth(token_admin), json=datos).status_code == 400


def test_productos_requieren_autenticacion(client):
    assert client.get("/api/productos/").status_code == 401


def test_cajero_puede_crear_producto(client, token_cajero):
    resp = client.post(
        "/api/productos/",
        headers=auth(token_cajero),
        json={"codigo": "P002", "nombre": "Té", "precio": 3000, "stock_inicial": 5},
    )
    assert resp.status_code == 200
    assert resp.json()["stock"] == 5


def test_movimiento_kardex_actualiza_stock(client, token_admin):
    creado = client.post(
        "/api/productos/",
        headers=auth(token_admin),
        json={"codigo": "P003", "nombre": "Azúcar", "precio": 4000, "stock_inicial": 10},
    ).json()

    resp = client.post(
        f"/api/productos/{creado['id']}/kardex",
        headers=auth(token_admin),
        json={
            "tipo_movimiento": "Ajuste",
            "cantidad": 15,
            "referencia": "Corrección de conteo",
            "motivo": "Mal conteo",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["saldo_stock"] == 25

    detalle = client.get(f"/api/productos/{creado['id']}", headers=auth(token_admin)).json()
    assert detalle["stock"] == 25
