from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.migraciones import inicializar_esquema
from app.core.config import CORS_ORIGINS, validar_configuracion
from app.core.rate_limit import RateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware

# Registrar los modelos en Base.metadata (efecto de importación).
from app.db import models  # noqa: F401

# Importar routers
from app.api.endpoints import auth, balance, caja, usuario, producto, factura, cliente, dashboard, reportes, ingreso, permiso, proveedor, costos, feedback


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Valida variables sensibles (SECRET_KEY, etc.) al arrancar.
    validar_configuracion()
    # Deja el esquema al día con Alembic (crea/actualiza tablas si hace falta).
    inicializar_esquema()
    yield


app = FastAPI(
    title="POS Casi Obsceno API",
    description="Backend para el Punto de Venta de Casi Obsceno",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS para el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cabeceras de seguridad (nosniff, X-Frame-Options, HSTS, CSP, ...).
app.add_middleware(SecurityHeadersMiddleware)
# Tope global de peticiones por IP (el login tiene además su propio límite).
app.add_middleware(RateLimitMiddleware)

# Incluir rutas de la API
app.include_router(auth.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(usuario.router, prefix="/api/usuarios", tags=["Usuarios"])
app.include_router(cliente.router, prefix="/api/clientes", tags=["Clientes"])
app.include_router(caja.router, prefix="/api/caja", tags=["Caja"])
app.include_router(producto.router, prefix="/api/productos", tags=["Productos y Kardex"])
app.include_router(ingreso.router, prefix="/api/ingresos", tags=["Ingresos de inventario"])
app.include_router(proveedor.router, prefix="/api/proveedores", tags=["Proveedores"])
app.include_router(costos.router, prefix="/api/costos", tags=["Costos y recetas"])
app.include_router(factura.router, prefix="/api/facturas", tags=["Facturas y Ventas"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(reportes.router, prefix="/api/reportes", tags=["Reportes"])
app.include_router(balance.router, prefix="/api/balance", tags=["Balance"])
app.include_router(permiso.router, prefix="/api/permisos", tags=["Permisos"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["Feedback"])


@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API del POS Casi Obsceno"}


@app.get("/api/health", tags=["Salud"])
def health():
    """Sonda de salud para el hosting (Render) y para CI."""
    return {"status": "ok"}
