"""Pruebas del rol Mesero y del control de permisos por rol."""
from .conftest import auth


def _abrir_caja(client, token):
    resp = client.post(
        "/api/caja/abrir",
        headers=auth(token),
        json={"saldo_inicial_efectivo": 0, "saldo_inicial_banco": 0},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _crear_producto(client, token, codigo="P1", nombre="Cerveza", precio=5000, stock=10):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={"codigo": codigo, "nombre": nombre, "precio": precio, "stock_inicial": stock},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- Permisos efectivos en /me ---

def test_me_devuelve_permisos(client, token_cajero, token_mesero):
    cajero = client.get("/api/auth/me", headers=auth(token_cajero)).json()
    assert "ventas.cobrar" in cajero["permisos"]
    assert "reportes.ver" not in cajero["permisos"]

    mesero = client.get("/api/auth/me", headers=auth(token_mesero)).json()
    assert mesero["rol"] == "Mesero"
    assert {"ventas.crear", "ventas.cobrar", "clientes.editar", "caja.ver"} <= set(
        mesero["permisos"]
    )
    # El mesero es más limitado: no opera caja, ni ingresos, ni reportes.
    assert "caja.operar" not in mesero["permisos"]
    assert "ingresos.ver" not in mesero["permisos"]
    assert "reportes.ver" not in mesero["permisos"]
    assert "usuarios.gestionar" not in mesero["permisos"]


# --- El mesero sí puede tomar pedidos y cobrar ---

def test_mesero_toma_pedido_y_cobra(client, token_mesero, token_cajero):
    _abrir_caja(client, token_cajero)
    producto = _crear_producto(client, token_cajero)

    venta = client.post(
        "/api/facturas/",
        headers=auth(token_mesero),
        json={"detalles": [{"producto_id": producto["id"], "cantidad": 2}]},
    )
    assert venta.status_code == 200, venta.text
    factura = venta.json()

    pago = client.post(
        f"/api/facturas/{factura['id']}/pagos",
        headers=auth(token_mesero),
        json={"valor": factura["total"], "forma_pago": "Efectivo"},
    )
    assert pago.status_code == 200, pago.text
    assert pago.json()["estado"] == "Pagada"


def test_mesero_ve_caja_pero_no_la_abre(client, token_mesero):
    # Ver caja: sin turno abierto responde 404 (no 403), es decir, tiene permiso.
    assert client.get("/api/caja/activa", headers=auth(token_mesero)).status_code == 404
    # Operar caja: prohibido.
    resp = client.post(
        "/api/caja/abrir",
        headers=auth(token_mesero),
        json={"saldo_inicial_efectivo": 0, "saldo_inicial_banco": 0},
    )
    assert resp.status_code == 403


# --- El mesero no entra a los módulos administrativos ---

def test_mesero_no_ve_ingresos(client, token_mesero):
    assert client.get("/api/ingresos/", headers=auth(token_mesero)).status_code == 403


def test_mesero_no_ve_reportes(client, token_mesero):
    assert client.get("/api/reportes/ventas", headers=auth(token_mesero)).status_code == 403


def test_mesero_no_gestiona_usuarios(client, token_mesero):
    assert client.get("/api/usuarios/", headers=auth(token_mesero)).status_code == 403


def test_mesero_no_edita_productos(client, token_mesero, token_cajero):
    producto = _crear_producto(client, token_cajero, codigo="P2", nombre="Agua")
    resp = client.put(
        f"/api/productos/{producto['id']}",
        headers=auth(token_mesero),
        json={"precio": 9999},
    )
    assert resp.status_code == 403


def test_mesero_no_anula_facturas(client, token_mesero):
    venta = client.post(
        "/api/facturas/", headers=auth(token_mesero), json={"detalles": []}
    )
    assert venta.status_code == 200, venta.text
    resp = client.post(
        f"/api/facturas/{venta.json()['id']}/anular",
        headers=auth(token_mesero),
        json={},
    )
    assert resp.status_code == 403


# --- Control de permisos (solo Admin por defecto) ---

def test_permisos_requiere_permiso(client, token_cajero):
    assert client.get("/api/permisos/", headers=auth(token_cajero)).status_code == 403


def test_admin_ve_catalogo_y_roles(client, token_admin):
    resp = client.get("/api/permisos/", headers=auth(token_admin))
    assert resp.status_code == 200, resp.text
    data = resp.json()

    claves = [p["clave"] for m in data["modulos"] for p in m["permisos"]]
    assert "ventas.cobrar" in claves
    assert set(data["todos"]) == set(claves)

    assert set(data["roles"].keys()) == {"Cajero", "Mesero"}
    assert "caja.operar" in data["roles"]["Cajero"]
    assert "caja.operar" not in data["roles"]["Mesero"]


def test_admin_edita_permisos_de_mesero(client, token_admin, token_mesero):
    resp = client.put(
        "/api/permisos/Mesero",
        headers=auth(token_admin),
        json={"permisos": ["ventas.ver", "ingresos.ver"]},
    )
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["permisos"]) == {"ventas.ver", "ingresos.ver"}

    # Ahora puede ver ingresos pero perdió el permiso de crear facturas.
    assert client.get("/api/ingresos/", headers=auth(token_mesero)).status_code == 200
    resp = client.post(
        "/api/facturas/", headers=auth(token_mesero), json={"detalles": []}
    )
    assert resp.status_code == 403


def test_permisos_de_admin_no_se_editan(client, token_admin):
    resp = client.put(
        "/api/permisos/Admin", headers=auth(token_admin), json={"permisos": []}
    )
    assert resp.status_code == 400


def test_rol_inexistente(client, token_admin):
    resp = client.put(
        "/api/permisos/NoExiste", headers=auth(token_admin), json={"permisos": []}
    )
    assert resp.status_code == 404


def test_claves_invalidas_se_descartan(client, token_admin):
    resp = client.put(
        "/api/permisos/Mesero",
        headers=auth(token_admin),
        json={"permisos": ["ventas.ver", "clave.inventada"]},
    )
    assert resp.status_code == 200
    assert resp.json()["permisos"] == ["ventas.ver"]
