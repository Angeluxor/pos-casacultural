"""Pruebas del vínculo usuario↔cliente y del descuento de nómina.

Un usuario se puede vincular (uno a uno) a un cliente para descontar de su
nómina las compras a crédito. El descuento baja el saldo de las facturas y crea
pagos con forma de pago ``Nómina``, pero **no** genera movimientos de caja.
"""
from app.db.models import DescuentoNomina, FormaPago, Pago, RegistroCaja
from app.db.session import SessionLocal

from .conftest import auth


def _crear_cliente(client, token, nombre="Empleado Uno", **extra):
    resp = client.post(
        "/api/clientes/", headers=auth(token), json={"nombre": nombre, **extra}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _crear_producto(client, token, codigo="P500", precio=5000, stock=50):
    resp = client.post(
        "/api/productos/",
        headers=auth(token),
        json={"codigo": codigo, "nombre": "Producto", "precio": precio, "stock_inicial": stock},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _crear_empleado(client, token, username="empleado", cliente_id=None, password="clave12345"):
    resp = client.post(
        "/api/usuarios/",
        headers=auth(token),
        json={
            "username": username,
            "nombre": username.capitalize(),
            "password": password,
            "rol": "Cajero",
            "activo": True,
            "cliente_id": cliente_id,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _vender(client, token, producto_id, cliente_id):
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


# --- Vínculo usuario ↔ cliente ---

def test_vincula_usuario_a_cliente(client, token_admin):
    cliente = _crear_cliente(client, token_admin)

    empleado = _crear_empleado(client, token_admin, cliente_id=cliente["id"])

    assert empleado["cliente_id"] == cliente["id"]
    assert empleado["cliente_nombre"] == cliente["nombre"]

    listado = client.get("/api/usuarios/?limit=100", headers=auth(token_admin)).json()
    fila = next(u for u in listado["items"] if u["id"] == empleado["id"])
    assert fila["cliente_nombre"] == cliente["nombre"]


def test_desvincula_usuario(client, token_admin):
    cliente = _crear_cliente(client, token_admin)
    empleado = _crear_empleado(client, token_admin, cliente_id=cliente["id"])

    resp = client.put(
        f"/api/usuarios/{empleado['id']}",
        headers=auth(token_admin),
        json={"cliente_id": None},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["cliente_id"] is None


def test_no_vincula_cliente_ya_vinculado(client, token_admin):
    cliente = _crear_cliente(client, token_admin)
    _crear_empleado(client, token_admin, username="empleado1", cliente_id=cliente["id"])

    resp = client.post(
        "/api/usuarios/",
        headers=auth(token_admin),
        json={
            "username": "empleado2",
            "nombre": "Empleado Dos",
            "password": "clave12345",
            "rol": "Cajero",
            "activo": True,
            "cliente_id": cliente["id"],
        },
    )

    assert resp.status_code == 400
    assert "vinculado" in resp.json()["detail"].lower()


def test_no_vincula_cliente_eventual(client, token_admin):
    producto = _crear_producto(client, token_admin)
    _vender(client, token_admin, producto["id"], cliente_id=None)

    # El cliente eventual es el único registro del sistema (es_eventual=True).
    resp = client.get(
        "/api/usuarios/clientes-disponibles", headers=auth(token_admin)
    )
    assert resp.status_code == 200, resp.text
    nombres = [c["nombre"] for c in resp.json()]
    assert "Cliente eventual" not in nombres


def test_clientes_disponibles_excluye_vinculados(client, token_admin):
    disponible = _crear_cliente(client, token_admin, "Disponible")
    vinculado = _crear_cliente(client, token_admin, "Vinculado")
    empleado = _crear_empleado(client, token_admin, cliente_id=vinculado["id"])

    libres = client.get(
        "/api/usuarios/clientes-disponibles", headers=auth(token_admin)
    ).json()
    ids = [c["id"] for c in libres]
    assert disponible["id"] in ids
    assert vinculado["id"] not in ids

    # Al editar al usuario se conserva su cliente actual en la lista.
    con_actual = client.get(
        f"/api/usuarios/clientes-disponibles?usuario_id={empleado['id']}",
        headers=auth(token_admin),
    ).json()
    ids_actual = [c["id"] for c in con_actual]
    assert vinculado["id"] in ids_actual


# --- Fusión conserva el vínculo ---

def test_fusion_transfiere_vinculo_de_nomina(client, token_admin):
    principal = _crear_cliente(client, token_admin, "Principal")
    duplicado = _crear_cliente(client, token_admin, "Duplicado")
    empleado = _crear_empleado(client, token_admin, cliente_id=duplicado["id"])

    resp = client.post(
        "/api/clientes/fusionar",
        headers=auth(token_admin),
        json={"destino_id": principal["id"], "origen_ids": [duplicado["id"]]},
    )

    assert resp.status_code == 200, resp.text
    detalle = client.get(
        f"/api/usuarios/{empleado['id']}", headers=auth(token_admin)
    ).json()
    assert detalle["cliente_id"] == principal["id"]
    assert detalle["cliente_nombre"] == "Principal"


def test_fusion_rechaza_dos_clientes_vinculados(client, token_admin):
    principal = _crear_cliente(client, token_admin, "Principal")
    duplicado = _crear_cliente(client, token_admin, "Duplicado")
    _crear_empleado(client, token_admin, username="empleado1", cliente_id=principal["id"])
    _crear_empleado(client, token_admin, username="empleado2", cliente_id=duplicado["id"])

    resp = client.post(
        "/api/clientes/fusionar",
        headers=auth(token_admin),
        json={"destino_id": principal["id"], "origen_ids": [duplicado["id"]]},
    )

    assert resp.status_code == 400
    assert "vinculad" in resp.json()["detail"].lower()


def test_no_elimina_cliente_vinculado(client, token_admin):
    cliente = _crear_cliente(client, token_admin)
    _crear_empleado(client, token_admin, cliente_id=cliente["id"])

    resp = client.delete(f"/api/clientes/{cliente['id']}", headers=auth(token_admin))

    assert resp.status_code == 400
    assert "vinculad" in resp.json()["detail"].lower()


# --- Descuento de nómina ---

def test_descuento_total_sin_caja(client, token_admin):
    producto = _crear_producto(client, token_admin)
    cliente = _crear_cliente(client, token_admin)
    empleado = _crear_empleado(client, token_admin, cliente_id=cliente["id"])
    facturas = [
        _vender(client, token_admin, producto["id"], cliente["id"]),
        _vender(client, token_admin, producto["id"], cliente["id"]),
    ]

    deuda = client.get(
        f"/api/usuarios/{empleado['id']}/nomina", headers=auth(token_admin)
    )
    assert deuda.status_code == 200, deuda.text
    assert deuda.json()["saldo_total"] == 10000

    resp = client.post(
        f"/api/usuarios/{empleado['id']}/nomina/descuento",
        headers=auth(token_admin),
        json={},
    )
    assert resp.status_code == 200, resp.text
    resultado = resp.json()
    assert resultado["monto_aplicado"] == 10000
    assert resultado["saldo_pendiente"] == 0
    assert resultado["facturas_afectadas"] == 2

    for factura in facturas:
        detalle = client.get(
            f"/api/facturas/{factura['id']}", headers=auth(token_admin)
        ).json()
        assert detalle["saldo"] == 0
        assert detalle["estado"] == "Pagada"
        assert any(p["forma_pago"] == "Nómina" for p in detalle["pagos"])

    # La nómina no toca la caja: no hay movimientos de entrada/salida.
    db = SessionLocal()
    try:
        assert db.query(RegistroCaja).count() == 0
        assert db.query(Pago).filter(Pago.forma_pago == FormaPago.NOMINA).count() == 2
    finally:
        db.close()


def test_descuento_parcial_va_a_la_factura_mas_antigua(client, token_admin):
    producto = _crear_producto(client, token_admin)
    cliente = _crear_cliente(client, token_admin)
    empleado = _crear_empleado(client, token_admin, cliente_id=cliente["id"])
    primera = _vender(client, token_admin, producto["id"], cliente["id"])
    segunda = _vender(client, token_admin, producto["id"], cliente["id"])

    resp = client.post(
        f"/api/usuarios/{empleado['id']}/nomina/descuento",
        headers=auth(token_admin),
        json={"monto": 3000},
    )

    assert resp.status_code == 200, resp.text
    resultado = resp.json()
    assert resultado["monto_aplicado"] == 3000
    assert resultado["saldo_pendiente"] == 7000
    assert resultado["facturas_afectadas"] == 1

    det_primera = client.get(
        f"/api/facturas/{primera['id']}", headers=auth(token_admin)
    ).json()
    det_segunda = client.get(
        f"/api/facturas/{segunda['id']}", headers=auth(token_admin)
    ).json()
    assert det_primera["saldo"] == 2000
    assert det_primera["estado"] == "Pagado Parcial"
    assert det_segunda["saldo"] == 5000


def test_descuento_rechaza_usuario_sin_cliente(client, token_admin):
    empleado = _crear_empleado(client, token_admin)

    resp = client.post(
        f"/api/usuarios/{empleado['id']}/nomina/descuento",
        headers=auth(token_admin),
        json={},
    )

    assert resp.status_code == 400
    assert "vinculado" in resp.json()["detail"].lower()


def test_descuento_rechaza_sin_deuda(client, token_admin):
    cliente = _crear_cliente(client, token_admin)
    empleado = _crear_empleado(client, token_admin, cliente_id=cliente["id"])

    resp = client.post(
        f"/api/usuarios/{empleado['id']}/nomina/descuento",
        headers=auth(token_admin),
        json={},
    )

    assert resp.status_code == 400
    assert "deuda" in resp.json()["detail"].lower()


def test_descuento_rechaza_monto_mayor_a_la_deuda(client, token_admin):
    producto = _crear_producto(client, token_admin)
    cliente = _crear_cliente(client, token_admin)
    empleado = _crear_empleado(client, token_admin, cliente_id=cliente["id"])
    _vender(client, token_admin, producto["id"], cliente["id"])

    resp = client.post(
        f"/api/usuarios/{empleado['id']}/nomina/descuento",
        headers=auth(token_admin),
        json={"monto": 99999},
    )

    assert resp.status_code == 400
    assert "supera" in resp.json()["detail"].lower()


def test_cajero_no_puede_descontar_nomina(client, token_admin, token_cajero, cajero_id):
    cliente = _crear_cliente(client, token_admin)
    empleado = _crear_empleado(client, token_admin, cliente_id=cliente["id"])

    # El Cajero no tiene `nomina.descontar` por defecto.
    resp = client.post(
        f"/api/usuarios/{empleado['id']}/nomina/descuento",
        headers=auth(token_cajero),
        json={},
    )
    assert resp.status_code == 403


# --- Protecciones del flujo normal de cobro ---

def test_pago_normal_rechaza_forma_nomina(client, token_admin):
    producto = _crear_producto(client, token_admin)
    cliente = _crear_cliente(client, token_admin)
    factura = _vender(client, token_admin, producto["id"], cliente["id"])

    resp = client.post(
        f"/api/facturas/{factura['id']}/pagos",
        headers=auth(token_admin),
        json={"valor": 1000, "forma_pago": "Nómina"},
    )

    assert resp.status_code == 400
    assert "nómina" in resp.json()["detail"].lower()


def test_caja_rechaza_movimiento_con_forma_nomina(client, token_admin):
    client.post(
        "/api/caja/abrir",
        headers=auth(token_admin),
        json={"saldo_inicial_efectivo": 0, "saldo_inicial_banco": 0},
    )

    resp = client.post(
        "/api/caja/movimientos",
        headers=auth(token_admin),
        json={
            "tipo": "Entrada",
            "referencia": "prueba",
            "forma_pago": "Nómina",
            "monto": 1000,
        },
    )

    assert resp.status_code == 400
    assert "nómina" in resp.json()["detail"].lower()


def test_no_anula_factura_con_abonos_de_nomina(client, token_admin):
    producto = _crear_producto(client, token_admin)
    cliente = _crear_cliente(client, token_admin)
    empleado = _crear_empleado(client, token_admin, cliente_id=cliente["id"])
    factura = _vender(client, token_admin, producto["id"], cliente["id"])

    resp = client.post(
        f"/api/usuarios/{empleado['id']}/nomina/descuento",
        headers=auth(token_admin),
        json={},
    )
    assert resp.status_code == 200, resp.text

    resp = client.post(
        f"/api/facturas/{factura['id']}/anular",
        headers=auth(token_admin),
        json={"motivo": "prueba"},
    )

    assert resp.status_code == 400
    assert "nómina" in resp.json()["detail"].lower()


# --- Auditoría: evento, historial y reporte ---

def test_descuento_crea_evento_de_auditoria(client, token_admin):
    producto = _crear_producto(client, token_admin)
    cliente = _crear_cliente(client, token_admin)
    empleado = _crear_empleado(client, token_admin, cliente_id=cliente["id"])
    _vender(client, token_admin, producto["id"], cliente["id"])
    _vender(client, token_admin, producto["id"], cliente["id"])

    resp = client.post(
        f"/api/usuarios/{empleado['id']}/nomina/descuento",
        headers=auth(token_admin),
        json={"nota": "Nómina octubre 2026"},
    )
    assert resp.status_code == 200, resp.text
    resultado = resp.json()
    assert resultado["descuento_id"] > 0
    assert resultado["nota"] == "Nómina octubre 2026"
    assert resultado["facturas_afectadas"] == 2

    db = SessionLocal()
    try:
        evento = db.query(DescuentoNomina).one()
        assert evento.id == resultado["descuento_id"]
        assert evento.usuario_id == empleado["id"]
        # La foto conserva el nombre del empleado y del cliente.
        assert evento.usuario_nombre == empleado["nombre"]
        assert evento.cliente_id == cliente["id"]
        assert evento.cliente_nombre == cliente["nombre"]
        assert evento.registrado_por_nombre == "Admin"
        assert evento.monto == 10000
        assert evento.saldo_pendiente == 0
        assert evento.facturas_afectadas == 2
        assert evento.nota == "Nómina octubre 2026"

        pagos = db.query(Pago).filter(Pago.forma_pago == FormaPago.NOMINA).all()
        assert len(pagos) == 2
        assert all(p.descuento_nomina_id == evento.id for p in pagos)
    finally:
        db.close()


def test_historial_nomina_conserva_la_foto_del_momento(client, token_admin):
    producto = _crear_producto(client, token_admin)
    cliente = _crear_cliente(client, token_admin)
    empleado = _crear_empleado(client, token_admin, cliente_id=cliente["id"])
    factura = _vender(client, token_admin, producto["id"], cliente["id"])

    resp = client.post(
        f"/api/usuarios/{empleado['id']}/nomina/descuento",
        headers=auth(token_admin),
        json={"nota": "Descuento quincena"},
    )
    assert resp.status_code == 200, resp.text

    # Después del descuento, el cliente se renombra y el usuario se desvincula.
    resp = client.put(
        f"/api/clientes/{cliente['id']}",
        headers=auth(token_admin),
        json={"nombre": "Nombre Nuevo"},
    )
    assert resp.status_code == 200, resp.text
    resp = client.put(
        f"/api/usuarios/{empleado['id']}",
        headers=auth(token_admin),
        json={"cliente_id": None},
    )
    assert resp.status_code == 200, resp.text

    resp = client.get(
        f"/api/usuarios/{empleado['id']}/nomina/historial",
        headers=auth(token_admin),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # El vínculo actual ya no existe...
    assert data["cliente_id"] is None
    assert data["cliente_nombre"] is None
    # ...pero el evento conserva la foto y la nota.
    assert data["descuentos"] == 1
    assert data["monto_total"] == 5000
    item = data["items"][0]
    assert item["usuario_nombre"] == empleado["nombre"]
    assert item["cliente_nombre"] == cliente["nombre"]
    assert item["registrado_por"] == "Admin"
    assert item["nota"] == "Descuento quincena"
    # El evento queda enlazado a la factura concreta que cubrió.
    assert len(item["facturas"]) == 1
    assert item["facturas"][0]["factura_id"] == factura["id"]
    assert item["facturas"][0]["abono"] == 5000
    assert item["facturas"][0]["total"] == 5000


def test_reporte_nomina_totaliza_y_filtra_por_empleado(client, token_admin):
    producto = _crear_producto(client, token_admin)

    cliente1 = _crear_cliente(client, token_admin, "Empleado Uno")
    cliente2 = _crear_cliente(client, token_admin, "Empleado Dos")
    empleado1 = _crear_empleado(
        client, token_admin, username="empleado1", cliente_id=cliente1["id"]
    )
    empleado2 = _crear_empleado(
        client, token_admin, username="empleado2", cliente_id=cliente2["id"]
    )

    _vender(client, token_admin, producto["id"], cliente1["id"])
    _vender(client, token_admin, producto["id"], cliente2["id"])
    _vender(client, token_admin, producto["id"], cliente2["id"])

    for empleado in (empleado1, empleado2):
        resp = client.post(
            f"/api/usuarios/{empleado['id']}/nomina/descuento",
            headers=auth(token_admin),
            json={"nota": f"Pago {empleado['username']}"},
        )
        assert resp.status_code == 200, resp.text

    resp = client.get("/api/reportes/nomina", headers=auth(token_admin))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["descuentos"] == 2
    assert data["monto_total"] == 15000
    assert data["facturas_afectadas_total"] == 3

    resp = client.get(
        f"/api/reportes/nomina?usuario_id={empleado1['id']}",
        headers=auth(token_admin),
    )
    assert resp.status_code == 200, resp.text
    filtrado = resp.json()
    assert filtrado["descuentos"] == 1
    assert filtrado["monto_total"] == 5000
    assert filtrado["items"][0]["usuario_nombre"] == empleado1["nombre"]

    # El filtro por fecha usa el día del descuento.
    dia = data["items"][0]["fecha"][:10]
    resp = client.get(
        f"/api/reportes/nomina?desde={dia}&hasta={dia}",
        headers=auth(token_admin),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["descuentos"] == 2


def test_cajero_no_puede_ver_historial_de_nomina(client, token_admin, token_cajero):
    cliente = _crear_cliente(client, token_admin)
    empleado = _crear_empleado(client, token_admin, cliente_id=cliente["id"])

    resp = client.get(
        f"/api/usuarios/{empleado['id']}/nomina/historial",
        headers=auth(token_cajero),
    )
    assert resp.status_code == 403


def test_historial_total_global_aunque_limite_la_lista(client, token_admin):
    producto = _crear_producto(client, token_admin)
    cliente = _crear_cliente(client, token_admin)
    empleado = _crear_empleado(client, token_admin, cliente_id=cliente["id"])
    _vender(client, token_admin, producto["id"], cliente["id"])

    for monto in (2000, 3000):
        resp = client.post(
            f"/api/usuarios/{empleado['id']}/nomina/descuento",
            headers=auth(token_admin),
            json={"monto": monto, "nota": f"Abono {monto}"},
        )
        assert resp.status_code == 200, resp.text

    resp = client.get(
        f"/api/usuarios/{empleado['id']}/nomina/historial?limite=1",
        headers=auth(token_admin),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # La lista se limita a 1, pero los totales cubren todo el historial.
    assert len(data["items"]) == 1
    assert data["items"][0]["monto"] == 3000
    assert data["descuentos"] == 2
    assert data["monto_total"] == 5000
