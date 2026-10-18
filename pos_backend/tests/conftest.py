"""Configuración de las pruebas.

Las variables de entorno se definen ANTES de importar cualquier módulo de la
app, para que `app.db.session` cree el motor apuntando a una base SQLite
temporal en lugar de a PostgreSQL.
"""
import os
import tempfile
from pathlib import Path

_TMP_DB = Path(tempfile.gettempdir()) / "pos_backend_tests.db"

os.environ["ENVIRONMENT"] = "development"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef-para-pruebas"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"
os.environ["BCRYPT_ROUNDS"] = "4"  # hashing rápido en pruebas
os.environ["PASSWORD_MIN_LENGTH"] = "8"
os.environ["LOGIN_MAX_ATTEMPTS"] = "100000"  # no interferir con las pruebas
os.environ["GLOBAL_MAX_REQUESTS"] = "1000000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db.base_class import Base  # noqa: E402
from app.db.session import engine, SessionLocal  # noqa: E402
from app.db.models import Usuario, RolUsuario  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _preparar_bd():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    try:
        _TMP_DB.unlink()
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _bd_limpia(_preparar_bd):
    """Deja todas las tablas vacías antes de cada prueba."""
    db = SessionLocal()
    try:
        for tabla in reversed(Base.metadata.sorted_tables):
            db.execute(tabla.delete())
        db.commit()
    finally:
        db.close()
    yield


def _crear_usuario(username: str, password: str, rol: RolUsuario, activo: bool = True) -> int:
    db = SessionLocal()
    try:
        usuario = Usuario(
            username=username,
            nombre=username.capitalize(),
            hashed_password=get_password_hash(password),
            rol=rol,
            activo=activo,
            token_version=0,
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario.id
    finally:
        db.close()


@pytest.fixture
def client() -> TestClient:
    # Sin `with` para no disparar el lifespan (que aplicaría migraciones de Postgres).
    return TestClient(app)


@pytest.fixture
def admin_id() -> int:
    return _crear_usuario("admin", "admin123", RolUsuario.ADMIN)


@pytest.fixture
def cajero_id() -> int:
    return _crear_usuario("cajero", "cajero123", RolUsuario.CAJERO)


@pytest.fixture
def mesero_id() -> int:
    return _crear_usuario("mesero", "mesero123", RolUsuario.MESERO)


def login(client: TestClient, username: str, password: str) -> str:
    respuesta = client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["access_token"]


@pytest.fixture
def token_admin(client: TestClient, admin_id: int) -> str:
    return login(client, "admin", "admin123")


@pytest.fixture
def token_cajero(client: TestClient, cajero_id: int) -> str:
    return login(client, "cajero", "cajero123")


@pytest.fixture
def token_mesero(client: TestClient, mesero_id: int) -> str:
    return login(client, "mesero", "mesero123")


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
