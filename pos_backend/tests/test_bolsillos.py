"""Pruebas de los bolsillos de gastos vitales."""
from .conftest import auth


def _abrir_caja(client, token, efectivo=100000, banco=50000):
    resp = client.post(
        "/api/caja/abrir",
        headers=auth(token),
        json={"saldo_inicial_efectivo": efectivo, "saldo_inicial_banco": banco},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _crear_bolsillo(
    client,
    token,
    nombre="Arriendo",
    descripcion="Reserva mensual",
    saldo_inicial=None,
):
    datos = {"nombre": nombre, "descripcion": descripcion}
    if saldo_inicial is not None:
        datos["saldo_inicial"] = saldo_inicial
    resp = client.post(
        "/api/balance/bolsillos",
        headers=auth(token),
        json=datos,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _movimiento(client, token, bolsillo_id, tipo, monto, nota=None):
    return client.post(
        f"/api/balance/bolsillos/{bolsillo_id}/movimientos",
        headers=auth(token),
        json={"tipo": tipo, "monto": monto, "nota": nota},
    )


def test_enum_bolsillo_usa_los_nombres_que_espera_postgres():
    # SQLAlchemy persiste los nombres del Enum (APORTE/RETIRO), no sus valores
    # legibles. La migración 0014 debe crear el tipo con esas mismas etiquetas.
    from app.db.models import BolsilloMovimiento

    assert BolsilloMovimiento.__table__.c.tipo.type.enums == ["APORTE", "RETIRO"]


def test_saldo_inicial_suma_al_bolsillo_sin_descontar_caja(client, token_admin):
    _abrir_caja(client, token_admin, efectivo=100000, banco=50000)

    bolsillo = _crear_bolsillo(client, token_admin, saldo_inicial=50000)
    assert bolsillo["reservado"] == 50000
    assert bolsillo["saldo_inicial"] == 50000

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["total_reservado"] == 50000
    assert balance["activos"]["reservado"] == 50000
    assert balance["activos"]["reservado_inicial"] == 50000
    assert balance["activos"]["reservado_caja"] == 0
    # El saldo inicial no reduce el dinero disponible.
    assert balance["activos"]["disponible"] == 150000
    assert balance["caja"]["disponible"] == 150000
    assert balance["activos"]["total"] == 150000

    # Los aportes posteriores sí se descuentan de la caja/banco.
    aporte = _movimiento(client, token_admin, bolsillo["id"], "Aporte", 30000)
    assert aporte.status_code == 200, aporte.text
    assert aporte.json()["es_inicial"] is False
    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["activos"]["reservado"] == 80000
    assert balance["activos"]["reservado_inicial"] == 50000
    assert balance["activos"]["reservado_caja"] == 30000
    assert balance["activos"]["disponible"] == 120000

    # El historial identifica el saldo inicial como un movimiento propio.
    historial = client.get(
        f"/api/balance/bolsillos/{bolsillo['id']}/movimientos",
        headers=auth(token_admin),
    ).json()
    inicial = next(m for m in historial if m["es_inicial"])
    assert inicial["tipo"] == "Aporte"
    assert inicial["monto"] == 50000
    assert inicial["nota"] == "Saldo inicial"

    # Solo los aportes pueden marcarse como saldo inicial.
    invalido = client.post(
        f"/api/balance/bolsillos/{bolsillo['id']}/movimientos",
        headers=auth(token_admin),
        json={"tipo": "Retiro", "monto": 1000, "es_inicial": True},
    )
    assert invalido.status_code == 400
    assert "aporte" in invalido.json()["detail"].lower()


def test_saldo_inicial_de_bolsillo_existente(client, token_admin):
    _abrir_caja(client, token_admin, efectivo=100000, banco=50000)
    bolsillo = _crear_bolsillo(client, token_admin)

    # Simula el caso del ticket: el bolsillo ya existía vacío y luego se
    # registra el saldo que ya estaba apartado.
    resp = client.post(
        f"/api/balance/bolsillos/{bolsillo['id']}/movimientos",
        headers=auth(token_admin),
        json={"tipo": "Aporte", "monto": 40000, "es_inicial": True},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["es_inicial"] is True

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["activos"]["reservado"] == 40000
    assert balance["activos"]["reservado_inicial"] == 40000
    assert balance["activos"]["disponible"] == 150000


def test_bolsillo_aparta_dinero_sin_cambiar_activos(client, token_admin):
    _abrir_caja(client, token_admin, efectivo=100000, banco=50000)

    bolsillo = _crear_bolsillo(client, token_admin)
    assert bolsillo["reservado"] == 0

    aporte = _movimiento(
        client, token_admin, bolsillo["id"], "Aporte", 30000, "Arriendo de noviembre"
    )
    assert aporte.status_code == 200, aporte.text
    assert aporte.json()["tipo"] == "Aporte"
    assert aporte.json()["usuario_nombre"] == "Admin"

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["total_reservado"] == 30000
    assert balance["activos"]["reservado"] == 30000
    assert balance["activos"]["disponible"] == 120000
    # El dinero sigue existiendo: el total de activos no cambia por apartarlo.
    assert balance["activos"]["total"] == 150000
    assert balance["caja"]["reservado"] == 30000
    assert balance["caja"]["disponible"] == 120000

    # No se puede apartar más de lo que hay disponible.
    excesivo = _movimiento(
        client, token_admin, bolsillo["id"], "Aporte", 200000
    )
    assert excesivo.status_code == 400
    assert "disponible" in excesivo.json()["detail"].lower()

    # Tampoco se puede liberar más de lo reservado.
    excesivo_retiro = _movimiento(
        client, token_admin, bolsillo["id"], "Retiro", 40000
    )
    assert excesivo_retiro.status_code == 400
    assert "reservado" in excesivo_retiro.json()["detail"].lower()

    retiro = _movimiento(
        client, token_admin, bolsillo["id"], "Retiro", 10000, "Ajuste"
    )
    assert retiro.status_code == 200, retiro.text
    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["total_reservado"] == 20000
    assert balance["activos"]["disponible"] == 130000
    assert balance["activos"]["total"] == 150000

    # No se archiva un bolsillo con saldo.
    archivar = client.delete(
        f"/api/balance/bolsillos/{bolsillo['id']}", headers=auth(token_admin)
    )
    assert archivar.status_code == 400
    assert "saldo" in archivar.json()["detail"].lower()

    # Se libera el resto y se archiva conservando el historial.
    assert (
        _movimiento(
            client, token_admin, bolsillo["id"], "Retiro", 20000
        ).status_code
        == 200
    )
    archivar = client.delete(
        f"/api/balance/bolsillos/{bolsillo['id']}", headers=auth(token_admin)
    )
    assert archivar.status_code == 204

    balance = client.get("/api/balance", headers=auth(token_admin)).json()
    assert balance["total_reservado"] == 0
    assert balance["activos"]["disponible"] == 150000
    assert balance["bolsillos"] == []

    historial = client.get(
        f"/api/balance/bolsillos/{bolsillo['id']}/movimientos",
        headers=auth(token_admin),
    )
    assert historial.status_code == 200
    assert len(historial.json()) == 3


def test_bolsillo_nombre_duplicado_y_permisos(client, token_admin, token_cajero):
    permisos_cajero = client.get(
        "/api/permisos", headers=auth(token_admin)
    ).json()["roles"]["Cajero"]

    _abrir_caja(client, token_admin)
    _crear_bolsillo(client, token_admin)

    duplicado = client.post(
        "/api/balance/bolsillos",
        headers=auth(token_admin),
        json={"nombre": " arriendo "},
    )
    assert duplicado.status_code == 400
    assert "ya existe" in duplicado.json()["detail"].lower()

    # El cajero no tiene balance.ver por defecto.
    assert (
        client.get(
            "/api/balance/bolsillos", headers=auth(token_cajero)
        ).status_code
        == 403
    )

    # Con balance.ver puede consultar, pero no administrar.
    resp = client.put(
        "/api/permisos/Cajero",
        headers=auth(token_admin),
        json={"permisos": ["balance.ver"]},
    )
    assert resp.status_code == 200, resp.text
    assert (
        client.get(
            "/api/balance/bolsillos", headers=auth(token_cajero)
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/balance/bolsillos",
            headers=auth(token_cajero),
            json={"nombre": "Otro"},
        ).status_code
        == 403
    )

    # Con balance.editar también puede administrar.
    resp = client.put(
        "/api/permisos/Cajero",
        headers=auth(token_admin),
        json={"permisos": ["balance.ver", "balance.editar"]},
    )
    assert resp.status_code == 200, resp.text
    creado = client.post(
        "/api/balance/bolsillos",
        headers=auth(token_cajero),
        json={"nombre": "Servicios"},
    )
    assert creado.status_code == 200, creado.text

    # Restaura los permisos del rol para no afectar otras pruebas.
    resp = client.put(
        "/api/permisos/Cajero",
        headers=auth(token_admin),
        json={"permisos": permisos_cajero},
    )
    assert resp.status_code == 200, resp.text


def test_dashboard_muestra_reservado_y_ventas_mes_a_mes(client, token_admin):
    _abrir_caja(client, token_admin, efectivo=100000, banco=50000)
    bolsillo = _crear_bolsillo(client, token_admin)
    assert (
        _movimiento(
            client, token_admin, bolsillo["id"], "Aporte", 30000
        ).status_code
        == 200
    )

    # Una venta para que el mes actual tenga datos.
    producto = client.post(
        "/api/productos/",
        headers=auth(token_admin),
        json={
            "codigo": "DASH1",
            "nombre": "Producto dashboard",
            "precio": 12000,
            "stock_inicial": 2,
        },
    )
    assert producto.status_code == 200, producto.text
    producto = producto.json()
    venta = client.post(
        "/api/facturas/",
        headers=auth(token_admin),
        json={"detalles": [{"producto_id": producto["id"], "cantidad": 1}]},
    )
    assert venta.status_code == 200, venta.text
    cobro = client.post(
        f"/api/facturas/{venta.json()['id']}/pagos",
        headers=auth(token_admin),
        json={"valor": venta.json()["total"], "forma_pago": "Efectivo"},
    )
    assert cobro.status_code == 200, cobro.text

    dashboard = client.get("/api/dashboard/", headers=auth(token_admin))
    assert dashboard.status_code == 200, dashboard.text
    datos = dashboard.json()

    assert len(datos["ventas_ultimos_12_meses"]) == 12
    mes_actual = datos["ventas_ultimos_12_meses"][-1]
    assert datos["kpis"]["ventas_mes_total"] == mes_actual["total"]
    assert datos["kpis"]["ventas_mes_cantidad"] == mes_actual["cantidad"]
    assert mes_actual["total"] == 12000
    assert mes_actual["cantidad"] == 1
    assert datos["caja"]["reservado"] == 30000
    assert datos["caja"]["disponible"] == 132000  # 150.000 + 12.000 - 30.000


def test_dashboard_disponible_no_descuenta_saldo_inicial(client, token_admin):
    _abrir_caja(client, token_admin, efectivo=100000, banco=50000)
    # Saldo inicial: ya estaba apartado antes de usar la app, no sale de caja.
    _crear_bolsillo(client, token_admin, saldo_inicial=50000)

    dashboard = client.get("/api/dashboard/", headers=auth(token_admin))
    assert dashboard.status_code == 200, dashboard.text
    caja = dashboard.json()["caja"]
    assert caja["reservado"] == 50000
    assert caja["disponible"] == 150000  # 150.000 de caja; el inicial no descuenta
