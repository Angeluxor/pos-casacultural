# POS Casa Cultural

Sistema de **punto de venta (POS)** web para Casa Cultural: gestión de inventario con kardex, facturación de ventas con pagos parciales, caja con apertura/cierre por turno, clientes y usuarios con roles. End-to-end: React, FastAPI y PostgreSQL.

## Características

- **Autenticación JWT** con roles **Admin** y **Cajero**; el username es insensible a mayúsculas.
- **Productos con kardex**: entrada por compra, salida por venta, devoluciones y ajustes, con saldo de stock histórico.
- **Ventas / facturas**: pago total o parcial, formas de pago (efectivo, transferencia, tarjeta, otro), anulación con motivo y trazabilidad (quién y cuándo), retiro de renglones sin borrar la traza.
- **Caja**: apertura y cierre de turno con saldo inicial, movimientos de entrada/salida y conciliación de saldo final.
- **Clientes**: documento (único), celular y correo.
- **Usuarios**: creación, edición, cambio de contraseña y eliminación (solo admin).
- **Dashboard** con métricas de ventas y filtro por rango de fechas.
- **Paginación** en todas las listas y **diseño responsive** (menú lateral deslizable en móvil, tablas y modales adaptados).
- Modo oscuro y mensajes reales de error del backend al validar el login.

## Stack

| Capa | Tecnología |
|------|------------|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 · PyJWT · bcrypt · psycopg2 |
| Frontend | React 19 · TypeScript · Vite 8 · React Router 7 · Oxlint |
| Base de datos | PostgreSQL (Neon serverless en producción) |
| Infraestructura | Docker Compose (local) · Render + Vercel (producción) |

## Arquitectura

```
Navegador
   │  HTTPS
   ▼
┌───────────────┐        ┌────────────────────┐        ┌───────────────┐
│  Vercel       │  CORS  │  Render (Docker)    │  SSL   │  Neon         │
│  React/Vite   │ ─────► │  FastAPI + uvicorn  │ ─────► │  PostgreSQL   │
│  (estático)   │        │  /api/*             │        │  (pooler)     │
└───────────────┘        └────────────────────┘        └───────────────┘
```

## Estructura del proyecto

```
WelcomeScreen/
├── pos_backend/          # API FastAPI (app, scripts, pruebas, Dockerfile)
├── frontend/             # SPA React + Vite (src, Dockerfile, nginx.conf)
├── docker-compose.yml    # Entorno local completo (db + backend + frontend)
├── render.yaml           # Blueprint de despliegue para Render
├── DEPLOY.md             # Guía de despliegue en la nube
├── RUN_LOCAL.md          # Cómo correr el MVP en local (Docker o manual)
├── empaquetar.ps1        # Genera pos-casacultural-mvp.zip
└── .env.example          # Variables para docker compose
```

El backend organiza su código en `pos_backend/app/`:

```
app/
├── main.py        # App FastAPI: CORS, tablas y routers
├── api/           # endpoints (auth, usuarios, clientes, caja, productos, facturas, dashboard)
├── core/          # config, security (JWT/bcrypt) y timezone (Colombia)
├── crud/          # operaciones de base de datos
├── db/            # models, session, migraciones aditivas
└── schemas/       # esquemas Pydantic
```

## Ponerlo en marcha

### En local (recomendado, un solo comando)

Requisito: **Docker Desktop**.

```bash
docker compose up --build
```

Abre **http://localhost:5173** y entra con `admin` / `admin123` (se crea automáticamente).

Guía completa con pasos, personalización y solución de problemas: [**RUN_LOCAL.md**](RUN_LOCAL.md).

### Sin Docker

Backend (desde `pos_backend/`):

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/pos"
python scripts\crear_admin.py
uvicorn app.main:app --reload --port 8000
```

Frontend (desde `frontend/`):

```powershell
npm install
# crea ".env.local" con:  VITE_API_URL=http://localhost:8000
npm run dev
```

### En la nube

Guía completa paso a paso (Neon + Render + Vercel): [**DEPLOY.md**](DEPLOY.md).

## Variables de entorno

### Backend (`pos_backend/.env.example`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `DATABASE_URL` | Sí | Cadena pooled de Neon / Postgres |
| `SECRET_KEY` | Sí | Firma de JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No (480) | Vigencia del token |
| `CORS_ORIGINS` | Sí | Dominios del frontend permitidos, separados por coma |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_NOMBRE` | No | Semilla del primer administrador |

### Frontend (`frontend/.env.example`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `VITE_API_URL` | Sí (build) | URL pública del backend, sin barra final |

> Los secretos reales (`.env.local`, `.neon`) **no** se versionan; están en `.gitignore`.

## Scripts útiles

| Script | Descripción |
|--------|-------------|
| `pos_backend/scripts/crear_admin.py` | Crea el primer administrador (idempotente) |
| `pos_backend/scripts/importar_excel.py` | Importa datos históricos desde el Excel maestro |
| `empaquetar.ps1` | Empaqueta `pos-casacultural-mvp.zip` para compartir |

## Roles y permisos

- **Admin**: acceso total (productos, ventas, caja, clientes, usuarios y dashboard).
- **Cajero**: opera caja y ventas; sin acceso a gestión de usuarios.

La API no tiene auto-registro: solo un Admin puede crear usuarios.