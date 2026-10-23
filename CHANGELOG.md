# Changelog — POS Casi Obsceno

Historial de cambios relevantes del proyecto. El formato está inspirado en
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el versionado es
semántico.

La versión actual es **1.0.0**. Las versiones anteriores a 1.0.0 son hitos
internos de desarrollo; no existen tags publicados de esas versiones.

---

## [Sin publicar]

### Añadido

- **Saldo inicial de bolsillos**: al crear un bolsillo (o después, con «Saldo
  inicial») se puede registrar dinero que ya estaba apartado. Suma al reservado
  pero no se descuenta del efectivo/banco; los aportes posteriores sí. El
  historial distingue los movimientos iniciales.
- **Forma de pago en el listado de ventas**: la tabla muestra el medio (o los
  medios combinados) de los pagos de cada factura, y «Crédito» cuando aún no
  tiene pagos.
- **Modo offline (Fase 1)**: la app se puede instalar como PWA y abrir sin red.
  Se guardan localmente la sesión (12 h), el catálogo de productos/clientes, la
  caja activa y la última lista de ventas. Las ventas y los cobros creados sin
  conexión entran en una cola local con fecha, turno y precios reales; al volver
  la red se sincronizan con las claves de idempotencia existentes. La UI muestra
  un banner de estado, las operaciones pendientes y un botón de reintento.
- **Cierre de caja protegido**: no se puede cerrar un turno mientras haya
  operaciones offline pendientes. La UI exige sincronizar la cola y volver a
  abrir el cuadro de cierre para recalcular los saldos; si alguna operación
  queda con error, el cierre sigue bloqueado.
- **Ventas offline con stock negativo**: si al sincronizar ya no alcanza el
  stock, la venta no se pierde: el stock queda negativo y la factura se marca
  con `requiere_revision` y una nota visible en Ventas.
- **Trazabilidad offline**: las facturas distinguen `origen` online/offline. El
  backend acepta fecha, turno y precio unitario de la operación original, y los
  pagos conservan la fecha y el turno en que se recibieron.
- Migración `0020_metadatos_offline` para `facturas.origen`,
  `facturas.requiere_revision`, `facturas.nota_revision` y su índice.
- Migración `0021_saldo_inicial_bolsillos` para
  `bolsillo_movimientos.es_inicial`.

### Corregido

- **Detalle de ingresos mostraba «Producto #8»**: las líneas de un ingreso
  ahora incluyen `producto_nombre` y el detalle muestra el nombre real del
  producto en lugar de su id.
- **Ventas que se quedaban en «Guardando…»**: la factura sí se guardaba, pero
  si la respuesta se perdía (red móvil, timeout o cold start de Render) la UI
  esperaba indefinidamente y el cajero no sabía si la venta había quedado
  registrada. La creación de ventas ahora es idempotente: el navegador reintenta
  una vez con la misma `Idempotency-Key` y el backend devuelve la factura
  original en lugar de duplicarla. Las peticiones tienen timeout y, si el cobro
  no se confirma, se avisa para revisar la factura antes de reintentar.
- **Cobros duplicados tras un timeout**: al reintentar un abono parcial cuya
  respuesta se había perdido, podía insertarse dos veces el pago y el
  movimiento de caja. Ahora el cobro también es idempotente mediante
  `Idempotency-Key`: el backend devuelve la factura ya cobrada sin duplicar
  pagos ni entradas de caja.
- **Esperas ilimitadas en PostgreSQL**: se configuran `lock_timeout`,
  `statement_timeout` e `idle_in_transaction_session_timeout` para que una fila
  bloqueada no deje la venta cargando durante minutos.

### Rendimiento

- La creación de una venta bloquea todos los productos en una sola consulta
  (ordenada por id) en vez de hacer una consulta por ítem. Menos viajes a Neon,
  menos latencia y sin riesgo de interbloqueos por orden de bloqueo.
- La respuesta de la factura se carga con sus detalles, pagos y cliente de forma
  anticipada, sin consultas perezosas después del commit.

### Mantenimiento

- **Ping automático a la API**: un workflow de GitHub Actions consulta
  `/api/health` cada 10 minutos para reducir los cold starts del plan free de
  Render. Si GitHub retrasa la ejecución, el servicio puede suspenderse igual;
  para una garantía estricta se recomienda un monitor externo o el plan pago.

### Limitaciones del modo offline

- Solo ventas y cobros funcionan sin red. Productos, clientes, caja,
  inventario, reportes y administración siguen requiriendo conexión.
- La cola y el catálogo se guardan en `localStorage` del navegador. Borrar los
  datos del sitio o usar otro navegador/dispositivo no traslada las operaciones
  pendientes.
- Varios dispositivos pueden vender el mismo stock sin red. Al sincronizar, la
  venta se conserva y queda marcada para revisión; el inventario debe ajustarse
  manualmente.
- La sesión cacheada dura 12 horas. Si el token expira durante el modo offline,
  las operaciones quedan en cola hasta que el mismo usuario vuelva a iniciar
  sesión con conexión.

---

## [1.0.0] — 2026-10-20

Primera versión de producción con la operación completa: ventas, caja,
inventario, costos, balance, proveedores, nómina, reportes, feedback y
administración por permisos.

### Añadido

- **Ayuda contextual en todas las pantallas**: bloque reutilizable con título y
  explicación breve, situado debajo del encabezado. En Costos y Reportes cambia
  según la pestaña activa y las pestañas muestran una pista al pasar el cursor.
- **Identidad visual collage** en el login y el dashboard: textura de papel,
  cinta adhesiva, logo tipo sticker, subrayado de marcador y nota decorativa.
  Implementada con CSS/SVG, sin dependencias nuevas y sin cambios de lógica.
- **Importador con wipe seguro**: nuevas opciones `--wipe`, `--usuario` y
  `--archivo`. El wipe conserva `usuarios` y `permisos_rol`, borra las tablas
  operativas en una sola transacción y reinicia las secuencias.
- **Mapeo correcto de facturas a crédito en la importación**: las filas
  `PENDIENTE` con forma de pago `Crédito` se importan como estado `Crédito`, no
  como `Abierta`.

### Cambiado

- **Preview de Vercel**: los despliegues que no son producción usan un proxy
  same-origin `/api`; producción mantiene la URL directa de `VITE_API_URL`.
- **Reimportación de datos de producción** desde el maestro
  `Sistema_Ventas_CasaCultural_MASTER_v2_BR_mejorado.xlsx`, preservando usuarios
  y permisos.
- **Cuenta `sistema` desactivada**: era un administrador heredado del importador
  con contraseña por defecto. Se conserva la fila por trazabilidad, pero ya no
  puede iniciar sesión. El usuario `admin` sigue activo.

### Corregido

- Las facturas históricas con saldo y forma de pago `Crédito` ya no quedan como
  `Abierta`; aparecen en cartera y en el dashboard como deuda.
- El wipe del importador ya no puede vaciar `usuarios` por el `CASCADE` de la
  FK `usuarios.cliente_id → clientes`.
- La importación conserva la integridad de las claves foráneas y reinicia los
  ids para que las facturas vuelvan a empezar en 1.

### Datos y operación

- Respaldo previo a la reimportación:
  `pos_backend/respaldos/respaldo_20261020_001333.json`.
- Datos finales: **642 facturas** (570 pagadas, 72 a crédito), **1.348
  detalles**, **579 pagos**, **748 movimientos de inventario**, **183 clientes**,
  **49 productos**, **176 movimientos de caja** y **1 turno cerrado**.
- Totales de facturas, saldos, detalles y pagos coinciden exactamente con el
  Excel de origen.
- `alembic_version = 0015`.
- Backend y frontend desplegados y con health check correcto.

### Calidad

- **151 pruebas de backend** y **45 pruebas de frontend** en verde.
- `typecheck`, `lint` y `build` del frontend en verde.
- CI de GitHub Actions ejecutando backend, frontend, pruebas y build.

---

## [0.9.0] — 2026-10-19

Versión funcional amplia: dashboard, bolsillos, balance, costos, proveedores,
nómina, feedback y permisos extendidos.

### Añadido

- **Dashboard de ventas**: ventas de hoy, últimos 7 días y mes actual; gráfico
  con vistas de 7 días o 12 meses; caja disponible, reservado en bolsillos,
  cartera por cobrar y productos con stock bajo.
- **Bolsillos de gastos vitales**: creación y archivo de bolsillos, depósitos,
  retiros e historial. El dinero reservado reduce la caja disponible, pero no el
  total de activos ni la utilidad.
- **Categorías de caja**: categorías para movimientos manuales, filtros,
  resumen por categoría y visualización en el historial de turnos.
- **Balance general**: activos, pasivos y patrimonio; estado de resultados;
  inventario valorizado; cuentas por pagar; bolsillos y exportación a Excel.
- **Costos y recetas**: histórico de costos, mejor precio de las últimas 6
  semanas, costo vigente, variación, recetas con rendimiento, costos manuales y
  relación con el balance.
- **Proveedores**: catálogo con documento, celular y correo; asociación a
  ingresos de inventario y protección contra eliminación si tienen compras.
- **Ingresos de inventario ampliados con proveedor, fuente de pago y cuentas
  por pagar**: fuente Caja activa o Balance general, pago con efectivo,
  transferencia, crédito o donación, y pago posterior de compras a crédito.
- **Nómina**: vínculo usuario-cliente, descuento de compras a crédito contra la
  nómina, consulta de deuda e historial auditable de descuentos.
- **Fusión de clientes duplicados**: reasigna facturas y pagos al cliente
  principal sin borrar historial.
- **Feedback integrado**: botón flotante, captura de pantalla con editor para
  tapar datos sensibles, contexto técnico y bandeja de gestión con estado,
  prioridad, etiquetas, responsable y notas internas. Las capturas solo las ve
  quien tenga `feedback.gestionar`.
- **Nuevas claves de permiso** para balance, costos, proveedores, nómina y
  feedback, con menús, rutas y botones adaptados al rol.
- **Versión de la aplicación** en login y barra lateral, incluida en el contexto
  del feedback.

### Cambiado

- El dashboard pasó de métricas básicas a un resumen operativo con ventas
  semanales/mensuales, caja disponible y cartera.
- La caja incorporó categorías, filtros y resumen, manteniendo el cuadre por
  efectivo y banco.
- Se agregó el reporte de **Nómina** y se ampliaron filtros y exportaciones de
  los reportes existentes.
- La guía de uso se amplió con las nuevas pantallas y reglas de negocio.
- Migraciones **0007 a 0015** para nómina, balance, proveedores, costos,
  categorías/bolsillos y feedback.

### Corregido

- Se protegió la FK de facturas con clientes para evitar borrados con historial.
- Se ajustaron cálculos de nómina, bolsillos, balance y categorías de caja.
- Se corrigieron casos de inventario y cuentas por pagar detectados en pruebas.

---

## [0.8.0] — 2026-10-17

Endurecimiento operativo de caja, inventario, crédito y permisos.

### Añadido

- **Caja separada en efectivo y banco**: apertura, cierre, esperado y diferencia
  por cada medio; reportes y dashboard ajustados; reverso de facturas según la
  forma de pago.
- **Forma de pago obligatoria** en los movimientos de caja, con migración y
  backfill.
- **Ingresos de inventario** con ítems, estados y movimiento de caja; más tarde
  se ampliaron con proveedor, fuente de pago y cuentas por pagar (ver 0.9.0).
  Se corrigió el signo para que resten de la caja en vez de sumar.
- **Facturas abiertas y a crédito** con cliente eventual y bloqueo del cierre de
  caja cuando hay facturas eventuales sin pagar.
- **Pagos combinados**: varias formas de pago en una factura, recálculo de monto
  y protección de cantidades en facturas pagadas o a crédito.
- **Ordenamiento de tablas** en toda la interfaz: servidor para listas
  paginadas y memoria para modales/reportes, con desempate estable y `aria-sort`.
- **Rol Mesero** y **permisos configurables por rol**: catálogo por módulo y
  acción, tabla `permisos_rol`, dependencia `require_permiso`, endpoints de
  consulta/edición y pantalla de matriz de permisos. Admin conserva acceso total.
- **Ojito para mostrar/ocultar contraseñas** en login, usuarios y cambio de
  clave.

### Cambiado

- El movimiento manual de stock solo admite `Ajuste` con motivo obligatorio
  (derrama/pérdida, mal conteo u otro con detalle).
- Editar productos quedó reservado a administradores; crear productos y ajustar
  stock sigue disponible para cajeros.
- El cierre de caja muestra y resta el crédito del turno.
- Se adoptó `.gitattributes` con `* text=auto eol=lf`.

### Corregido

- Se eliminaron movimientos falsos de caja al editar ítems de una venta.
- Se corrigió el signo de los ingresos de inventario en la caja.
- Se corrigió el cálculo del crédito en el cierre de caja.
- Se corrigió el contraste de los desplegables en modo oscuro.

---

## [0.7.0] — 2026-10-16

Base de ingeniería: migraciones, seguridad, respaldos, pruebas y CI.

### Añadido

- **Alembic** con revisión base `0000_esquema_legado` y `0001_regularizacion`;
  detección de bases legadas con `stamp 0000`, `upgrade` al arrancar y
  verificación del esquema contra los modelos.
- **Rate limiting** para login y para el resto de la API.
- **Cabeceras de seguridad**: `Content-Security-Policy`, `X-Frame-Options`,
  `Strict-Transport-Security`, `X-Content-Type-Options` y `Referrer-Policy`.
- **bcrypt configurable** y longitud mínima de contraseña.
- **SECRET_KEY obligatoria** en producción.
- **Revocación de tokens por `token_version`** al cambiar la contraseña.
- **Respaldos portables** con `scripts/respaldo_bd.py` y restauración con
  `scripts/restaurar_bd.py` (simulacro por defecto, `--confirmar`, `--force` y
  reajuste de secuencias en PostgreSQL).
- **Pruebas de backend** con pytest y **pruebas de frontend** con Vitest +
  Testing Library, incluido un E2E de login y navegación protegida.
- **CI en GitHub Actions** para backend y frontend.
- **Importador del Excel maestro reescrito**: atómico, enums, productos por
  código + nombre y mejor manejo de duplicados.
- **Empaquetado seguro**: `empaquetar.ps1` excluye `.env.local`, `.neon`,
  entornos virtuales, `node_modules`, `dist` y cachés.

### Cambiado

- El Excel maestro se renombró y el ZIP generado dejó de versionarse.
- Se documentó el despliegue y el uso en `README.md`, `DEPLOY.md` y
  `RUN_LOCAL.md`.

---

## [0.1.0] — 2026-10-10

MVP funcional del POS.

### Añadido

- Autenticación JWT con roles **Admin** y **Cajero**, usuario insensible a
  mayúsculas y mensajes reales del backend al fallar el login.
- Productos con kardex: entradas por compra, salidas por venta, devoluciones y
  ajustes, con saldo histórico.
- Ventas/facturas con pago total o parcial, formas de pago, anulación con motivo
  y trazabilidad de quién y cuándo.
- Caja con apertura/cierre de turno, saldo inicial, movimientos de entrada/salida
  y conciliación.
- Clientes con documento único, celular y correo.
- Usuarios: creación, edición, cambio de contraseña y eliminación (solo Admin).
- Dashboard con métricas de ventas.
- Reportes con exportación a Excel y PDF.
- Paginación en todas las listas, salto directo de página y filtro de ventas por
  fechas.
- Diseño responsive: menú lateral deslizable, tablas y modales adaptados a móvil.
- Modo oscuro automático y corrección de contraste en desplegables.
- Retiro persistente de productos de una factura y motivo obligatorio de
  anulación.
- Logo del local en barra, menú lateral y login.
- README principal y ajustes finales de interfaz.

---

## Notas de mantenimiento

- Las migraciones se aplican automáticamente al arrancar el backend.
- Los respaldos portables no deben subirse al repositorio porque contienen datos
  personales de clientes.
- El importador debe ejecutarse con `--wipe` solo después de un respaldo y con
  la base apuntando al entorno correcto.
- Para una nueva importación, crear primero el usuario administrador o indicar
  un usuario existente con `--usuario`.
