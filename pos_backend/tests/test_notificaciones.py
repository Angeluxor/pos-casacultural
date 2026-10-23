"""Pruebas del aviso de nuevos tickets por Telegram."""
import json
from urllib.parse import parse_qs

from app.db.session import SessionLocal
from app.services import notificaciones
from app.services.configuracion import (
    CLAVE_TELEGRAM_CHAT_ID,
    CLAVE_TELEGRAM_TOKEN,
    guardar_valor,
)

from .conftest import auth


class _RespuestaFalsa:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _crear(client, token, **cambios):
    datos = {
        "tipo": "Bug",
        "comentario": "La caja se queda cargando al guardar.",
        "contexto": {"ruta": "/ventas", "version": "1.0.0"},
    }
    datos.update(cambios)
    return client.post("/api/feedback/", headers=auth(token), json=datos)


def test_feedback_envia_aviso_telegram(client, token_cajero, monkeypatch):
    llamadas = []

    def fake_urlopen(peticion, timeout=None):
        llamadas.append((peticion, timeout))
        return _RespuestaFalsa({"ok": True})

    monkeypatch.setattr(notificaciones, "TELEGRAM_BOT_TOKEN", "token-prueba")
    monkeypatch.setattr(notificaciones, "TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setattr(notificaciones, "urlopen", fake_urlopen)

    respuesta = _crear(client, token_cajero)
    assert respuesta.status_code == 200, respuesta.text

    assert len(llamadas) == 1
    peticion, timeout = llamadas[0]
    assert peticion.full_url == (
        "https://api.telegram.org/bottoken-prueba/sendMessage"
    )
    assert timeout == 10.0
    datos = parse_qs(peticion.data.decode("utf-8"))
    assert datos["chat_id"] == ["12345"]
    texto = datos["text"][0]
    assert f"Nuevo ticket #{respuesta.json()['id']}" in texto
    assert "Tipo: Bug" in texto
    assert "Cajero" in texto
    assert "Ruta: /ventas" in texto
    assert "La caja se queda cargando" in texto
    assert "/feedback" in texto


def test_configuracion_en_bd_tiene_prioridad(client, token_cajero, monkeypatch):
    db = SessionLocal()
    try:
        guardar_valor(db, CLAVE_TELEGRAM_TOKEN, "token-db")
        guardar_valor(db, CLAVE_TELEGRAM_CHAT_ID, "999")
    finally:
        db.close()

    llamadas = []

    def fake_urlopen(peticion, timeout=None):
        llamadas.append(peticion)
        return _RespuestaFalsa({"ok": True})

    monkeypatch.setattr(notificaciones, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(notificaciones, "TELEGRAM_CHAT_ID", "")
    monkeypatch.setattr(notificaciones, "urlopen", fake_urlopen)

    respuesta = _crear(client, token_cajero)
    assert respuesta.status_code == 200, respuesta.text
    assert len(llamadas) == 1
    assert llamadas[0].full_url.endswith("/bottoken-db/sendMessage")
    datos = parse_qs(llamadas[0].data.decode("utf-8"))
    assert datos["chat_id"] == ["999"]


def test_sin_configuracion_no_intenta_enviar(client, token_cajero, monkeypatch):
    def fake_urlopen(*_args, **_kwargs):
        raise AssertionError("No debería llamarse a Telegram sin configuración")

    monkeypatch.setattr(notificaciones, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(notificaciones, "TELEGRAM_CHAT_ID", "")
    monkeypatch.setattr(notificaciones, "urlopen", fake_urlopen)

    respuesta = _crear(client, token_cajero)
    assert respuesta.status_code == 200, respuesta.text


def test_fallo_de_telegram_no_rompe_el_feedback(client, token_cajero, monkeypatch):
    def fake_urlopen(*_args, **_kwargs):
        raise OSError("sin red")

    monkeypatch.setattr(notificaciones, "TELEGRAM_BOT_TOKEN", "token-prueba")
    monkeypatch.setattr(notificaciones, "TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setattr(notificaciones, "urlopen", fake_urlopen)

    respuesta = _crear(client, token_cajero)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["comentario"].startswith("La caja")
