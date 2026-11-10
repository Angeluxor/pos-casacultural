"""Pruebas de los traslados entre efectivo y banco."""
from .conftest import auth


def _abrir_caja(client, token, efectivo=0, banco=0):
    resp = client.post(
        "/api/caja/abrir",
        headers=auth(token),
        json={"saldo_inicial_efectivo": efectivo, "saldo_inicial_banco": banco},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _traslado(client, token, **datos):
    cuerpo = {"origen": "Banco", "monto": 10000}
    cuerpo.update(datos)
    return client.post("/api/caja/traslados", headers=auth(token), json=cuerpo)


def _turno(client, token, turno_id):
    resp = client.get("/api/caja/turnos?limit=10&incluir_abierta=true", headers=auth(token))
    assert resp.status_code == 200, resp.text
    return next(t for t in resp.json()["items"] if t["id"] == turno_id)


def test_traslado_banco_a_efectivo_reparte_sin_cambiar_el_total(client, token_admin):
    turno_id = _abrir_caja(client, token_admin, efectivo=50000, banco=200000)

    resp = _traslado(client, token_admin, origen="Banco", monto=100000)
    assert resp.status_code == 200, resp.text
    datos = resp.json()
    assert datos["origen"] == "Banco" and datos["destino"] == "Efectivo"
    assert datos["salida"]["tipo"] == "Salida"
    assert datos["salida"]["forma_pago"] == "Transferencia"
    assert datos["entrada"]["tipo"] == "Entrada"
    assert datos["entrada"]["forma_pago"] == "Efectivo"
    assert datos["salida"]["categoria"] == datos["entrada"]["categoria"] == "Traslado"
    assert datos["salida"]["referencia"] == datos["entrada"]["referencia"]

    turno = _turno(client, token_admin, turno_id)
    assert turno["esperado_efectivo"] == 150000
    assert turno["esperado_banco"] == 100000
    assert turno["esperado_efectivo"] + turno["esperado_banco"] == 250000


def test_traslado_efectivo_a_banco(client, token_admin):
    turno_id = _abrir_caja(client, token_admin, efectivo=80000, banco=0)
    resp = _traslado(client, token_admin, origen="Efectivo", monto=30000)
    assert resp.status_code == 200, resp.text
    turno = _turno(client, token_admin, turno_id)
    assert turno["esperado_efectivo"] == 50000
    assert turno["esperado_banco"] == 30000


def test_traslado_exige_caja_abierta_y_monto_valido(client, token_admin):
    assert _traslado(client, token_admin).status_code == 400
    _abrir_caja(client, token_admin, efectivo=1000)
    assert _traslado(client, token_admin, monto=0).status_code == 422
    assert _traslado(client, token_admin, monto=-5).status_code == 422
    assert _traslado(client, token_admin, origen="Otro").status_code == 422


def test_traslado_no_es_gasto_ni_venta_en_balance_y_reportes(client, token_admin):
    _abrir_caja(client, token_admin, efectivo=50000, banco=50000)
    antes = client.get("/api/balance", headers=auth(token_admin)).json()
    assert _traslado(client, token_admin, origen="Efectivo", monto=20000).status_code == 200
    despues = client.get("/api/balance", headers=auth(token_admin)).json()
    assert despues["resultados"]["gastos_caja"] == antes["resultados"]["gastos_caja"] == 0
    assert despues["resultados"]["gastos"] == antes["resultados"]["gastos"]
    assert despues["caja"]["efectivo"] == 30000 and despues["caja"]["banco"] == 70000


def test_traslado_pide_permiso_de_operar_caja(client, token_admin, token_mesero):
    _abrir_caja(client, token_admin, efectivo=1000)
    assert _traslado(client, token_mesero).status_code == 403


def test_traslado_aparece_como_categoria_propia_en_movimientos(client, token_admin):
    turno_id = _abrir_caja(client, token_admin, efectivo=1000, banco=1000)
    assert _traslado(client, token_admin, referencia="Vuelto del gasto").status_code == 200
    resp = client.get(
        f"/api/caja/{turno_id}/movimientos?categoria=Traslado", headers=auth(token_admin)
    )
    assert resp.status_code == 200
    movs = resp.json()
    assert len(movs) == 2
    assert {m["referencia"] for m in movs} == {"Vuelto del gasto"}
