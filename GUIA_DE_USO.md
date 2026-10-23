# Guía de uso — POS Casi Obsceno

Bienvenido al sistema de punto de venta de Casi Obsceno. Esta guía explica, en lenguaje cotidiano, cómo usar cada pantalla. Está pensada para cajeros, administradores y cualquier persona que vaya a operar el sistema a diario.

---

## 1. Iniciar sesión

Al abrir la aplicación aparece la pantalla de acceso. Escribe tu **usuario** y tu **contraseña** y presiona **Entrar**.

- El usuario no distingue entre mayúsculas y minúsculas.
- Si los datos no coinciden, verás el mensaje exacto del sistema.
- Si olvidas tu contraseña, pídele a un administrador que te la restablezca.
- El **ojito** 👁 junto al campo de contraseña muestra u oculta lo que escribes, para revisarlo antes de entrar (también al crear usuarios y al cambiar tu clave).

> **Primer ingreso del administrador**: la primera vez se usa el usuario `admin` y la contraseña que definió quien instaló el sistema. **Cambia esa contraseña de inmediato** en *Mi perfil*.

---

## 2. Mi perfil

Aquí puedes:

- Ver tus datos (usuario, nombre y rol).
- **Cambiar tu contraseña**. Usa una clave que nadie más conozca y no la compartas.

---

## 3. Inicio (dashboard)

Es el resumen del negocio. Muestra las cifras principales de ventas y actividad:

- **Ventas de hoy**, de los **últimos 7 días** y del **mes actual**.
- **Gráfico de ventas** con dos vistas: **7 días** o **12 meses**. La vista mensual grafica cada mes; al pasar el cursor ves su total y cantidad de facturas, y debajo aparece el acumulado del año móvil.
- **Caja disponible**: el efectivo y banco que quedan después de restar lo apartado en los **bolsillos de gastos vitales**. También muestra el total de caja/banco y cuánto está reservado.
- **Cartera por cobrar**, facturas pendientes/a crédito, productos con stock bajo y totales de clientes/productos.

Úsalo para tener una idea rápida de cómo va el día, la semana o el año.

---

## 4. Productos

Esta es la lista de lo que vendes.

### Ver y buscar

- Se muestran **código, nombre, precio y stock**.
- Usa la caja de **búsqueda** para encontrar un producto por código o nombre (funciona mientras escribes).
- Usa el **paginador** para pasar de página en listas largas.

### Crear un producto

1. Presiona **+ Nuevo producto**.
2. Diligencia **código** (dentro de una misma lista, debe ser único), **nombre**, **precio** y **stock inicial**.
3. Presiona **Guardar**.

### Editar un producto

- Presiona **Editar** en la fila del producto.
- Puedes cambiar el **nombre** y el **precio** (el código no se puede modificar).

### Unidades 1:1 (compra = venta)

- Al crear o editar un producto hay una casilla **«Se compra y se vende en la misma unidad (1:1)»**, marcada por defecto.
- Déjala marcada cuando compras y vendes el producto en la misma unidad (por ejemplo, una botella). Así **Costos** puede comparar su costo con el precio de venta.
- Desmárcala cuando compras por caja o paquete y vendes por unidad: el producto no mostrará la relación CMV/precio en Costos, porque el costo de compra no es comparable con el precio de una sola unidad.

### Movimientos de stock

- El botón **Stock** abre el formulario para registrar un movimiento de inventario.
- Tipos disponibles:

| Tipo | Para qué se usa |
|------|-----------------|
| Entrada por Compra | Cuando llega mercancía nueva |
| Salida por Venta | Cuando sale mercancía por una venta |
| Devolución | Cuando un cliente devuelve mercancía y vuelve a entrar |
| Ajuste | Correcciones manuales; usa signo: `+` suma, `−` resta |

Puedes asociar una **referencia** (por ejemplo, el número de la compra) para dejar constancia.

### Historial (kardex)

El botón **Historial** muestra el historial completo de ese producto: fecha, tipo de movimiento, cuánto cambió el stock y el saldo después de cada movimiento. Es útil para revisar por qué un stock varió.

---

## 5. Clientes

Aquí registras las personas que compran en el local.

### Crear o editar un cliente

Se registran: **nombre**, **documento** (es único: no puede haber dos clientes con el mismo), **celular** y **correo**.

- Presiona **+ Nuevo cliente** para agregar uno.
- Presiona **Editar** en la fila para corregir sus datos.

Registrar bien a los clientes permite asociarle las ventas a la persona correcta.

### Eliminar un cliente

Solo se puede eliminar un cliente que **no tenga facturas** y que **no esté
vinculado a un usuario** para nómina. Si tiene ventas, el sistema lo impide para
conservar el historial; en ese caso, si es un duplicado, usa la fusión. Si está
vinculado a un usuario, desvincúlalo primero desde **Usuarios**.

### Fusionar clientes duplicados (solo administradores)

Sirve cuando la misma persona quedó registrada varias veces con nombres
distintos:

1. Marca con las casillas los clientes que corresponden a la misma persona.
2. Presiona **Fusionar seleccionados**.
3. Elige el cliente que se conservará como principal.
4. Confirma la operación.

Las facturas de los duplicados se reasignan al cliente principal y los registros
duplicados se eliminan. **No se borra ninguna factura**: solo queda todo el
historial consolidado en un único cliente. Si el cliente principal tiene datos
vacíos (documento, celular o correo), se completan con los del duplicado cuando
no haya ambigüedad.

---

## 6. Ventas / Facturas

Aquí se registra cada venta.

### Registrar una venta (paso a paso)

1. **Abrir caja** (ver sección 7): para vender primero debe haber una caja abierta.
2. Presiona **+ Nueva venta**.
3. **Agrega los productos** que se van a vender, con sus cantidades. El sistema va sumando el total.
4. Si quieres, **asigna la venta a un cliente**.
5. Elige la **forma de pago**: efectivo, transferencia, tarjeta u otro.
6. El pago puede ser **total o parcial**:
   - Si el cliente paga el valor completo, la factura queda **Pagada**.
   - Si paga por partes, la factura queda con un **saldo pendiente** que luego puedes ir cobrando.
7. Confirma la venta.

### Cobrar una factura pendiente

En la lista de ventas puedes ver qué facturas tienen **saldo pendiente** y registrar nuevos pagos hasta dejarlas en **Pagada**.

### Filtrar y totalizar ventas

Arriba de la lista puedes filtrar por:

- **# de factura o nombre del cliente**.
- **Desde / Hasta** (rango de fechas).
- **Estado** (Abierta, Crédito, Pagada, Pagado Parcial, Anulada).

Con los filtros aplicados, el sistema muestra un **totalizador** con:

- **Total facturado**: suma de todas las facturas que cumplen los filtros.
- **Saldo pendiente**: lo que aún falta por cobrar de esas facturas.
- **Anulado**: valor de las facturas anuladas incluidas en el filtro.
- **Neto**: total facturado menos lo anulado.

Los totales cubren **todos los resultados filtrados**, no solo la página visible. Para un reporte por día con exportación a Excel/PDF, usa **Reportes → Ventas** (ver sección 8).

### Anular una factura

Si una venta se anula:

- Presiona **Anular** en la factura.
- **Exige un motivo** (por ejemplo, "cliente desistió", "error de digitación").
- El sistema guarda quién anuló, cuándo y por qué: queda constancia de todo.

> **Nota importante**: anular es distinto de "borrar". Las facturas anuladas ya no cuentan en las ventas, pero el registro queda para auditoría. Anular devuelve el stock de los productos vendidos.

### Retiro de un producto de la factura

Si quieres quitar un renglón de una factura (por ejemplo, porque el cliente se arrepintió de ese producto), puedes retirarlo. El renglón queda marcado y no se borra del registro, solo deja de sumar al total.

---

## 7. Caja

La caja se maneja por **turnos**: un cajero la abre al empezar y la cierra al terminar.

### Abrir caja

1. Presiona **Abrir caja**.
2. Escribe el **saldo inicial** (cuánto dinero hay en la caja al empezar).
3. A partir de ahí, cada venta ingresa automáticamente a la caja del turno.

### Movimientos manuales de caja

Puedes registrar **entradas** (dinero que entra) y **salidas** (dinero que sale) que no provienen de una venta. Cada movimiento manual lleva una **categoría** obligatoria:

- **Entradas:** Aporte cultural, Donación, Evento u Otro ingreso.
- **Salidas:** Arriendo, Servicios, Nómina, Gasto menor, Pago a proveedor, Devolución u Otro gasto.

Para registrarlo:

1. Elige **Entrada** o **Salida**.
2. Elige la **categoría**. Por ejemplo, un aporte cultural usa **Entrada → Aporte cultural**.
3. Escribe una **referencia** clara, por ejemplo `Aporte cultural – Evento de octubre` o `Arriendo de octubre`.
4. Indica el **monto** y la **forma de pago** según cómo entró o salió el dinero (**Efectivo**, **Transferencia** o **Tarjeta**).
5. Usa la **observación** para el detalle opcional.

La **referencia** es obligatoria y es la que aparece en la tabla de movimientos. Los movimientos quedan en el historial del turno y se incluyen en el cierre de caja.

En la tabla del turno puedes **filtrar por categoría** y ver un **resumen por categoría** con cantidad de movimientos, entradas, salidas y neto. Así puedes revisar rápido, por ejemplo, cuánto entró por aportes culturales. El **Historial** de cada turno permite el mismo filtro por categoría.

Los movimientos automáticos también reciben una categoría para que el resumen sea completo: **Ventas** (abonos de facturas), **Compra de inventario** (ingresos), **Pago a proveedor** (pagos de compras a crédito), **Devolución** (anulaciones), **Apertura** y **Cierre**. No se pueden registrar a mano.\n\nLos movimientos anteriores a esta actualización que no se puedan clasificar automáticamente aparecen como **Sin categoría**. Las aperturas y cierres históricos sí se clasifican solos.

> Un aporte cultural **no es una venta**: no aparece en Reportes de ventas. En el Balance aumenta el efectivo o el banco (y el patrimonio residual), pero no la utilidad del período.

### Cerrar caja

1. Presiona **Cerrar caja**.
2. Ingresa el **saldo final real** (el dinero físico que hay al cerrar).
3. El sistema compara el saldo esperado con el real, dejando constancia de las diferencias si las hay.

> Regla: no se pueden registrar ventas con la caja cerrada. Olvídate de cerrar la caja si falta facturar algo.

---

## 8. Reportes

En **Reportes** consultas y exportas la información del negocio. Requiere el permiso `reportes.ver`; el reporte de **Nómina** exige además `nomina.descontar`. Cada pestaña —**Ventas**, **Más vendidos**, **Cartera**, **Cierres de caja**, **Inventario** y **Nómina**— se puede exportar a **Excel** o **PDF** con los mismos filtros que ves en pantalla.

### Fechas: días calendario exactos

El filtro **Desde / Hasta** de los reportes con fechas trabaja con **días calendario en hora de Colombia**:

- **Desde** incluye desde las **00:00** de ese día.
- **Hasta** incluye el **día completo**, hasta las **23:59:59**.
- Cada operación se fecha cuando ocurre: las ventas con la fecha de **facturación**, la nómina con la fecha del descuento. Una venta registrada a las 00:30 del día 20 cuenta en el **20**, aunque la caja siga abierta desde el 19.

Así, **Reportes → Ventas** responde a "cuánto se vendió el día X" y **Reportes → Nómina** a "cuánto se descontó entre X e Y".

> **Cartera** e **Inventario** no usan fechas: muestran el estado actual.

### Cierres de caja: el filtro es por apertura del turno

En **Reportes → Cierres de caja** las fechas filtran por la **fecha de apertura del turno**, y el reporte muestra el turno **completo** (todos sus movimientos y ventas) en el día en que se abrió. Solo aparecen turnos **cerrados**.

Sirve para lo que su nombre dice: **ver todas las cajas abiertas entre X e Y** —por ejemplo, las de un evento o todas las del mes—, cada una con su cuadre.

> **Importante**: un turno que abre el 19 y cierra después de medianoche se reporta **completo el 19**, y las ventas que se hayan cobrado después de las 00:00 también suman en esa caja del 19. Esas mismas ventas, en **Reportes → Ventas**, aparecen fechadas el **20**. No es un descuadre: son dos criterios distintos.

### Cómo cuadrar sin confundirse

- **Total vendido por día calendario**: usa **Reportes → Ventas**.
- **Cuadre de una caja concreta**: usa **Reportes → Cierres de caja** (o la pantalla **Caja**) y revisa ese turno.
- **Reporte de un evento**: abre una **caja aparte por evento**. Cada turno queda identificado por su apertura y el filtro de Cierres de caja te entrega exactamente ese evento, aunque comparta día con otro.

> Si un día largo tiene varios eventos, no los mezcles en una misma caja: abre una caja nueva en cada uno para poder reportarlos y cuadrarlos por separado.

### Balance general

Las fechas del **Balance** filtran **solo el estado de resultados**; los activos, pasivos y patrimonio siempre son un corte del momento de la consulta (ver sección 10).

---

## 9. Ingresos de inventario y cuentas por pagar

La pantalla **Ingresos** registra la entrada de mercancía al inventario. Cada ingreso tiene proveedor (opcional), **fuente de pago**, forma de pago, total e ítems. El total es obligatorio y no se puede cambiar después; la fuente de pago tampoco se edita una vez registrado el ingreso.

### Proveedores

El menú **Proveedores** es el catálogo de proveedores del negocio. Cada uno guarda **nombre**, **documento/NIT**, **celular** y **correo**. Requiere los permisos `proveedores.ver`, `proveedores.crear`, `proveedores.editar` y `proveedores.eliminar`, configurables por rol en **Permisos**.

- Al registrar un ingreso, el proveedor se elige de este catálogo. También puedes crear uno nuevo sin salir del formulario con **＋ Nuevo proveedor…**.
- Los nombres de proveedor que ya estaban escritos en ingresos anteriores se trasladaron automáticamente al catálogo; no hay que volver a registrarlos.
- Si cambias el nombre de un proveedor, el cambio se refleja en todos sus ingresos, porque los ingresos quedan enlazados al proveedor y no a un texto copiado.
- Un proveedor **con ingresos asociados no se puede eliminar**, para no perder la trazabilidad de las compras. Sí puedes editarlo.
- Por defecto, el rol **Cajero** puede ver, crear y editar proveedores; eliminar queda reservado al Admin salvo que se habilite en **Permisos**.

### Fuente de pago

| Fuente | Qué significa |
|--------|---------------|
| **Caja activa** | Exige una caja abierta. Efectivo y transferencia descuentan de la caja; Crédito y Donación no mueven dinero, pero quedan ligados al turno. |
| **Balance general** | No exige caja abierta y no genera movimientos de caja. Úsala para compras ya pagadas por fuera del POS o para saldos iniciales. |

En **Balance general**:

- **Efectivo** o **Transferencia**: el ingreso queda marcado como **Pagado**, pero no mueve efectivo ni banco. El inventario entra al balance y la contrapartida queda en el patrimonio residual.
- **Crédito**: queda como **cuenta por pagar**. Cuando la pagues desde Ingresos, el total sí saldrá de la caja abierta.
- **Donación**: no mueve caja y no genera deuda.

> No uses **Balance general** para ocultar una salida de caja que sí ocurrió. Si el dinero salió del efectivo o del banco del turno, registra el ingreso con fuente **Caja activa**.

### Formas de pago de un ingreso

| Forma | Fuente Caja activa | Fuente Balance general |
|-------|--------------------|------------------------|
| **Efectivo** | El total sale de la caja en efectivo. | Queda pagado por fuera; no mueve caja. |
| **Transferencia** | El total sale del bolsillo de banco. | Queda pagado por fuera; no mueve caja. |
| **Crédito** | No sale dinero todavía; queda como **cuenta por pagar**. | No sale dinero; queda como **cuenta por pagar**. |
| **Donación** | No sale dinero y no genera deuda. | No sale dinero y no genera deuda. |

Los ítems pueden ser un producto existente, un producto nuevo o un ítem **Otros** (por ejemplo, un servicio o un gasto que no es inventario).

### Pagar una compra a crédito

1. Entra a **Ingresos** y busca la compra con forma de pago **Crédito** (la columna **Pago** dice **Pendiente**).
2. Presiona **Ver**.
3. En el panel **Pago de la compra**, elige **Efectivo** o **Transferencia**.
4. Presiona **Registrar pago**.

El pago:

- Descuenta el total de la **caja abierta** (efectivo o banco), aunque la compra se haya registrado con fuente **Balance general**.
- Deja la cuenta por pagar en cero.
- Guarda quién pagó, cuándo y con qué forma de pago.
- No se puede deshacer y, una vez pagada, la compra ya no se puede editar.

> Si no hay caja abierta, el sistema pide abrirla antes de pagar. Si ya habías registrado el pago como movimiento manual de caja, no lo registres otra vez: estarías descontando el dinero dos veces.

---

## 10. Balance general

El **Balance** es una foto del negocio en el momento de la consulta. Está en el menú **Balance** y requiere el permiso **`balance.ver`** (el Admin lo tiene por defecto; se puede habilitar a otros roles en **Permisos**). Para crear bolsillos y apartar/liberar dinero se necesita además **`balance.editar`**.

### Qué muestra

- **Activos**:
  - **Efectivo** y **Banco**: saldo esperado del turno de caja abierto. Si no hay turno abierto, se usan los saldos reales del último cierre. Incluyen el dinero apartado en bolsillos.
  - **Reservado en bolsillos**: dinero apartado para gastos vitales. Incluye los saldos iniciales, que no se descontaron de efectivo/banco.
  - **Disponible para operación**: efectivo + banco menos lo reservado. Es la liquidez que queda para el día a día.
  - **Inventario**: stock valorizado al **costo vigente** del producto. El costo vigente es el promedio ponderado de las compras; si hay un **costo manual** más reciente, ese manda; y si el producto tiene **receta**, se usa el costo calculado de sus insumos (ver sección 11). Si un producto nunca tuvo costo, se valoriza a **precio de venta** y el sistema lo marca como respaldo.
  - **Cartera por cobrar**: saldo pendiente de las facturas no anuladas.
- **Pasivos**: compras a crédito que todavía no se han pagado, sin importar si se registraron con fuente **Caja activa** o **Balance general**.
- **Patrimonio**: activos menos pasivos. El sistema no lleva aportes ni retiros de capital, así que es un patrimonio **residual**. Los ingresos de balance general pagados por fuera no mueven caja; su contrapartida queda en este patrimonio.
- **Estado de resultados** del período elegido:
  - Ventas no anuladas.
  - Costo de ventas (costo vigente de los productos vendidos).
  - Gastos: salidas de caja que no son compras de inventario, pagos de esas compras ni devoluciones por anulación, más los ítems **Otros** de los ingresos (también los registrados en balance general).
  - Utilidad y margen.
  - Las facturas anuladas no se reconocen como venta y su devolución tampoco como gasto.

### Fechas y exportación

- Las fechas **Desde / Hasta** filtran **solo el estado de resultados**. El balance de activos, pasivos y patrimonio siempre es un corte actual.
- Presiona **Consultar** para aplicar las fechas y **Actualizar** para refrescar el corte.
- **Exportar Excel** incluye cinco hojas: Balance, Bolsillos, Resultados, Inventario y Cuentas por pagar.
- **Exportar PDF** incluye el resumen del balance y los resultados.

### Cuentas por pagar

La tabla **Cuentas por pagar** lista las compras a crédito pendientes, sin importar si se registraron con fuente **Caja activa** o **Balance general**. Si tienes permiso para ver Ingresos y pagar compras a crédito, aparece el botón **Pagar**, que abre el ingreso para registrar el pago.

> Los ingresos de **Balance general** en efectivo o transferencia ya están pagados por fuera y no aparecen como cuenta por pagar. Los de **Crédito** sí aparecen hasta que se paguen.

### Bolsillos de gastos vitales

Un **bolsillo** es una marca virtual para apartar una parte del efectivo/banco y reservarla para un gasto vital, por ejemplo el **arriendo**. No es una cuenta nueva ni una salida de dinero: el efectivo sigue en la caja y en el total de activos, pero deja de contar como **disponible para operación**.

1. En **Balance**, sección **Bolsillos de gastos vitales**, presiona **+ Nuevo bolsillo**.
2. Escribe un **nombre** (por ejemplo `Arriendo`), una descripción opcional y, si ya tenías dinero apartado, un **saldo inicial**. Ese saldo suma al bolsillo pero **no se descuenta del banco**.
3. En la fila del bolsillo, presiona **Aportar** e indica cuánto quieres apartar. El sistema no permite apartar más de lo que hay disponible en efectivo + banco.
4. Si el bolsillo ya existía y necesitas registrar su saldo inicial, usa **Saldo inicial** en la fila. No se descuenta de la caja/banco.
5. Cuando necesites usar el dinero, presiona **Liberar** para devolverlo a la liquidez disponible. No se puede liberar más de lo reservado.
6. **Historial** muestra cada aporte, retiro, monto, nota y usuario; los saldos iniciales aparecen marcados como **Inicial**.
7. **Archivar** oculta el bolsillo de la lista, pero solo si su saldo es cero; el historial se conserva.

Para pagar el arriendo, el orden recomendado es: **liberar** el valor del bolsillo y luego registrar la **salida real** en **Caja** con categoría **Arriendo**. Así el gasto queda en el estado de resultados y el bolsillo no sigue mostrando ese dinero como reservado.

> Los bolsillos **no cambian el total de activos ni la utilidad**. Los aportes normales reducen el **disponible** y aumentan el **reservado**; el saldo inicial solo aumenta el reservado, porque representa ahorros que ya existían antes de usar la app. No se puede apartar más que el efectivo + banco actual. Si al pagar un gasto no liberas el bolsillo, el sistema no lo detecta automáticamente: el bolsillo seguiría con saldo.

> El costo de ventas y el inventario usan el **costo vigente** de cada producto: promedio de compras, costo manual más reciente o costo de la **receta** si es una preparación. Es una aproximación operativa: el sistema no lleva capas de costo por lote ni contabilidad de partida doble.

---

## 11. Costos y recetas

El módulo **Costos** sirve para dos cosas:

1. Llevar el **histórico de los costos de compra** de cada producto y compararlo con su precio de venta.
2. Calcular el costo de **productos transformados o preparaciones** a partir de una **receta estándar** de insumos.

**CMV** significa *costo de la mercancía vendida*; en este módulo es el costo unitario vigente del producto.

Está en el menú **Costos**. Requiere el permiso **`costos.ver`**; para registrar costos manuales o editar recetas, **`costos.editar`**. Por defecto solo el **Admin** los tiene; se pueden habilitar a otros roles en **Permisos**.

Cada pestaña muestra una **ayuda breve** con lo que hace; al pasar el cursor sobre la pestaña también aparece una pista.

### Histórico

La pestaña **Histórico** muestra una vista sintética por producto:

- **Mejor precio 6 sem**: el menor costo unitario de compra registrado en los últimos 42 días, con el proveedor y la fecha. Si el producto no tiene compras en ese período pero sí un costo manual, muestra el menor costo manual y lo marca como **Manual**.
- **Costo vigente**: el costo que usa el sistema hoy. El orden de prioridad es:
  1. **Receta**, si el producto es una preparación.
  2. **Costo manual** más reciente, si existe.
  3. **Promedio ponderado** de todas las compras del producto.
- **Variación 6 sem**: compara el primer y el último costo registrado dentro de los últimos 42 días. Un costo que baja se muestra en verde; uno que sube, en rojo. Si hay menos de dos registros, muestra **—**.
- **Precio venta**: el precio actual del producto.
- **CMV / venta**: solo aparece cuando el producto se compra y se vende en la misma unidad (**1:1**) o cuando es una preparación con receta. Muestra qué porcentaje del precio de venta se lo lleva el costo (CMV) y el margen en pesos y porcentaje.

El botón **Historial** abre el detalle de todos los costos del producto: compras (con proveedor, cantidad y número de ingreso) y costos manuales. Por defecto muestra los últimos 6 semanas; puedes activar **Ver todo el histórico**.

> El histórico se construye con las líneas de **Ingresos de inventario** y los **costos manuales**. Si corriges el costo de un ingreso, ese punto del histórico también cambia.

### Preparaciones y recetas

Una **preparación** es un producto que no se compra directamente, sino que se produce a partir de otros productos (insumos). Ejemplos: una arepa, una salsa, un plato terminado.

La pestaña **Preparaciones** permite crear una **receta estándar**:

1. Presiona **+ Nueva receta**.
2. Elige el **producto que se prepara** (debe ser un producto del catálogo; si ya tiene receta, se edita desde la lista).
3. Define el **rendimiento**: cuántas unidades vendibles produce la receta completa. Por ejemplo, una receta de salsa que rinde 10 porciones tiene rendimiento **10**.
4. Agrega los **insumos** y la **cantidad** de cada uno para toda la receta.
5. Presiona **Guardar receta**.

El costo se calcula así:

> **Costo total** = suma de (cantidad del insumo × costo vigente del insumo)
>
> **Costo por unidad** = costo total ÷ rendimiento

El costo vigente de cada insumo usa las mismas reglas del histórico: receta si es otra preparación, costo manual si existe, o promedio de compras. Por eso una receta puede usar **otra preparación como insumo** (recetas anidadas). El sistema rechaza las recetas que generan un **ciclo** (por ejemplo, A usa B y B usa A).

Si a un insumo le falta el costo, la receta queda **Incompleta** y el sistema indica qué insumos faltan. Mientras esté incompleta, el producto no tiene costo calculado y el Balance lo trata como **sin costo** (usa el precio de venta como respaldo).

> **Importante:** la receta **solo calcula el costo**. No descuenta insumos del inventario ni suma stock de la preparación al vender. El stock de la preparación se sigue manejando con **Movimientos de stock**, como cualquier otro producto; recuerda cargarle stock antes de venderla.

### Costos manuales

La pestaña **Costos manuales** sirve para registrar un costo unitario a mano, por ejemplo para un insumo que nunca se ha comprado por el sistema o para corregir un costo desactualizado.

- Presiona **+ Costo manual** (o **Costo manual** en la fila de un producto del histórico).
- Elige el producto, la fecha, el costo unitario y una nota opcional.
- El registro **más reciente** pasa a ser el costo vigente y reemplaza al promedio de compras.
- Puedes eliminar un registro manual desde la tabla.

> No se puede registrar un costo manual para un producto que tiene receta: su costo se calcula desde los insumos. Si necesitas usar un costo manual, elimina primero la receta.

### Relación con el Balance

El **Balance general** usa el costo vigente de cada producto:

- Los productos con compras se valorizan al promedio ponderado.
- Los productos con costo manual usan ese costo.
- Las preparaciones con receta usan el costo calculado de la receta, tanto para el **inventario** como para el **costo de ventas**.
- Si a una preparación le falta algún costo, el Balance la marca como **sin costo** y usa el precio de venta como respaldo.

La columna **Origen del costo** del inventario indica si el costo viene del promedio de compras, de un costo manual o de una receta.

---

## 12. Usuarios y permisos (solo administradores)

Solo el rol **Admin** puede entrar a estas pantallas.

En **Usuarios** puedes:

- **Crear usuarios** con rol **Admin**, **Cajero** o **Mesero**:
  - *Admin*: acceso total, incluidos Usuarios y Permisos.
  - *Cajero*: opera caja, ventas, productos, clientes, ingresos y proveedores, y puede pagar compras a crédito; no anula facturas, ni ve reportes, costos o balance, ni administra usuarios.
  - *Mesero*: toma pedidos y cobra, gestiona clientes y ve la caja; no opera la caja ni entra a ingresos, reportes o usuarios.
- **Editar** datos y rol de un usuario existente.
- **Restablecer contraseñas** cuando un usuario la olvida.
- **Eliminar usuarios** que ya no trabajen en el local (los vendidos en periodos pasados quedan intactos).
- **Vincular un usuario a un cliente** para manejar sus compras a crédito como
  deuda de nómina (ver abajo).

### Vincular un usuario a un cliente (nómina)

Pensado para empleados que compran a crédito en el local y luego se les
descuenta de la nómina:

1. Presiona **Editar** (o **+ Nuevo usuario**).
2. En **Cliente vinculado (nómina)** elige el cliente del empleado.
3. Guarda.

El vínculo es **uno a uno**: un cliente solo puede estar en un usuario. Si el
cliente no aparece en la lista, es porque ya está vinculado a otro usuario (o es
el "Cliente eventual"). Para desvincular, deja la opción **Sin vincular**.

### Descontar de la nómina

Con el usuario vinculado, en la fila aparece el botón **Nómina**:

1. Presiona **Nómina** para ver las facturas a crédito pendientes del empleado.
2. Escribe el **monto a descontar** (déjalo en el total para saldar toda la
   deuda).
3. Presiona **Aplicar descuento**.

El monto se abona a las facturas **más antiguas primero** y baja el saldo
pendiente. Este abono **no entra a la caja** como efectivo o banco: es una
compensación contra la nómina, no un cobro en el local. Por eso tampoco exige
tener la caja abierta, y las facturas con abonos de nómina no se pueden anular
desde Ventas (primero hay que ajustar la nómina).

### Auditar los descuentos de nómina

Cada descuento queda registrado como un **evento de auditoría** con:

- Empleado y cliente **congelados** al momento del descuento (aunque luego se
  renombre el cliente o se desvincule el usuario, el historial conserva los
  nombres).
- Monto descontado, saldo pendiente después del abono y cantidad de facturas
  afectadas, con el **detalle de cada factura y el abono aplicado**.
- Quién aplicó el descuento y la fecha.
- Una **nota / período** opcional (por ejemplo, "Nómina octubre 2026").

En el modal **Nómina** de cada usuario aparece el **Historial de descuentos**
con esos datos. Para ver todos los descuentos del local, entra a **Reportes →
Nómina**, filtra por fecha y exporta a Excel o PDF. Los pagos de nómina
anteriores a esta actualización se migran como eventos individuales con la nota
«Registro migrado»; no es posible reconstruir la agrupación original, pero el
monto y la factura quedan auditados.

En **Permisos** ajustas, con casillas por módulo y acción, qué puede hacer cada
rol **Cajero** y **Mesero**. El rol **Admin** siempre tiene todo y no se edita.
Los cambios se aplican de inmediato (cada usuario los recibe al iniciar sesión).

Permisos nuevos de esta actualización:

- **`clientes.fusionar`**: permite fusionar clientes duplicados. Solo el
  **Admin** lo tiene por defecto; se puede habilitar a otros roles.
- **`nomina.descontar`**: permite aplicar descuentos de nómina y consultar su
  historial/reporte. Solo el **Admin** lo tiene por defecto.
- **`ingresos.pagar`**: permite registrar el pago de compras a crédito. El
  **Cajero** lo tiene por defecto; se puede quitar.
- **`balance.ver`**: permite ver y exportar el **Balance general**. Solo el
  **Admin** lo tiene por defecto; se puede habilitar a otros roles.
- **`balance.editar`**: permite crear bolsillos de gastos vitales y apartar o
  liberar dinero. Requiere también `balance.ver`. Solo el **Admin** lo tiene por
  defecto; se puede habilitar a otros roles.
- **`feedback.crear`**: permite enviar comentarios, ideas y reportes de error
  desde el botón flotante. El **Cajero** y el **Mesero** lo tienen por defecto.
- **`feedback.gestionar`**: permite abrir la bandeja **Feedback** y cambiar
  estado, prioridad, etiquetas, responsable y notas internas. Solo el **Admin**
  lo tiene por defecto.

---

## 13. Feedback y sugerencias

En todas las pantallas del POS aparece un botón flotante **Feedback** (abajo a
la derecha). Sirve para reportar un error, proponer una idea, hacer una duda o
dejar cualquier comentario al equipo administrador.

1. Presiona **Feedback**.
2. Elige el tipo: **Error**, **Idea**, **Duda** u **Otro**.
3. Escribe el comentario. Si es un error, incluye los pasos para reproducirlo.
4. Opcionalmente, presiona **Capturar pantalla**. Se toma una imagen de la
   página y puedes **arrastrar sobre la imagen** para tapar con negro nombres,
   montos, teléfonos o cualquier dato sensible. Usa **Deshacer** o **Limpiar
   marcas** si te equivocas. También puedes **Quitar captura** y enviar solo el
   texto.
5. Si adjuntas captura, marca la confirmación de que revisaste y tapaste los
   datos sensibles.
6. Presiona **Enviar feedback**. Verás un número de referencia.

El envío incluye automáticamente contexto técnico útil (ruta de la pantalla,
rol, versión de la app, navegador, tamaño de pantalla, idioma y el último error
de JavaScript, si hubo). Ese contexto no incluye tu contraseña ni el contenido
de campos de texto. La captura, si decides adjuntarla, es una imagen de la
página y puede mostrar lo que esté en pantalla: revisa que no muestre datos que
no quieras compartir.

Los administradores ven los envíos en **Feedback**, en el menú lateral. Allí
pueden:

- Filtrar por estado, tipo, prioridad o texto.
- Abrir **Gestionar** para cambiar **estado** (Nuevo, En revisión, Resuelto,
  Descartado), **prioridad** (Baja, Media, Alta), **etiquetas**, **notas
  internas** y **responsable**.
- **Asignarme** el caso o **Liberar** la asignación.
- Ver y descargar la captura adjunta.

Las capturas se guardan en la base de datos y solo se entregan a usuarios con
permiso `feedback.gestionar`. No envíes contraseñas, claves ni datos personales
sin redactar: la captura es una foto de lo que está en pantalla.

---

## 14. Trabajar desde el celular

El sistema se adapta a pantallas pequeñas:

- El menú se convierte en un **menú lateral deslizable** (botón de tres líneas).
- Las tablas se convierten en **tarjetas** apiladas para que sea fácil leerlas.
- Los modales y formularios se ajustan automáticamente.

---

## 15. Buenas prácticas diarias

- **Abre la caja** al empezar el día y **ciérrala** al terminar.
- **Registra cada venta** en el momento; no acumules "para después".
- **Registra las compras a crédito** y págalas desde **Ingresos** cuando las canceles, para que las cuentas por pagar del balance estén al día.
- Usa **Balance general** solo para compras ya pagadas por fuera del POS o saldos iniciales. Si el dinero salió de la caja, usa **Caja activa**.
- Pide siempre el **motivo** cuando anules o retires productos.
- Mantén la **contraseña** privada y cámbiala periódicamente.
- Al final del turno, revisa en el **dashboard** el total del día para conciliar con el dinero físico.
- Revisa el **Balance general** al menos una vez por semana para ver activos, deudas y resultado del período.

---

## 16. ¿Algo no funciona?

| Situación | Qué hacer |
|-----------|-----------|
| "No se pudo conectar con el servidor" | Espera unos segundos y vuelve a intentar (el servicio puede tardar en despertar). |
| No puedo iniciar sesión | Verifica tu usuario y contraseña; si sigue fallando, pide que te restablezcan la clave. |
| "La caja está cerrada" | Alguien debe abrir la caja aun estando en el turno. |
| No me aparece una pantalla (Usuarios, Reportes, Balance, Caja…) | Tu rol no tiene ese permiso; un Admin puede activarlo en *Permisos*. |
| No me aparece el botón **Feedback** | Tu rol no tiene `feedback.crear`; un Admin puede activarlo en *Permisos*. |
| No puedo tomar la captura de pantalla | Puedes enviar el comentario sin imagen. Si el navegador bloquea la captura, prueba desde un navegador actualizado o en una pantalla con menos contenido. |
| No puedo registrar un ingreso porque no hay caja abierta | Abre la caja o elige fuente **Balance general** si la compra ya se pagó por fuera del POS. |
| Un ingreso de balance general no cambió la caja | Es el comportamiento esperado: esa fuente no genera movimientos de caja. Si el dinero sí salió de la caja, registra la salida manual correspondiente o consulta a un administrador. |
| No puedo pagar una compra a crédito | Verifica que la caja esté abierta, que la compra sea **Crédito**, que no esté pagada y que tengas el permiso `ingresos.pagar`. |
| El balance muestra un producto a precio de venta | Ese producto no tiene costo de compra registrado; el sistema usa el precio de venta como respaldo. Registra su costo en un ingreso para corregirlo. |
| Cometí un error en una venta | Anula la factura (con motivo) y regístrala de nuevo correctamente. |

---

*Última actualización del documento: octubre 2026.*