"""Idempotencia de la creación de ventas.

El POS puede perder la respuesta de una venta (timeout, red móvil, cold start)
aunque el servidor ya la haya guardado. El navegador reintenta con la misma
cabecera ``Idempotency-Key`` y el backend debe devolver la factura original,
sin duplicar la venta ni descontar stock dos veces.
"""
from app.db.models import Factura, Kardex, TipoMovimientoInventario
from app.db.session import SessionLocal

from .conftest import auth


def _crear_producto(client, token, codigo="IDEM1", nombre="Producto idempotente", precio=5000, stock=10):
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


def _vender(
    client,
    token,
    producto_id,
    cantidad=2,
    clave="venta-idempotente-1",
    nombre_eventual="Cliente de prueba",
):
    headers = auth(token)
    if clave is not None:
        headers["Idempotency-Key"] = clave
    return client.post(
        "/api/facturas/",
        headers=headers,
        json={
            "nombre_eventual": nombre_eventual,
            "detalles": [{"producto_id": producto_id, "cantidad": cantidad}],
        },
    )


def _conteos():
    db = SessionLocal()
    try:
        salidas = (
            db.query(Kardex)
            .filter(
                Kardex.tipo_movimiento
                == TipoMovimientoInventario.SALIDA_VENTA
            )
            .count()
        )
        return db.query(Factura).count(), salidas
    finally:
        db.close()


def test_reintento_con_la_misma_clave_no_duplica_la_venta(client, token_cajero):
    producto = _crear_producto(client, token_cajero, stock=10)

    primera = _vender(client, token_cajero, producto["id"], cantidad=2)
    segunda = _vender(client, token_cajero, producto["id"], cantidad=2)

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert primera.json()["id"] == segunda.json()["id"]
    assert segunda.json()["total"] == 10000

    # El stock y el kardex se movieron una sola vez.
    actualizado = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_cajero)
    ).json()
    assert actualizado["stock"] == 8

    facturas, kardex = _conteos()
    assert facturas == 1
    assert kardex == 1


def test_la_clave_devuelve_la_venta_original_aunque_cambie_el_cuerpo(client, token_cajero):
    producto = _crear_producto(client, token_cajero, stock=10)

    primera = _vender(client, token_cajero, producto["id"], cantidad=2)
    segunda = _vender(
        client,
        token_cajero,
        producto["id"],
        cantidad=5,
        nombre_eventual="Otro nombre",
    )

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["id"] == primera.json()["id"]
    assert segunda.json()["nombre_eventual"] == "Cliente de prueba"
    assert segunda.json()["total"] == 10000

    actualizado = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_cajero)
    ).json()
    assert actualizado["stock"] == 8


def test_la_clave_no_se_puede_reutilizar_desde_otro_usuario(
    client, token_cajero, token_admin
):
    producto = _crear_producto(client, token_cajero, stock=10)

    primera = _vender(client, token_cajero, producto["id"])
    ajena = _vender(client, token_admin, producto["id"])

    assert primera.status_code == 200, primera.text
    assert ajena.status_code == 409, ajena.text
    assert "otro usuario" in ajena.json()["detail"].lower()

    actualizado = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_cajero)
    ).json()
    assert actualizado["stock"] == 8


def test_sin_clave_se_mantiene_el_comportamiento_anterior(client, token_cajero):
    producto = _crear_producto(client, token_cajero, stock=10)

    primera = _vender(client, token_cajero, producto["id"], clave=None)
    segunda = _vender(client, token_cajero, producto["id"], clave=None)

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert primera.json()["id"] != segunda.json()["id"]

    actualizado = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_cajero)
    ).json()
    assert actualizado["stock"] == 6


def test_clave_demasiado_larga_se_rechaza(client, token_cajero):
    producto = _crear_producto(client, token_cajero)

    respuesta = _vender(client, token_cajero, producto["id"], clave="x" * 65)

    assert respuesta.status_code == 400, respuesta.text
    assert "64" in respuesta.json()["detail"]
    actualizado = client.get(
        f"/api/productos/{producto['id']}", headers=auth(token_cajero)
    ).json()
    assert actualizado["stock"] == 10
