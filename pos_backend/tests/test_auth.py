"""Pruebas de autenticación, autorización y revocación de tokens."""
from app.core.security import create_access_token
from app.db.models import RolUsuario

from .conftest import _crear_usuario, auth, login


def test_login_correcto(client, admin_id):
    resp = client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200
    cuerpo = resp.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["access_token"]


def test_login_password_incorrecta(client, admin_id):
    resp = client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "mala"},
    )
    assert resp.status_code == 401


def test_login_usuario_inexistente(client):
    resp = client.post(
        "/api/auth/login",
        data={"username": "nadie", "password": "x"},
    )
    assert resp.status_code == 401


def test_login_es_insensible_a_mayusculas(client, admin_id):
    resp = client.post(
        "/api/auth/login",
        data={"username": "ADMIN", "password": "admin123"},
    )
    assert resp.status_code == 200


def test_me_con_token(client, token_admin, admin_id):
    resp = client.get("/api/auth/me", headers=auth(token_admin))
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_me_sin_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_con_token_alterado(client, token_admin):
    resp = client.get("/api/auth/me", headers=auth(token_admin + "x"))
    assert resp.status_code == 401


def test_token_con_version_invalida_es_revocado(client, admin_id):
    # Un token con una versión distinta a la del usuario debe rechazarse.
    token = create_access_token("admin", token_version=99)
    resp = client.get("/api/auth/me", headers=auth(token))
    assert resp.status_code == 401


def test_usuario_inactivo_no_puede_iniciar_sesion(client):
    _crear_usuario("inactivo", "inactivo123", RolUsuario.CAJERO, activo=False)

    resp = client.post(
        "/api/auth/login",
        data={"username": "inactivo", "password": "inactivo123"},
    )

    assert resp.status_code == 403
    assert "inactivo" in resp.json()["detail"].lower()
    assert "access_token" not in resp.json()


def test_usuario_inactivo_no_puede_usar_la_api(client):
    _crear_usuario("inactivo", "inactivo123", RolUsuario.CAJERO, activo=False)
    # Aunque se emita un token por otra vía, la API rechaza al usuario inactivo.
    token = create_access_token("inactivo", token_version=0)
    resp = client.get("/api/auth/me", headers=auth(token))
    assert resp.status_code == 400
    assert "inactivo" in resp.json()["detail"].lower()


def test_cajero_no_puede_listar_usuarios(client, token_cajero):
    resp = client.get("/api/usuarios/", headers=auth(token_cajero))
    assert resp.status_code == 403


def test_admin_puede_listar_usuarios(client, token_admin):
    resp = client.get("/api/usuarios/", headers=auth(token_admin))
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_cambio_de_password_revoca_tokens_anteriores(client, token_admin):
    resp = client.put(
        "/api/auth/me/password",
        headers=auth(token_admin),
        json={"password_actual": "admin123", "password_nueva": "nuevaClave123"},
    )
    assert resp.status_code == 204
    # El token emitido antes del cambio ya no debe servir.
    assert client.get("/api/auth/me", headers=auth(token_admin)).status_code == 401
    # Con la nueva contraseña sí se puede entrar.
    assert login(client, "admin", "nuevaClave123")


def test_cambio_de_password_exige_minimo(client, token_admin):
    resp = client.put(
        "/api/auth/me/password",
        headers=auth(token_admin),
        json={"password_actual": "admin123", "password_nueva": "corta"},
    )
    assert resp.status_code == 400


def test_cambio_de_password_valida_la_actual(client, token_admin):
    resp = client.put(
        "/api/auth/me/password",
        headers=auth(token_admin),
        json={"password_actual": "incorrecta", "password_nueva": "nuevaClave123"},
    )
    assert resp.status_code == 400
