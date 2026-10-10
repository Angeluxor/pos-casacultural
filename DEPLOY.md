# Guía de despliegue del MVP — POS Casa Cultural

Stack: **FastAPI + SQLAlchemy** (backend) · **React + Vite** (frontend) · **PostgreSQL en Neon** (base de datos).

Hosting recomendado, todo con capa gratuita:

| Capa | Servicio | Notas |
|------|----------|-------|
| Base de datos | **Neon** | Serverless Postgres. Ya integrado vía `DATABASE_URL`. |
| Backend (API) | **Render** (Docker) | Free: se duerme a los ~15 min sin tráfico (cold start ~30-60 s). |
| Frontend (SPA) | **Vercel** | Estático, siempre encendido. |

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

---

## 0. Requisitos previos

- Cuenta en [GitHub](https://github.com), [Render](https://render.com), [Vercel](https://vercel.com) y [Neon](https://neon.tech).
- El proyecto subido a un repositorio de GitHub (paso 1).
- `git` instalado.

---

## 1. Subir el proyecto a GitHub

En la raíz del proyecto (`WelcomeScreen/`) ya existen los `.gitignore` que evitan subir `venv/`, `.env.local`, `.neon`, `node_modules/`, etc.

```powershell
git init
git add .
git commit -m "MVP POS Casa Cultural listo para desplegar"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

> Verifica antes con `git status` que **no** aparezcan `pos_backend/.env.local` ni `.neon`.

---

## 2. Base de datos en Neon

1. Crea un proyecto en Neon y una base de datos (por defecto `neondb`).
2. En **Dashboard → Connection Details** copia **ambas** cadenas:
   - **Pooled connection** → será tu `DATABASE_URL` (la usa la app).
   - **Direct connection** (sin `-pooler`) → `DATABASE_URL_UNPOOLED` (solo migraciones/scripts).
3. Deben verse así (nota el `?sslmode=require`):

   ```
   postgresql://USUARIO:CLAVE@ep-xxxx-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```

> Las tablas **se crean solas** al arrancar el backend (`Base.metadata.create_all` en `app/main.py:14`). No necesitas Alembic para el MVP.

---

## 3. Backend en Render

El repo ya trae `render.yaml` (Blueprint) y `pos_backend/Dockerfile`.

1. Render → **New + → Blueprint** → conecta el repositorio.
2. Detecta `render.yaml` y crea el servicio `pos-casacultural-api`.
3. Rellena las variables que piden (**sync: false**):

   | Variable | Valor |
   |----------|-------|
   | `DATABASE_URL` | Cadena **pooled** de Neon |
   | `CORS_ORIGINS` | `http://localhost:5173` por ahora (se completa en el paso 5) |
   | `ADMIN_PASSWORD` | Una contraseña segura para el primer admin |

   `SECRET_KEY` se genera automáticamente; `ACCESS_TOKEN_EXPIRE_MINUTES` = `480`; `ADMIN_USERNAME` = `admin`.

4. **Create**. Render construye la imagen Docker y arranca.
5. Cuando termine, prueba:

   ```powershell
   curl https://pos-casacultural-api.onrender.com/
   # {"message":"Bienvenido a la API del POS Casa Cultural"}
   ```

**¿Cómo se crea el primer administrador?**
Al iniciar el contenedor se ejecuta `scripts/crear_admin.py` (idempotente): si no existe el usuario `admin`, lo crea con `ADMIN_USERNAME`/`ADMIN_PASSWORD` y rol **Admin**. La API **no tiene auto-registro** (solo un Admin puede crear usuarios), por eso este paso es obligatorio.

> Si prefieres hacerlo manual, en Render → servicio → **Shell**:
> ```bash
> python scripts/crear_admin.py
> ```

---

## 4. Frontend en Vercel

1. Vercel → **Add New… → Project** → importa el repositorio.
2. **Root Directory**: `frontend`.
3. Framework: **Vite** (autodetectado). `vercel.json` ya define el build y los *rewrites* SPA (necesarios porque la app usa `BrowserRouter`).
4. **Environment Variables** → agrega:

   | Nombre | Valor |
   |--------|-------|
   | `VITE_API_URL` | `https://pos-casacultural-api.onrender.com` (sin barra final) |

5. **Deploy**. Obtendrás una URL tipo `https://tu-proyecto.vercel.app`.

> `VITE_API_URL` se incrusta en **tiempo de build**. Si la cambias, hay que **redeployar**.

---

## 5. Cerrar el CORS (conectar frontend ↔ backend)

1. Copia el dominio de Vercel (ej. `https://tu-proyecto.vercel.app`).
2. En Render → servicio → **Environment** → edita `CORS_ORIGINS`:

   ```
   http://localhost:5173,http://127.0.0.1:5173,https://tu-proyecto.vercel.app
   ```

3. Guarda → Render redepliega solo. `app/core/config.py:11` lee esta variable.

---

## 6. Verificación (smoke test)

1. Abre `https://tu-proyecto.vercel.app`.
2. Inicia sesión con `admin` / la contraseña que definiste (`ADMIN_PASSWORD`).
3. **Cambia la contraseña** en *Mi perfil*.
4. Prueba el flujo completo: crear producto → crear cliente → **abrir caja** → registrar venta → cobrar → cerrar caja.
5. Si el backend estaba dormido, el primer request puede tardar ~30-60 s (free tier de Render).

---

## 7. Actualizaciones (deploy continuo)

- **Backend**: `git push` a `main` → Render reconstruye y redepliega (por `autoDeploy: true`).
- **Frontend**: `git push` a `main` → Vercel redepliega.
- Nunca edites variables de producción en archivos versionados; usa el panel del hosting.

---

## 8. (Opcional) Cargar los datos históricos del Excel

El maestro está en `pos_backend/data/Sistema_Ventas_CasaCultural_MASTER.xlsx` y el importador en `pos_backend/scripts/importar_excel.py`.

⚠️ **El importador también crea un usuario `admin`/`admin123`.** Úsalo en una base **vacía**; si ya sembraste el admin con el paso 3, cámbiale el nombre en el script o usa otra base.

Puedes ejecutarlo desde tu máquina apuntando a Neon (usa la cadena **unpooled** de forma temporal):

```powershell
cd pos_backend
$env:DATABASE_URL = "postgresql://...@ep-xxxx.us-east-1.aws.neon.tech/neondb?sslmode=require"
$env:PYTHONPATH = "."
.\venv\Scripts\python scripts\importar_excel.py
```

---

## 9. Alternativas de hosting

| Capa | Alternativas | Comentario |
|------|--------------|------------|
| Backend | **Railway**, **Fly.io**, **Koyeb** | El `Dockerfile` funciona tal cual. |
| Frontend | **Netlify**, **Cloudflare Pages** | Mismos *rewrites* a `/index.html`. |
| DB | **Supabase**, **Railway Postgres** | Ajusta `DATABASE_URL` con `sslmode=require`. |

En Netlify, crea `frontend/netlify.toml`:

```toml
[build]
  command = "npm run build"
  publish = "dist"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

---

## 10. Checklist de producción

- [ ] `SECRET_KEY` aleatoria y secreta (no el default `dev-secret-change-me`).
- [ ] `ADMIN_PASSWORD` fuerte y **cambiada** tras el primer login.
- [ ] `CORS_ORIGINS` con **solo** los dominios reales del frontend.
- [ ] `DATABASE_URL` es la **pooled**; el `.env.local`/`.neon` no están en el repo.
- [ ] HTTPS en ambos servicios (Render y Vercel lo dan gratis).
- [ ] Backend free tier: acepta el *cold start* o sube a un plan pago si molesta.

---

## 11. Solución de problemas

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| Login falla con 401 | No se sembró el admin | Revisa logs de arranque de Render o corre `python scripts/crear_admin.py` en el Shell |
| Frontend: "No se pudo conectar con el servidor" | `VITE_API_URL` vacía o CORS mal | Revisa la env var en Vercel (y redeploy) y `CORS_ORIGINS` en Render |
| 500 al arrancar el backend | `DATABASE_URL` inválida o sin `sslmode=require` | Corrobora la cadena pooled de Neon; revisa `import psycopg2` |
| Rutas del frontend dan 404 al recargar | Faltan los *rewrites* SPA | Verifica `frontend/vercel.json` (`BrowserRouter` requiere fallback a `index.html`) |
| Todo lento el primer request | Free tier de Render dormido | Esperado; sube de plan para evitarlo |

---

## 12. Variables de entorno (referencia)

**Backend** (`pos_backend/.env.example`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `DATABASE_URL` | Sí | Cadena pooled de Neon |
| `SECRET_KEY` | Sí | Firma de JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No (480) | Vigencia del token |
| `CORS_ORIGINS` | Sí | Dominios del frontend, separados por coma |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_NOMBRE` | No | Semilla del primer admin |

**Frontend** (`frontend/.env.example`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `VITE_API_URL` | Sí (build) | URL pública del backend, sin barra final |
