"""Pruebas de la validación de configuración y utilidades."""
import pytest

from app.core import config


def test_produccion_exige_secret_key_propia(monkeypatch):
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setattr(config, "SECRET_KEY", config._DEFAULT_SECRET)
    with pytest.raises(RuntimeError):
        config.validar_configuracion()


def test_produccion_con_secret_key_propia_no_falla(monkeypatch):
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setattr(config, "SECRET_KEY", "x" * 64)
    config.validar_configuracion()


def test_generar_secret_key_es_larga():
    assert len(config.generar_secret_key()) >= 32
