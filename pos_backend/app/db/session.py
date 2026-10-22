import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Cargar variables de entorno desde .env.local
load_dotenv(".env.local")
load_dotenv(".env")

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/pos_casacultural"

_ES_SQLITE = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

# Neon requiere en algunos casos sslmode=require o pre_ping.
# connect_timeout evita que una conexión caída deje la petición esperando
# indefinidamente cuando el host no responde.
_opciones_engine = {"pool_pre_ping": True}
if not _ES_SQLITE:
    _opciones_engine.update(
        {
            "pool_recycle": 300,
            "connect_args": {"connect_timeout": 10},
        }
    )

engine = create_engine(SQLALCHEMY_DATABASE_URL, **_opciones_engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

if not _ES_SQLITE:
    # En PostgreSQL (Neon) ponemos topes del lado del servidor. Sin esto, una
    # fila bloqueada por otra transacción puede dejar la venta "cargando"
    # durante minutos. El statement_timeout es amplio para no cortar reportes;
    # el lock_timeout y el idle_in_transaction son los que evitan cuelgues.
    @event.listens_for(engine, "connect")
    def _configurar_timeouts(dbapi_connection, _connection_record):
        with dbapi_connection.cursor() as cursor:
            cursor.execute(
                "SET statement_timeout = '120000ms'; "
                "SET lock_timeout = '10000ms'; "
                "SET idle_in_transaction_session_timeout = '60000ms'"
            )
        dbapi_connection.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

