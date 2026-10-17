# Imagen base de Python 3.12 (slim) para el backend FastAPI del POS Casi Obsceno
FROM python:3.12-slim

# Salida de logs sin buffer y sin .pyc (mejor para contenedores)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# curl se usa para el HEALTHCHECK
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias primero (mejor cache de capas)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar el código de la aplicación
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/" || exit 1

# Al arrancar: asegura el admin inicial (idempotente) y levanta uvicorn.
# Render (y otros PaaS) inyectan el puerto en $PORT.
CMD ["sh", "-c", "python scripts/crear_admin.py && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
