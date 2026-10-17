# Probar el MVP en otro equipo (local, sin nube)

Todo el entorno (PostgreSQL + backend + frontend) corre con **Docker Compose**. Un solo comando levanta las tres piezas.

> Guía de despliegue en la nube: ver [`DEPLOY.md`](DEPLOY.md).

---

## Requisito único

- **Docker Desktop** (Windows / macOS) o **Docker Engine + Compose** (Linux).
  Descárgalo en <https://www.docker.com/products/docker-desktop/>. Ábrelo y asegúrate de que el motor esté corriendo.

No necesitas instalar Python, Node ni Postgres: van dentro de los contenedores.

---

## Pasos

1. **Descomprime** `pos-casiobsceno-mvp.zip` (o copia la carpeta del proyecto) en el otro equipo.
2. Abre una terminal **en la carpeta que contiene `docker-compose.yml`**.
3. Levanta todo:

   ```bash
   docker compose up --build
   ```

   La primera vez tarda unos minutos (descarga imágenes, compila el frontend e instala dependencias). Verás logs de los tres servicios.
4. Cuando el log del backend muestre que uvicorn está corriendo, abre:

   **http://localhost:5173**

5. Inicia sesión:

   | Usuario | Contraseña |
   |---------|------------|
   | `admin` | `admin123` |

   El usuario admin se crea **automáticamente** al arrancar el backend (`scripts/crear_admin.py`).

6. Para **detener**: `Ctrl + C` en la terminal, o en otra terminal:

   ```bash
   docker compose down          # detiene (los datos se conservan)
   docker compose down -v       # detiene y BORRA la base de datos local
   ```

---

## Servicios y puertos

| Servicio | URL / Puerto | Descripción |
|----------|--------------|-------------|
| Frontend | http://localhost:5173 | SPA servida por nginx |
| Backend (API) | http://localhost:8000 | FastAPI. Docs interactivas en `/docs` |
| Postgres | localhost:5432 | Usuario/clave/db: `pos` / `pos` / `pos_casacultural` |

Los datos de Postgres se guardan en el volumen `pgdata` y persisten entre reinicios.

---

## Personalizar (opcional)

Copia `.env.example` a `.env` en la raíz y ajusta, por ejemplo:

```env
ADMIN_PASSWORD=una-clave-mejor
POSTGRES_PASSWORD=otra-clave
VITE_API_URL=http://localhost:8000
```

Vuelve a ejecutar `docker compose up --build` para aplicar los cambios.

> Cambiar `VITE_API_URL` requiere **reconstruir** el frontend (por eso `--build`), ya que se incrusta en tiempo de compilación.

---

## Tras hacer cambios en el código

```bash
docker compose up --build
```

Reconstruye solo lo que cambió y reinicia los servicios.

---

## Problemas comunes

| Síntoma | Causa / solución |
|---------|------------------|
| "port is already allocated" | Algún puerto (5173/8000/5432) está ocupado. Ciérralo o cámbialo en `docker-compose.yml`. |
| El frontend carga pero dice "No se pudo conectar con el servidor" | El backend aún no terminó de arrancar, o `VITE_API_URL` no es `http://localhost:8000`. Revisa los logs. |
| Error de login | La base venía de un intento previo con otra contraseña. Arranca limpio con `docker compose down -v` y vuelve a subir. |
| Docker se queda sin memoria | En Docker Desktop → Settings → Resources, sube la memoria (mínimo ~4 GB). |
| Quiero ver los logs de un servicio | `docker compose logs -f backend` (o `db`, `frontend`). |

---

## Alternativa sin Docker

Si el equipo no puede instalar Docker, corre cada parte a mano (necesitas **Python 3.12+**, **Node 20+** y un **PostgreSQL** accesible).

**Backend** (desde `pos_backend/`):

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/pos"
$env:CORS_ORIGINS = "http://localhost:5173"
$env:ADMIN_PASSWORD = "admin123"

python scripts\crear_admin.py
uvicorn app.main:app --reload --port 8000
```

**Frontend** (desde `frontend/`):

```powershell
npm install
# crea ".env.local" con:  VITE_API_URL=http://localhost:8000
npm run dev
```

Abre http://localhost:5173.

---

## ¿Y cómo empaqueto el ZIP?

En la máquina de origen, desde la raíz del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File .\empaquetar.ps1
```

Genera `pos-casiobsceno-mvp.zip` sin entornos virtuales, `node_modules`, `dist`, cachés ni secretos (`.env.local`, `.neon`). Ese archivo es el que se comparte.
