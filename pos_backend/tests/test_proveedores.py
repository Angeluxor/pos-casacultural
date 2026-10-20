"""Pruebas del catálogo de proveedores y su vínculo con los ingresos."""
from .conftest import auth


def _crear_proveedor(client, token, **cambios):
    datos = {
        "nombre": "Distribuidora La Fría",
        "documento": "900123456-7",
        "celular": "3001234567",
        "correo": "compras@lafria.co",
    }
    datos.update(cambios)
    return client.post("/api/proveedores/", headers=auth(token), json=datos)


def _ingreso_balance(client, token, **cambios):
    datos = {
        "fuente_pago": "Balance general",
        "forma_pago": "Efectivo",
        "total": 10000,
        "items": [{"tipo": "Otros", "concepto": "Flete", "valor": 10000}],
    }
    datos.update(cambios)
    return client.post("/api/ingresos/", headers=auth(token), json=datos)


def test_crud_proveedor(client, token_admin):
    creado = _crear_proveedor(client, token_admin)
    assert creado.status_code == 200, creado.text
    proveedor = creado.json()
    assert proveedor["nombre"] == "Distribuidora La Fría"
    assert proveedor["documento"] == "900123456-7"

    listado = client.get(
        "/api/proveedores/?buscar=lafria", headers=auth(token_admin)
    )
    assert listado.status_code == 200, listado.text
    assert listado.json()["total"] == 1

    actualizado = client.put(
        f"/api/proveedores/{proveedor['id']}",
        headers=auth(token_admin),
        json={"nombre": "La Fría S.A.S.", "celular": "3009999999"},
    )
    assert actualizado.status_code == 200, actualizado.text
    assert actualizado.json()["nombre"] == "La Fría S.A.S."
    assert actualizado.json()["celular"] == "3009999999"

    detalle = client.get(
        f"/api/proveedores/{proveedor['id']}", headers=auth(token_admin)
    )
    assert detalle.status_code == 200
    assert detalle.json()["documento"] == "900123456-7"

    borrado = client.delete(
        f"/api/proveedores/{proveedor['id']}", headers=auth(token_admin)
    )
    assert borrado.status_code == 204
    assert (
        client.get(
            f"/api/proveedores/{proveedor['id']}", headers=auth(token_admin)
        ).status_code
        == 404
    )


def test_documento_duplicado(client, token_admin):
    assert _crear_proveedor(client, token_admin).status_code == 200
    repetido = _crear_proveedor(client, token_admin, nombre="Otro proveedor")
    assert repetido.status_code == 400
    assert "documento" in repetido.json()["detail"].lower()

    otro = _crear_proveedor(
        client, token_admin, nombre="Sin documento", documento=None
    ).json()
    cambio = client.put(
        f"/api/proveedores/{otro['id']}",
        headers=auth(token_admin),
        json={"documento": "900123456-7"},
    )
    assert cambio.status_code == 400


def test_nombre_duplicado(client, token_admin):
    assert _crear_proveedor(client, token_admin).status_code == 200
    repetido = _crear_proveedor(
        client, token_admin, nombre="distribuidora la fría", documento=None
    )
    assert repetido.status_code == 400
    assert "nombre" in repetido.json()["detail"].lower()


def test_cajero_gestiona_pero_no_elimina_por_defecto(client, token_cajero):
    creado = _crear_proveedor(client, token_cajero)
    assert creado.status_code == 200, creado.text

    assert client.get("/api/proveedores/", headers=auth(token_cajero)).status_code == 200

    borrado = client.delete(
        f"/api/proveedores/{creado.json()['id']}", headers=auth(token_cajero)
    )
    assert borrado.status_code == 403


def test_mesero_no_gestiona_proveedores(client, token_mesero):
    assert client.get("/api/proveedores/", headers=auth(token_mesero)).status_code == 403
    assert _crear_proveedor(client, token_mesero).status_code == 403


def test_ingreso_enlaza_proveedor_por_id_y_por_nombre(client, token_admin):
    proveedor = _crear_proveedor(client, token_admin).json()

    por_id = _ingreso_balance(client, token_admin, proveedor_id=proveedor["id"])
    assert por_id.status_code == 200, por_id.text
    assert por_id.json()["proveedor_id"] == proveedor["id"]
    assert por_id.json()["proveedor"] == proveedor["nombre"]

    # Enviar solo el nombre crea el proveedor si no existe.
    nuevo = _ingreso_balance(client, token_admin, proveedor="Fletes del Norte")
    assert nuevo.status_code == 200, nuevo.text
    assert nuevo.json()["proveedor"] == "Fletes del Norte"
    assert nuevo.json()["proveedor_id"] is not None

    # El mismo nombre con otra capitalización reutiliza el proveedor.
    repetido = _ingreso_balance(client, token_admin, proveedor="fletes del norte")
    assert repetido.status_code == 200, repetido.text
    assert repetido.json()["proveedor_id"] == nuevo.json()["proveedor_id"]

    listado = client.get(
        "/api/proveedores/?buscar=fletes", headers=auth(token_admin)
    ).json()
    assert listado["total"] == 1


def test_no_elimina_proveedor_con_ingresos(client, token_admin):
    proveedor = _crear_proveedor(client, token_admin).json()
    assert _ingreso_balance(
        client, token_admin, proveedor_id=proveedor["id"]
    ).status_code == 200

    borrado = client.delete(
        f"/api/proveedores/{proveedor['id']}", headers=auth(token_admin)
    )
    assert borrado.status_code == 400
    assert "ingreso" in borrado.json()["detail"].lower()


def test_editar_ingreso_cambia_y_limpia_proveedor(client, token_admin):
    proveedor = _crear_proveedor(client, token_admin).json()
    ingreso = _ingreso_balance(
        client, token_admin, proveedor_id=proveedor["id"]
    ).json()

    cambio = client.put(
        f"/api/ingresos/{ingreso['id']}",
        headers=auth(token_admin),
        json={"proveedor_id": None},
    )
    assert cambio.status_code == 200, cambio.text
    assert cambio.json()["proveedor_id"] is None
    assert cambio.json()["proveedor"] is None
