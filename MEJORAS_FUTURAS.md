# Roadmap y mejoras futuras — POS Casi Obsceno

Estado actual: **1.0.0** (2026-10-20). El detalle de lo entregado está en
[`CHANGELOG.md`](CHANGELOG.md).

Leyenda:

- ✅ Implementado y en producción.
- 🟡 Implementado parcialmente; queda una parte concreta.
- ⬜ Pendiente.

---

## Estado actual

### Completado en 1.0.0

- Operación completa de ventas, caja, inventario, clientes, proveedores,
  costos, balance, nómina, reportes y feedback.
- Dashboard con ventas diarias/semanales/mensuales, caja disponible, cartera y
  stock bajo.
- Caja separada en efectivo y banco, con categorías, filtros, resumen, historial
  de turnos y cierre con crédito del turno.
- Bolsillos de gastos vitales que reducen la caja disponible sin alterar el
  total de activos ni la utilidad.
- Balance general con activos, pasivos, patrimonio, resultados, inventario,
  cuentas por pagar y exportación.
- Costos y recetas, proveedores, ingresos de inventario y compras a crédito.
- Permisos configurables por rol (Admin, Cajero y Mesero) y menús/rutas/botones
  adaptados.
- Feedback con captura de pantalla, contexto técnico y bandeja de gestión.
- Identidad visual collage, versión visible y ayuda contextual en todas las
  pantallas.
- Alembic hasta la revisión `0015`, respaldos portables, pruebas y CI.
- Reimportación de producción desde el maestro v2, preservando usuarios y
  permisos.

### Próximos focos recomendados

1. Automatizar respaldos y hacer un simulacro de restauración programado.
2. Completar seguridad: refresh tokens, auditoría de acciones y cambio de
   contraseña obligatorio en el primer ingreso.
3. Impresión de recibos y cierre de caja en formato ticket/A4.
4. Separar staging de producción y añadir monitoreo/alertas.
5. Historial de clientes y límites de crédito; después multisucursal y
   descuentos.

---

## 1. Migraciones y esquema de base de datos

- ✅ **Alembic adoptado y al día**: revisiones `0000` a `0015`, aplicación
  automática con `alembic upgrade head` al arrancar, `stamp 0000` para bases
  legadas y verificación del esquema contra los modelos. La regla vigente es
  crear una migración por cada cambio de modelo.
- ✅ **Respaldos portables y PITR**: `scripts/respaldo_bd.py` y
  `scripts/restaurar_bd.py` (simulacro por defecto, `--confirmar`, `--force`,
  reajuste de secuencias). Se usaron antes de la reimportación de producción.
  Neon aporta PITR como capa primaria.
- ⬜ **Automatizar respaldos**: tarea programada o trigger de Neon, con retención
  definida y alerta si falla.
- ⬜ **Simulacro de restauración programado**: restaurar periódicamente en una
  base de prueba y registrar el resultado.
- ⬜ **Índices para consultas frecuentes**: `facturas.fecha`, `pagos.fecha`,
  `kardex(producto_id, fecha)` y búsquedas `ILIKE` de productos/clientes.
- ⬜ **Revisar crecimiento de tablas históricas**: pagos, kardex y caja a medida
  que crezca el volumen.

---

## 2. Seguridad / ciberseguridad

- ✅ **Base de datos**: SQLAlchemy ORM y consultas parametrizadas; validación de
  entrada con Pydantic y escapado de salida por React.
- ✅ **Rate limiting**: límite específico en login y tope global por IP.
- ✅ **Cabeceras de seguridad**: CSP, `X-Frame-Options`, HSTS,
  `X-Content-Type-Options` y `Referrer-Policy`.
- 🟡 **JWT**: token de acceso con `token_version` para revocar sesiones al
  cambiar contraseña. Queda pendiente:
  - Access token de corta duración + refresh token rotable.
  - Lista negra/`jti` para cierre de sesión explícito.
  - Expulsar sesiones por usuario desde administración.
- 🟡 **Contraseñas**: bcrypt con rondas configurables (12 por defecto), longitud
  mínima y cambio desde el perfil. Queda pendiente:
  - Evaluar Argon2id.
  - Política de complejidad y rotación.
  - Bloqueo temporal tras intentos fallidos.
- 🟡 **Secretos**: `.env.local` y `.neon` no se versionan; producción exige
  `SECRET_KEY` propia; el ZIP excluye secretos. Queda pendiente rotación
  periódica y centralización en el hosting.
- ⬜ **Auditoría de acciones**: quién crea/edita/elimina usuarios, anula
  facturas, abre/cierra caja y registra movimientos, con IP y rol.
- ⬜ **Auditoría formal de SQL crudo** en `app/crud/` y revisión OWASP Top 10.
- ⬜ **Protección de capturas de feedback**: revisar retención, acceso y
  eliminación de imágenes con datos personales.

---

## 3. Calidad y pruebas

- ✅ **Pruebas automatizadas**: 151 pruebas de backend (pytest + TestClient) y
  45 de frontend (Vitest + Testing Library).
- 🟡 **E2E**: hay flujo de login, navegación protegida y cierre de sesión. Queda
  pendiente el flujo crítico completo: abrir caja → vender → cobrar → cerrar
  caja → anular.
- ✅ **CI/CD**: GitHub Actions ejecuta backend, frontend, lint, typecheck,
  pruebas y build en cada push/PR.
- ⬜ **Análisis de dependencias**: `pip-audit`, `npm audit` y Dependabot.
- ⬜ **Lint type-aware** de oxlint (`oxlint-tsgolint`) para detectar bugs de
  tipos en build.
- ⬜ **Cobertura**: medir cobertura y fijar umbrales para módulos críticos
  (facturación, caja, balance, nómina).
- ⬜ **Pruebas de carga** en dashboard, reportes y cierre de caja.

---

## 4. Funcionalidad de negocio

- ✅ **Reportes**: ventas, más vendidos, cartera, cierres de caja, inventario y
  nómina, con filtros y exportación a Excel/PDF.
- ✅ **Auditoría de caja**: movimientos con categoría, origen/referencia, forma
  de pago, filtros, resumen e historial de turnos.
- ✅ **Crédito a clientes**: facturas a crédito, cartera, abonos y descuentos de
  nómina.
- 🟡 **Historial de clientes**: existen clientes, cartera y nómina vinculada;
  falta una vista dedicada de compras previas, frecuencia y saldo acumulado.
- 🟡 **Filtros avanzados en ventas**: hay fechas, estado, búsqueda y
  ordenamiento; faltan forma de pago, producto y vendedor.
- ⬜ **Impresión de recibos**: factura y cierre de caja en A4 y ticket térmico de
  80 mm.
- ⬜ **Multisucursal**: stock, caja y reportes por sucursal.
- ⬜ **Descuentos**: por producto, por factura y cupones.
- ⬜ **Límites de crédito y recordatorios de saldo** por cliente.
- ⬜ **Devoluciones completas de facturas** además de la anulación con motivo.
- ⬜ **Cambio de contraseña obligatorio** en el primer ingreso del admin y para
  usuarios con clave temporal.
- ⬜ **Facturación electrónica / integración contable**, si el negocio lo
  requiere.

---

## 5. Experiencia de usuario

- ⬜ **Tema claro/oscuro manual**: hoy el modo oscuro sigue al sistema; falta un
  selector persistente.
- 🟡 **Accesibilidad**: hay `aria-sort`, etiquetas, foco visible y ayuda
  contextual; falta una auditoría formal de contraste AA y navegación completa
  por teclado.
- ⬜ **Cambio de idioma** español/inglés.
- ⬜ **Notificaciones de stock bajo** en tiempo real.
- ⬜ **Rutas independientes para una venta en curso**: no perder el carrito al
  navegar a otra pantalla.
- ⬜ **Onboarding**: recorrido guiado para el primer turno de caja.
- ⬜ **Preferencias por usuario**: columnas visibles, filtros guardados y
  pantalla de inicio.

---

## 6. Rendimiento y operación

- ⬜ **Paginación por cursor (keyset)** para listas grandes en lugar de `OFFSET`.
- ⬜ **Caché** de productos/búsquedas frecuentes y datos estáticos del frontend.
- ⬜ **Monitoreo**: logs estructurados, métricas, alertas de errores 5xx y
  latencia.
- ⬜ **Cold start de Render**: plan pago o keep-alive; evaluar Redis/caché
  compartida si crece la concurrencia.
- ⬜ **Idempotencia en pagos** para evitar cobros duplicados al reintentar.
- ⬜ **Respaldo y recuperación documentados** con tiempos objetivo (RPO/RTO).

---

## 7. Infraestructura y despliegue

- ⬜ **Separar entornos** dev / staging / producción con bases y variables
  propias.
- 🟡 **Contenedores**: backend `python:3.12-slim` y frontend multi-stage con
  nginx. Queda revisar tamaño, usuario no root y distroless si aplica.
- ⬜ **Escaneo de imágenes** (Trivy/Snyk) en el pipeline.
- ✅ **TLS y HSTS**: Render/Vercel gestionan TLS y el backend envía HSTS en
  producción. Queda monitorear vencimiento de certificados.
- ✅ **Secretos en artefactos**: `empaquetar.ps1` excluye `.env.local`, `.neon`,
  entornos virtuales, `node_modules`, `dist` y cachés.
- ⬜ **Versionado de release**: crear tags `v1.0.0` y notas de release en GitHub.
- ⬜ **Runbook de incidentes**: caída de Neon, Render o Vercel; restauración y
  comunicación.

---

## Criterio general

Para cada mejora conviene priorizar por **riesgo/beneficio**, **esfuerzo** y
**momento del negocio**. Orden sugerido para la siguiente etapa:

1. Automatizar respaldos + simulacro de restauración.
2. Seguridad: refresh tokens, auditoría de acciones y cambio de clave
   obligatorio.
3. Impresión de recibos y cierre de caja.
4. Staging + monitoreo/alertas.
5. Historial de clientes y límites de crédito.
6. Multisucursal, descuentos y facturación electrónica, si el negocio lo pide.

*Última actualización: 20 de octubre de 2026.*
