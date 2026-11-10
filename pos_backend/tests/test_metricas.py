"""Pruebas del registro de métricas de rendimiento."""
from app.core import metricas as nucleo
from app.db.models import MetricaHttp
from app.db.session import SessionLocal
from app.services import metricas as servicio

from .conftest import auth


def _filas():
    nucleo.volcar()
    db = SessionLocal()
    try:
        return db.query(MetricaHttp).order_by(MetricaHttp.id).all()
    finally:
        db.close()


def test_peticion_se_registra_con_ruta_plantilla_y_consultas(client, token_admin):
    nucleo.volcar()
    assert client.get("/api/usuarios/", headers=auth(token_admin)).status_code == 200
    filas = [f for f in _filas() if f.ruta.startswith("/api/usuarios")]
    assert filas, "no se registró la petición"
    fila = filas[-1]
    assert fila.origen == "servidor" and fila.metodo == "GET"
    assert fila.estado == 200
    assert fila.ms_total > 0
    assert fila.consultas >= 1
    assert 0 < fila.ms_db <= fila.ms_total


def test_ruta_con_id_se_agrupa_por_plantilla(client, token_admin):
    client.get("/api/productos/999999", headers=auth(token_admin))
    rutas = {f.ruta for f in _filas()}
    assert not any(r.endswith("/999999") for r in rutas)


def test_health_y_metricas_no_se_registran(client, token_admin):
    nucleo.volcar()
    client.get("/api/health")
    client.get("/api/metricas/resumen", headers=auth(token_admin))
    rutas = {f.ruta for f in _filas()}
    assert "/api/health" not in rutas
    assert not any(r.startswith("/api/metricas") for r in rutas)


def test_muestras_del_cliente_y_resumen(client, token_admin):
    resp = client.post(
        "/api/metricas/cliente",
        headers=auth(token_admin),
        json={
            "muestras": [
                {"metodo": "GET", "ruta": "/api/facturas/15/pagos", "estado": 200, "ms": 4200, "conexion": "4g"},
                {"metodo": "GET", "ruta": "/api/facturas/", "estado": 0, "ms": 30000},
            ]
        },
    )
    assert resp.status_code == 204, resp.text
    client.get("/api/usuarios/", headers=auth(token_admin))

    resp = client.get("/api/metricas/resumen?horas=1", headers=auth(token_admin))
    assert resp.status_code == 200, resp.text
    datos = resp.json()
    assert datos["servidor"]["n"] >= 1
    assert datos["cliente"]["n"] == 2 and datos["cliente"]["fallidas"] == 1
    assert datos["diagnostico"]
    assert any(r["ruta"].startswith("GET /api/usuarios") for r in datos["rutas"])


def test_resumen_pide_permiso_y_muestras_validan(client, token_cajero, token_admin):
    assert client.get("/api/metricas/resumen", headers=auth(token_cajero)).status_code == 403
    # Cualquier usuario con sesión puede enviar sus tiempos.
    ok = client.post(
        "/api/metricas/cliente",
        headers=auth(token_cajero),
        json={"muestras": [{"metodo": "GET", "ruta": "/api/x", "estado": 200, "ms": 10}]},
    )
    assert ok.status_code == 204
    malo = client.post(
        "/api/metricas/cliente",
        headers=auth(token_cajero),
        json={"muestras": [{"metodo": "GET", "ruta": "/api/x", "estado": 200, "ms": -5}]},
    )
    assert malo.status_code == 422
    assert client.post("/api/metricas/cliente", json={"muestras": []}).status_code == 401


def test_percentil_e_interpolacion():
    assert servicio.percentil([], 0.95) == 0.0
    assert servicio.percentil([5], 0.95) == 5.0
    assert servicio.percentil([10, 20, 30, 40], 0.5) == 25.0
    assert servicio.percentil(list(range(1, 101)), 0.95) == 95.0


def test_diagnostico_detecta_arranque_en_frio():
    class F:
        def __init__(self, **kw):
            self.ms_total = 5000.0
            self.ms_db = 100.0
            self.consultas = 3
            self.conexiones_nuevas = 0
            self.inactivo_s = 900.0
            self.primera_tras_arranque = False
            self.estado = 200
            self.__dict__.update(kw)

    notas = servicio._diagnostico([F(), F(), F(ms_total=100.0, inactivo_s=1.0)], [], [])
    assert any("arranque en frío" in n for n in notas)
