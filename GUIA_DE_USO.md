# Guía de uso — POS Casi Obsceno

Bienvenido al sistema de punto de venta de Casi Obsceno. Esta guía explica, en lenguaje cotidiano, cómo usar cada pantalla. Está pensada para cajeros, administradores y cualquier persona que vaya a operar el sistema a diario.

---

## 1. Iniciar sesión

Al abrir la aplicación aparece la pantalla de acceso. Escribe tu **usuario** y tu **contraseña** y presiona **Entrar**.

- El usuario no distingue entre mayúsculas y minúsculas.
- Si los datos no coinciden, verás el mensaje exacto del sistema.
- Si olvidas tu contraseña, pídele a un administrador que te la restablezca.

> **Primer ingreso del administrador**: la primera vez se usa el usuario `admin` y la contraseña que definió quien instaló el sistema. **Cambia esa contraseña de inmediato** en *Mi perfil*.

---

## 2. Mi perfil

Aquí puedes:

- Ver tus datos (usuario, nombre y rol).
- **Cambiar tu contraseña**. Usa una clave que nadie más conozca y no la compartas.

---

## 3. Inicio (dashboard)

Es el resumen del negocio. Muestra las cifras principales de ventas y actividad, y puedes:

- **Filtrar por rango de fechas** (desde / hasta) para ver un período específico.
- Consultar indicadores como total facturado, número de ventas y otras estadísticas.

Úsalo para tener una idea rápida de cómo va el día o la semana.

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

Puedes registrar **entradas** (dinero que entra) y **salidas** (dinero que sale) que no provienen de una venta, por ejemplo: gasto menor, pago a proveedor o un ingreso extra. Agrega una **observación** para que quede claro el motivo.

### Cerrar caja

1. Presiona **Cerrar caja**.
2. Ingresa el **saldo final real** (el dinero físico que hay al cerrar).
3. El sistema compara el saldo esperado con el real, dejando constancia de las diferencias si las hay.

> Regla: no se pueden registrar ventas con la caja cerrada. Olvídate de cerrar la caja si falta facturar algo.

---

## 8. Usuarios (solo administradores)

Solo el rol **Admin** puede entrar a esta pantalla. En ella puedes:

- **Crear usuarios** con rol **Admin** o **Cajero**.
  - *Cajero*: opera caja, ventas, productos y clientes.
  - *Admin*: además puede administrar usuarios y ver el dashboard.
- **Editar** datos y rol de un usuario existente.
- **Restablecer contraseñas** cuando un usuario la olvida.
- **Eliminar usuarios** que ya no trabajen en el local (los vendidos en periodos pasados quedan intactos).

---

## 9. Trabajar desde el celular

El sistema se adapta a pantallas pequeñas:

- El menú se convierte en un **menú lateral deslizable** (botón de tres líneas).
- Las tablas se convierten en **tarjetas** apiladas para que sea fácil leerlas.
- Los modales y formularios se ajustan automáticamente.

---

## 10. Buenas prácticas diarias

- **Abre la caja** al empezar el día y **ciérrala** al terminar.
- **Registra cada venta** en el momento; no acumules "para después".
- Pide siempre el **motivo** cuando anules o retires productos.
- Mantén la **contraseña** privada y cámbiala periódicamente.
- Al final del turno, revisa en el **dashboard** el total del día para conciliar con el dinero físico.

---

## 11. ¿Algo no funciona?

| Situación | Qué hacer |
|-----------|-----------|
| "No se pudo conectar con el servidor" | Espera unos segundos y vuelve a intentar (el servicio puede tardar en despertar). |
| No puedo iniciar sesión | Verifica tu usuario y contraseña; si sigue fallando, pide que te restablezcan la clave. |
| "La caja está cerrada" | Alguien debe abrir la caja aun estando en el turno. |
| No me aparece la pantalla de usuarios | Tu rol es Cajero; necesita un Admin para ver/administrar usuarios. |
| Cometí un error en una venta | Anula la factura (con motivo) y regístrala de nuevo correctamente. |

---

*Última actualización del documento: octubre 2026.*