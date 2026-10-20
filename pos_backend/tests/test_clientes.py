"""Pruebas de eliminación de clientes.

La regla de negocio es conservar siempre el historial de ventas: un cliente
solo se puede borrar si no tiene facturas. El "Cliente eventual" es un registro
del sistema y nunca se elimina.
"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base_class import Base
from app.db.models import Cliente, Factura
from app.db.session import SessionLocal

from .conftest import auth

def _crear_cliente(client, token, nombre="Ana Pérez", **extra):
    resp = client.post(
        "/api/clientes/", headers=auth(token), json={"nombre": nombre, **extra}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _crear_producto(client, token, codigo="P300", nombre="Café", precio=5000, stock=10):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={"codigo": codigo, "nombre": nombre, "precio": precio, "stock_inicial": stock},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _vender(client, token, producto_id, cliente_id=None):
    resp = client.post(
        "/api/facturas/",
        headers=auth(token),
        json={
            "cliente_id": cliente_id,
            "detalles": [{"producto_id": producto_id, "cantidad": 1}],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_elimina_cliente_sin_facturas(client, token_admin):
    cliente = _crear_cliente(client, token_admin)

    resp = client.delete(f"/api/clientes/{cliente['id']}", headers=auth(token_admin))

    assert resp.status_code == 204, resp.text
    assert client.get(f"/api/clientes/{cliente['id']}", headers=auth(token_admin)).status_code == 404


def test_no_elimina_cliente_con_facturas(client, token_admin):
    cliente = _crear_cliente(client, token_admin)
    producto = _crear_producto(client, token_admin)
    factura = _vender(client, token_admin, producto["id"], cliente_id=cliente["id"])

    resp = client.delete(f"/api/clientes/{cliente['id']}", headers=auth(token_admin))

    assert resp.status_code == 400
    assert "factura" in resp.json()["detail"].lower()
    # El cliente y la venta siguen intactos.
    assert client.get(f"/api/clientes/{cliente['id']}", headers=auth(token_admin)).status_code == 200
    detalle = client.get(f"/api/facturas/{factura['id']}", headers=auth(token_admin))
    assert detalle.status_code == 200
    assert detalle.json()["cliente_id"] == cliente["id"]


def test_no_elimina_cliente_eventual(client, token_admin):
    producto = _crear_producto(client, token_admin)
    # Una venta sin cliente crea (o reutiliza) el registro "Cliente eventual".
    _vender(client, token_admin, producto["id"])

    db = SessionLocal()
    try:
        eventual = db.query(Cliente).filter(Cliente.es_eventual == True).first()
        assert eventual is not None
        eventual_id = eventual.id
    finally:
        db.close()

    resp = client.delete(f"/api/clientes/{eventual_id}", headers=auth(token_admin))

    assert resp.status_code == 400
    assert "registro del sistema" in resp.json()["detail"].lower()


def test_cajero_no_puede_eliminar_clientes_por_defecto(client, token_cajero, token_admin):
    cliente = _crear_cliente(client, token_cajero)

    resp = client.delete(f"/api/clientes/{cliente['id']}", headers=auth(token_cajero))
    assert resp.status_code == 403

    # El Admin sí tiene el permiso y puede borrarlo si no tiene ventas.
    resp = client.delete(f"/api/clientes/{cliente['id']}", headers=auth(token_admin))
    assert resp.status_code == 204, resp.text


def test_la_bd_rechaza_borrar_cliente_con_facturas():
    """Protección de último nivel: FK con ON DELETE RESTRICT.

    Se usa una base SQLite en memoria con las FK habilitadas para comprobar que
    el ORM no "desvincula" las facturas (passive_deletes) y que la restricción
    de la base de datos frena el borrado.
    """
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _habilitar_fk(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            cliente = Cliente(nombre="Cliente con historial")
            db.add(cliente)
            db.flush()
            db.add(Factura(cliente_id=cliente.id, total=100, saldo=100))
            db.commit()

            db.delete(cliente)
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
    finally:
        engine.dispose()


# --- Fusión de duplicados ---

def test_fusiona_duplicados_y_conserva_las_facturas(client, token_admin):
    producto = _crear_producto(client, token_admin)
    principal = _crear_cliente(client, token_admin, "Juan Pérez")
    duplicado_1 = _crear_cliente(client, token_admin, "Juan P.")
    duplicado_2 = _crear_cliente(client, token_admin, "J. Pérez")
    facturas = [
        _vender(client, token_admin, producto["id"], cliente_id=principal["id"]),
        _vender(client, token_admin, producto["id"], cliente_id=duplicado_1["id"]),
        _vender(client, token_admin, producto["id"], cliente_id=duplicado_2["id"]),
    ]

    resp = client.post(
        "/api/clientes/fusionar",
        headers=auth(token_admin),
        json={
            "destino_id": principal["id"],
            "origen_ids": [duplicado_1["id"], duplicado_2["id"]],
        },
    )

    assert resp.status_code == 200, resp.text
    resultado = resp.json()
    assert resultado["cliente"]["id"] == principal["id"]
    assert resultado["facturas_reasignadas"] == 2
    assert resultado["clientes_eliminados"] == 2

    # Las tres facturas siguen existiendo y ahora apuntan al cliente principal.
    for factura in facturas:
        detalle = client.get(
            f"/api/facturas/{factura['id']}", headers=auth(token_admin)
        )
        assert detalle.status_code == 200
        assert detalle.json()["cliente_id"] == principal["id"]
        assert detalle.json()["cliente_nombre"] == "Juan Pérez"

    # Los duplicados ya no existen.
    for duplicado in (duplicado_1, duplicado_2):
        resp = client.get(
            f"/api/clientes/{duplicado['id']}", headers=auth(token_admin)
        )
        assert resp.status_code == 404


def test_fusion_completa_datos_unicos_del_duplicado(client, token_admin):
    principal = _crear_cliente(client, token_admin, "Ana")
    duplicado = _crear_cliente(
        client,
        token_admin,
        "Ana P.",
        documento="123456",
        celular="3001234567",
        correo="ana@example.com",
    )

    resp = client.post(
        "/api/clientes/fusionar",
        headers=auth(token_admin),
        json={"destino_id": principal["id"], "origen_ids": [duplicado["id"]]},
    )

    assert resp.status_code == 200, resp.text
    cliente = resp.json()["cliente"]
    assert cliente["nombre"] == "Ana"
    assert cliente["documento"] == "123456"
    assert cliente["celular"] == "3001234567"
    assert cliente["correo"] == "ana@example.com"


def test_fusion_no_copia_datos_ambiguos(client, token_admin):
    principal = _crear_cliente(client, token_admin, "Ana")
    _crear_cliente(client, token_admin, "Ana 1", celular="3001111111")
    _crear_cliente(client, token_admin, "Ana 2", celular="3002222222")

    ids = [
        cliente["id"]
        for cliente in client.get(
            "/api/clientes/?limit=100", headers=auth(token_admin)
        ).json()["items"]
        if cliente["nombre"] != "Ana"
    ]
    resp = client.post(
        "/api/clientes/fusionar",
        headers=auth(token_admin),
        json={"destino_id": principal["id"], "origen_ids": ids},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["cliente"]["celular"] is None


def test_fusion_rechaza_cliente_eventual(client, token_admin):
    producto = _crear_producto(client, token_admin)
    principal = _crear_cliente(client, token_admin)
    _vender(client, token_admin, producto["id"])  # crea el cliente eventual

    db = SessionLocal()
    try:
        eventual = db.query(Cliente).filter(Cliente.es_eventual == True).first()
        assert eventual is not None
        eventual_id = eventual.id
    finally:
        db.close()

    resp = client.post(
        "/api/clientes/fusionar",
        headers=auth(token_admin),
        json={"destino_id": principal["id"], "origen_ids": [eventual_id]},
    )

    assert resp.status_code == 400
    assert "eventual" in resp.json()["detail"].lower()


def test_fusion_rechaza_destino_entre_origenes(client, token_admin):
    cliente = _crear_cliente(client, token_admin)

    resp = client.post(
        "/api/clientes/fusionar",
        headers=auth(token_admin),
        json={"destino_id": cliente["id"], "origen_ids": [cliente["id"]]},
    )

    assert resp.status_code == 400


def test_fusion_rechaza_clientes_inexistentes(client, token_admin):
    principal = _crear_cliente(client, token_admin)

    resp = client.post(
        "/api/clientes/fusionar",
        headers=auth(token_admin),
        json={"destino_id": principal["id"], "origen_ids": [99999]},
    )

    assert resp.status_code == 404


def test_cajero_no_puede_fusionar_clientes(client, token_cajero):
    principal = _crear_cliente(client, token_cajero)
    duplicado = _crear_cliente(client, token_cajero, "Duplicado")

    resp = client.post(
        "/api/clientes/fusionar",
        headers=auth(token_cajero),
        json={"destino_id": principal["id"], "origen_ids": [duplicado["id"]]},
    )

    assert resp.status_code == 403

