# Mejoras futuras — POS Casi Obsceno

Inventario de ideas y mejoras técnicas para las próximas iteraciones del MVP. Está ordenado por área y, dentro de lo posible, por prioridad.

---

## 1. Migraciones y esquema de base de datos

- **Alembic adoptado** ✅ para las migraciones: el esquema está versionado en `pos_backend/alembic/` (revisión base `0000_esquema_legado` + `0001_regularizacion`) y se aplica con `alembic upgrade head` al arrancar. Las bases creadas antes se marcan con `stamp 0000` y el `upgrade` repara las diferencias. Tras migrar se verifica que el esquema coincida con los modelos. Queda pendiente crear migraciones para cada cambio de modelo (en lugar de `create_all`).
- **Plan de datos de respaldo** (parcial ✅): respaldo/restauración portables con `pos_backend/scripts/respaldo_bd.py` y `pos_backend/scripts/restaurar_bd.py` (JSON con metadatos; el restaurador es simulacro por defecto y reajusta secuencias en Postgres) y **PITR de Neon** como capa primaria (configurar la ventana de retención en el panel). Queda pendiente **automatizar** la toma de respaldos (tarea programada / *trigger* de Neon) y agendar el simulacro de restauración.
- **Índices para consultas frecuentes**: por ejemplo, en `facturas.fecha`, `pagos.fecha`, `kardex.producto_id + fecha` y búsquedas con `ILIKE` en productos y clientes.

## 2. Seguridad / ciberseguridad

- **Panel con la postura actual**: la app usa SQLAlchemy ORM y consultas parametrizadas, lo que reduce el riesgo de **SQL Injection**, pero conviene:
  - Auditar que **no existan queries con cadenas concatenadas** (SQL crudo) en `app/crud/`.
  - **Validación estricta de entrada** con Pydantic (tipos, rangos, longitudes, formatos) y sanitización de salida (escapado de HTML en el frontend para evitar **XSS**).
- **Rate limiting en login y endpoints sensibles** (por IP y por usuario) para frenar fuerza bruta.
- **Cabeceras de seguridad**: `Content-Security-Policy`, `X-Frame-Options`, `Strict-Transport-Security`, `X-Content-Type-Options`, `Referrer-Policy` (equivalente a `helmet` en FastAPI, p. ej. `secure`/middleware propio). Seguir las buenas prácticas de la guía **OWASP Top 10**.
- **JWT más robusto**:
  - Tokens de acceso de corta duración + **refresh token** rotable.
  - **Revocación / lista negra** al cerrar sesión o al cambiar la contraseña.
  - Guardar la huella del token (jti) para expulsar sesiones.
- **Contraseñas**:
  - Subir las rondas de bcrypt o migrar a **Argon2id**.
  - Política de complejidad y rotación; **bloqueo temporal** tras varios intentos fallidos.
- **Gestión de secretos**: nunca versionar `.env.local`; centralizarlos (secrets del hosting, variables del panel) y rotarlos cada cierto tiempo. Revisar que `SECRET_KEY` de producción sea aleatoria y distinta a la de desarrollo.
- **Estadísticas de auditoría**: registrar quién crea/edita/elimina usuarios, quién anula facturas, aperturas y cierres de caja, con IP y rol.

## 3. Calidad y pruebas

- **Pruebas automatizadas**: unitarias del backend (pytest + TestClient) y del frontend (Vitest + Testing Library).
- **Pruebas end-to-end** del flujo crítico: abrir caja → vender → cobrar → cerrar caja → anular.
- **CI/CD**: correr lint, tipos y pruebas en cada push; análisis de seguridad de dependencias (`pip-audit`, `npm audit`, Dependabot).
- **Lint del frontend**: activar reglas type-aware de oxlint (`oxlint-tsgolint`) para atrapar bugs de tipos en build.

## 4. Funcionalidad de negocio

- **Reportes**: exportar ventas del día/periodo a **Excel/PDF**; cierre de caja imprimible.
- **Impresión de recibos**: formato A4 o **ticket térmico** (80 mm) por factura y por cierre.
- **Multisucursal**: sucursales con su propio stock y caja; reportes por sucursal.
- **Descuentos**: por producto, por factura y cupones.
- **Crédito a clientes**: topes por cliente y recordatorios de saldos.
- **Historial de clientes**: compras previas, frecuencia y saldo acumulado.
- **Devoluciones completas de facturas** además de la anulación con motivo.
- **Filtros avanzados en ventas**: por forma de pago, producto y vendedor, además del rango de fechas.
- **Auditoría de caja**: detalle de movimientos con su origen (venta, manual, pago parcial).
- **Cambio de contraseña obligatorio** en el primer ingreso del admin y para usuarios sin clave propia.

## 5. Experiencia de usuario

- **Alternar tema claro/oscuro manualmente** además de seguir al sistema.
- **Accesibilidad (a11y)**: contraste AA, navegación por teclado, foco visible y etiquetas ARIA.
- **Cambio de idioma** (español/inglés).
- **Notificaciones en tiempo real** cuando el stock de un producto baja del mínimo.
- **Rutas en la app encoladas/independientes**: una venta en curso no se pierde al navegar a otra pantalla.

## 6. Rendimiento y operación

- **Paginación por cursor (keyset)** en listas grandes en lugar de `OFFSET`.
- **Caché** de productos/busquedas frecuentes en el backend y de los datos estáticos del frontend.
- **Monitoreo**: logs estructurados, métricas (Prometheus) y alertas de errores 5xx.
- **Cold start de Render**: plan pago, o mantener activo con *pings*; versiones de Redis/caché compartida si crece la concurrencia.
- **Idempotencia en pagos**: evitar cobros duplicados si se reintenta una confirmación.

## 7. Infraestructura y despliegue

- **Separar entornos** (dev / staging / prod) con su propia base y variables.
- **Contenedores mínimos**: usar imágenes `python:3.12-slim` (o distroless) y fases `multi-stage` para el frontend.
- **Escaneo de imágenes** (Trivy / Snyk) en el pipeline.
- **TLS y expiración de certificados** automatizados; `HSTS` en el front.
- **Secrets del sidenote**: revisar que `empaquetar.ps1` no incluya `.env.local`, `.neon` ni credenciales al generar el ZIP para compartir.

---

## Criterio general

Para cada mejora conviene priorizar por: **riesgo/beneficio**, **esfuerzo** y **momento del negocio**. Como sugerencia de arranque:

1. Migraciones (Alembic) + respaldos. ✅ (respaldos: falta automatizar la ejecución — ver §1).
2. Rate limiting, cabeceras de seguridad y endurecimiento de contraseñas/JWT.
3. Pruebas automatizadas y CI/CD.
4. Reportes/impresión de recibos.
5. Multisucursal y crédito a clientes (si el negocio lo pide).

*Última actualización del documento: octubre 2026.*