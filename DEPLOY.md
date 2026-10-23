# Guía de despliegue del MVP — POS Casi Obsceno

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
git commit -m "MVP POS Casi Obsceno listo para desplegar"
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

> El esquema se versiona con **Alembic** y **se aplica solo al arrancar** el backend (`alembic upgrade head` en `app/db/migraciones.py`). No necesitas correr nada a mano. Si tu base ya existía de antes de Alembic (tiene las tablas pero no `alembic_version`), la app la detecta y la marca con `stamp` la primera vez.

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
   # {"message":"Bienvenido a la API del POS Casi Obsceno"}
   ```

**¿Cómo se crea el primer administrador?**
Al iniciar el contenedor se ejecuta `scripts/crear_admin.py` (idempotente): si no existe el usuario `admin`, lo crea con `ADMIN_USERNAME`/`ADMIN_PASSWORD` y rol **Admin**. La API **no tiene auto-registro** (solo un Admin puede crear usuarios), por eso este paso es obligatorio.

> Si prefieres hacerlo manual, en Render → servicio → **Shell**:
> ```bash
> python scripts/crear_admin.py
> ```

### Avisos de feedback por Telegram (opcional)

Cuando alguien envía un ticket desde la app, el backend puede avisar por
Telegram con el tipo, el autor, la ruta y el comentario. Es opcional: si las
variables no están configuradas, el feedback se guarda igual.

1. En Telegram, habla con **@BotFather**, envía `/newbot` y guarda el **token**.
2. Envía cualquier mensaje al bot que acabas de crear.
3. Consulta el chat ID:

   ```text
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

   Busca `message.chat.id` en la respuesta. También puedes usar **@userinfobot**.
4. En Render → servicio → **Environment**, agrega:

   | Variable | Valor |
   |----------|-------|
   | `TELEGRAM_BOT_TOKEN` | Token de BotFather |
   | `TELEGRAM_CHAT_ID` | Chat ID del usuario o grupo que recibirá los avisos |
   | `FRONTEND_URL` | `https://pos-casacultural.vercel.app` (para el enlace «Ver bandeja») |

5. Guarda; Render redepliega. Crea un ticket de prueba y debería llegar el mensaje.

> Si usas un grupo, agrega el bot al grupo, envía un mensaje allí y usa el chat ID
> del grupo (suele empezar con `-`). Nunca pongas el token en el frontend ni en el
> repositorio.

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
>
> Los **previews de Vercel** usan el proxy `/api` definido en `frontend/vercel.json`, que
> reenvía al backend de producción. Así el navegador no hace una petición cross-origin:
> no hace falta configurar `VITE_API_URL` en Preview ni agregar cada URL de preview a
> `CORS_ORIGINS`.

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

El maestro está en `pos_backend/data/Sistema_Ventas_MASTER.xlsx` y el importador en `pos_backend/scripts/importar_excel.py`.

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
- [ ] Respaldo inicial tomado y PITR de Neon configurado (ver **12. Respaldos**).

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

## 12. Respaldos

Hay dos capas complementarias:

1. **PITR de Neon** (primaria): Neon conserva un historial que permite restaurar la base a un instante pasado (*instant restore*) o crear una rama desde ese punto. Es la forma más rápida de recuperarse de un borrado accidental. Configura la ventana de retención en **Neon → Project → Settings** y revisa <https://neon.com/docs/introduction/branch-restore>.
2. **Respaldo portable** (secundaria, exportable): `scripts/respaldo_bd.py` vuelca todas las tablas a un JSON y `scripts/restaurar_bd.py` lo restaura respetando las claves foráneas. Sirve como copia fuera de Neon y para migrar de proveedor.

```powershell
cd pos_backend
# Respaldo (solo lectura; usa la cadena de .env.local)
.\venv\Scripts\python scripts\respaldo_bd.py
# -> respaldos\respaldo_<AAAAMMDD_HHMMSS>.json

# Restauración: primero el simulacro (no escribe nada)
.\venv\Scripts\python scripts\restaurar_bd.py --archivo respaldos\respaldo_....json
# Restauración real (base vacía) o reemplazando datos con --force
.\venv\Scripts\python scripts\restaurar_bd.py --archivo respaldos\respaldo_....json --confirmar
```

Recomendaciones:

- Guarda los respaldos **fuera del repositorio** (almacenamiento externo); `respaldos/` está en `.gitignore`.
- Programa el respaldo (Tarea programada de Windows, cron en un servidor o un *trigger* de Neon) y **prueba la restauración** de vez en cuando contra una base de prueba.
- Nunca subas el JSON de respaldo a un repositorio: contiene datos personales de clientes.

---

## 13. Variables de entorno (referencia)

**Backend** (`pos_backend/.env.example`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `DATABASE_URL` | Sí | Cadena pooled de Neon |
| `DATABASE_URL_UNPOOLED` | No | Cadena directa de Neon; Alembic la prefiere para migraciones |
| `SECRET_KEY` | Sí | Firma de JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No (480) | Vigencia del token |
| `CORS_ORIGINS` | Sí | Dominios del frontend, separados por coma |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_NOMBRE` | No | Semilla del primer admin |

**Frontend** (`frontend/.env.example`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `VITE_API_URL` | Sí (build) | URL pública del backend, sin barra final |
