from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.base_class import Base
from app.db.session import engine
from app.core.config import CORS_ORIGINS

# Importar modelos para que SQLAlchemy los reconozca al crear las tablas
from app.db.models import *

# Importar routers
from app.api.endpoints import auth, caja, usuario, producto, factura, cliente, dashboard

# Crear tablas en la base de datos (En producción usar Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="POS Casa Cultural API",
    description="Backend para el Punto de Venta de Casa Cultural",
    version="1.0.0"
)

# CORS para el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rutas de la API
app.include_router(auth.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(usuario.router, prefix="/api/usuarios", tags=["Usuarios"])
app.include_router(cliente.router, prefix="/api/clientes", tags=["Clientes"])
app.include_router(caja.router, prefix="/api/caja", tags=["Caja"])
app.include_router(producto.router, prefix="/api/productos", tags=["Productos y Kardex"])
app.include_router(factura.router, prefix="/api/facturas", tags=["Facturas y Ventas"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])

@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API del POS Casa Cultural"}
