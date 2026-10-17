"""Pruebas unitarias de hashing de contraseñas y tokens JWT."""
import jwt
import pytest

from app.core import security


def test_hash_no_expone_la_clave_y_verifica():
    hashed = security.get_password_hash("claveSegura123")
    assert hashed != "claveSegura123"
    assert hashed.startswith("$2")  # bcrypt
    assert security.verify_password("claveSegura123", hashed)
    assert not security.verify_password("otraClave", hashed)


def test_verify_password_no_lanza_con_hash_invalido():
    assert security.verify_password("x", "no-es-un-hash") is False


def test_token_incluye_claims_de_seguridad():
    token = security.create_access_token("admin", token_version=3)
    payload = security.decode_access_token(token)
    assert payload["sub"] == "admin"
    assert payload["type"] == "access"
    assert payload["ver"] == 3
    for claim in ("jti", "iat", "exp"):
        assert claim in payload


def test_tokens_tienen_jti_unico():
    a = security.decode_access_token(security.create_access_token("admin"))
    b = security.decode_access_token(security.create_access_token("admin"))
    assert a["jti"] != b["jti"]


def test_token_expirado_es_rechazado():
    token = security.create_access_token("admin", expires_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_access_token(token)


def test_token_alterado_es_rechazado():
    token = security.create_access_token("admin")
    with pytest.raises(jwt.PyJWTError):
        security.decode_access_token(token + "manipulado")
