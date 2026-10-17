"""Crea el usuario administrador inicial de forma idempotente.

La API NO tiene auto-registro: solo un Admin puede crear usuarios, así que en
una base de datos nueva hay que sembrar el primer administrador.

Se ejecuta automáticamente al iniciar el contenedor (ver Dockerfile) y también
puede correrse manualmente desde pos_backend/:

    $env:PYTHONPATH = "."; .\\venv\\Scripts\\python scripts\\crear_admin.py

Variables de entorno opcionales:
    ADMIN_USERNAME  (por defecto: admin)
    ADMIN_PASSWORD  (por defecto: admin123)  -> cámbiala en producción
    ADMIN_NOMBRE    (por defecto: Administrador)
"""
import os
import sys
from pathlib import Path

# Permite `python scripts/crear_admin.py` sin depender de PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.db.migraciones import inicializar_esquema
from app.db.models import Usuario, RolUsuario
from app.core.security import get_password_hash


def main() -> None:
    # Garantiza que el esquema exista/esté al día antes de insertar.
    inicializar_esquema()

    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    nombre = os.getenv("ADMIN_NOMBRE", "Administrador")

    db = SessionLocal()
    try:
        existente = db.query(Usuario).filter(Usuario.username == username).first()
        if existente:
            print(f"[crear_admin] El usuario '{username}' ya existe (id={existente.id}). Nada que hacer.")
            return

        admin = Usuario(
            username=username,
            nombre=nombre,
            hashed_password=get_password_hash(password),
            rol=RolUsuario.ADMIN,
            activo=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(f"[crear_admin] Usuario administrador '{username}' creado (id={admin.id}).")
        if password == "admin123":
            print("[crear_admin] ADVERTENCIA: usas la contraseña por defecto. Cámbiala cuanto antes.")
    except Exception as exc:  # noqa: BLE001 - queremos ver el motivo y salir con error
        db.rollback()
        print(f"[crear_admin] ERROR al crear el administrador: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
