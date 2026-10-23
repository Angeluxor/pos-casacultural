# POS Casi Obsceno

Sistema de **punto de venta (POS)** web para Casi Obsceno: gestión de inventario con kardex, facturación de ventas con pagos parciales, caja con apertura/cierre por turno, clientes y usuarios con roles. End-to-end: React, FastAPI y PostgreSQL.

> Novedades por versión: [CHANGELOG.md](CHANGELOG.md) · Roadmap: [MEJORAS_FUTURAS.md](MEJORAS_FUTURAS.md)

## Características

- **Autenticación JWT** con roles **Admin** y **Cajero**; el username es insensible a mayúsculas.
- **Productos con kardex**: entrada por compra, salida por venta, devoluciones y ajustes, con saldo de stock histórico.
- **Ventas / facturas**: pago total o parcial, formas de pago (efectivo, transferencia, tarjeta, otro), anulación con motivo y trazabilidad (quién y cuándo), retiro de renglones sin borrar la traza.
- **Caja**: apertura y cierre de turno con saldo inicial, movimientos de entrada/salida y conciliación de saldo final.
- **Modo offline (Fase 1)**: PWA instalable, sesión/catálogo/caja cacheados y cola local de ventas y cobros que se sincroniza al volver la red. El cierre de caja se bloquea si quedan operaciones pendientes.
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

## Modo offline

- La primera vez hay que abrir la app **con conexión** para instalar el service worker y guardar el catálogo y la caja activa.
- Sin red se pueden registrar ventas, cobros y **agregar ítems a una factura ya existente** si hay una caja abierta cacheada. Quedan en una cola local y se envían solos al recuperar la conexión; también se pueden reintentar desde el banner o desde Ventas.
- No se puede cerrar la caja hasta que la cola quede vacía.
- Cambiar cantidades, retirar productos o anular una factura requiere conexión. También requieren conexión los productos, clientes, apertura/cierre de caja, inventario, reportes y administración.
- Si una venta offline deja el stock negativo, se conserva y se marca **Revisar** en Ventas. Varios dispositivos offline pueden sobrevender; el inventario debe conciliarse manualmente.

## Estructura del proyecto

```
WelcomeScreen/
├── pos_backend/          # API FastAPI (app, scripts, pruebas, Dockerfile)
├── frontend/             # SPA React + Vite (src, Dockerfile, nginx.conf)
├── docker-compose.yml    # Entorno local completo (db + backend + frontend)
├── render.yaml           # Blueprint de despliegue para Render
├── DEPLOY.md             # Guía de despliegue en la nube
├── RUN_LOCAL.md          # Cómo correr el MVP en local (Docker o manual)
├── empaquetar.ps1        # Genera pos-casiobsceno-mvp.zip
└── .env.example          # Variables para docker compose
```

El backend organiza su código en `pos_backend/app/`:

```
app/
├── main.py        # App FastAPI: CORS, migraciones y routers
├── api/           # endpoints (auth, usuarios, clientes, caja, productos, facturas, dashboard)
├── core/          # config, security (JWT/bcrypt) y timezone (Colombia)
├── crud/          # operaciones de base de datos
├── db/            # models, session, inicialización de esquema (Alembic)
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
| `DATABASE_URL_UNPOOLED` | No | Cadena directa (sin pooler). Alembic la prefiere para migraciones/DDL |
| `SECRET_KEY` | Sí | Firma de JWT. En `production` debe ser propia y aleatoria (el arranque falla si se deja la de desarrollo) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No (480) | Vigencia del token |
| `ENVIRONMENT` | No (`development`) | `development` o `production` (activa HSTS y exige `SECRET_KEY`) |
| `CORS_ORIGINS` | Sí | Dominios del frontend permitidos, separados por coma |
| `BCRYPT_ROUNDS` | No (12) | Rondas de bcrypt |
| `PASSWORD_MIN_LENGTH` | No (8) | Longitud mínima de contraseñas |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_WINDOW_SECONDS` | No (10 / 60) | Rate limiting del login por IP |
| `GLOBAL_MAX_REQUESTS` / `GLOBAL_WINDOW_SECONDS` | No (600 / 60) | Tope global de peticiones por IP |
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
| `pos_backend/scripts/respaldo_bd.py` | Respalda la base de datos a un JSON portable |
| `pos_backend/scripts/restaurar_bd.py` | Restaura un respaldo (simulacro por defecto) |
| `empaquetar.ps1` | Empaqueta `pos-casiobsceno-mvp.zip` para compartir |

## Base de datos y migraciones (Alembic)

El esquema se versiona con **Alembic** (`pos_backend/alembic/`). Al arrancar, la app aplica `alembic upgrade head` automáticamente (`app/db/migraciones.py`), reutilizando el pool de conexiones; no hay que correr nada a mano en el despliegue.

```powershell
cd pos_backend
# aplicar migraciones (lo mismo que hace el arranque)
$env:DATABASE_URL = "postgresql://..."; .\venv\Scripts\python.exe -m alembic upgrade head
# crear una nueva revisión a partir de los cambios en los modelos
.\venv\Scripts\python.exe -m alembic revision --autogenerate -m "descripción del cambio"
# ver el estado actual
.\venv\Scripts\python.exe -m alembic current
```

- Alembic prefiere `DATABASE_URL_UNPOOLED` (cadena directa de Neon) y usa `DATABASE_URL` como respaldo.
- Las revisiones viven en `pos_backend/alembic/versions/`: `0000_esquema_legado` (base) y `0001_regularizacion` (añade `usuarios.token_version` y la FK `facturas.anulada_por_id`).
- **Bases creadas antes de Alembic** (tienen las tablas pero no `alembic_version`) se detectan y se marcan con `alembic stamp 0000` la primera vez, sin re-crear tablas; el `upgrade` siguiente repara las diferencias del esquema legado.
- Tras migrar, el arranque **verifica** que el esquema coincida con los modelos y falla con el detalle si hay diferencias (no arranca con la base a medias).

## Respaldos

Dos capas complementarias:

- **PITR de Neon** (primaria, recomendada): Neon guarda un historial que permite restaurar la base a un punto en el tiempo o crear una rama desde un instante (*instant restore*). Configura la ventana de retención en el panel de Neon. Guía: <https://neon.com/docs/introduction/branch-restore>.
- **Respaldo portable** (secundaria, versionable): `scripts/respaldo_bd.py` vuelca todas las tablas a un JSON con metadatos (fecha, revisión de Alembic y conteos) y `scripts/restaurar_bd.py` lo restaura respetando las claves foráneas.

```powershell
cd pos_backend
# Respaldo (solo lectura; usa DATABASE_URL_UNPOOLED/DATABASE_URL de .env.local)
.\venv\Scripts\python scripts\respaldo_bd.py
# -> respaldos/respaldo_<AAAAMMDD_HHMMSS>.json   (respaldos/ está en .gitignore)

# Restauración: simulacro primero (no escribe nada)
.\venv\Scripts\python scripts\restaurar_bd.py --archivo respaldos\respaldo_....json
# Restauración real en una base vacía
.\venv\Scripts\python scripts\restaurar_bd.py --archivo respaldos\respaldo_....json --confirmar
```

Notas:

- El restaurador es un **simulacro** por defecto; solo escribe con `--confirmar`. Si el destino ya tiene datos, se niega salvo `--force` (los reemplaza).
- En una base nueva, aplica primero las migraciones (`alembic upgrade head`) o usa `--crear-esquema`.
- En PostgreSQL reajusta las secuencias de los `id` tras restaurar.
- `respaldos/` está en `.gitignore`: no se versiona.
- **Prueba restauraciones periódicas**: corre el simulacro y una restauración real contra una base de prueba de vez en cuando para confirmar que los respaldos sirven.

## Pruebas y CI

Las pruebas del backend usan `pytest` sobre SQLite en memoria (no requieren Postgres):

```powershell
cd pos_backend
python -m venv venv; .\venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
```

El frontend se valida con lint, tipos, pruebas unitarias y build:

```bash
cd frontend
npm ci
npm run lint        # oxlint
npm run typecheck   # tsc -b
npm run test        # Vitest + Testing Library (jsdom)
npm run build
```

`.github/workflows/ci.yml` corre todo esto en cada push y pull request.

## Seguridad

- **JWT endurecido**: tokens con `jti`, `iat` y `type`; **revocación por versión** —al cambiar una contraseña se invalidan los tokens emitidos antes.
- **Contraseñas**: bcrypt con rondas configurables y longitud mínima.
- **Rate limiting**: límite por IP en el login y tope global de peticiones (en memoria; para varias instancias, migrar a Redis).
- **Cabeceras de seguridad**: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy`, `Permissions-Policy` y `HSTS` (en producción).

## Roles y permisos

- **Admin**: acceso total (productos, ventas, caja, clientes, usuarios y dashboard).
- **Cajero**: opera caja y ventas; sin acceso a gestión de usuarios.

La API no tiene auto-registro: solo un Admin puede crear usuarios.