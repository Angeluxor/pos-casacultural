# Novedades — POS Casi Obsceno

Resumen para el equipo de lo nuevo en la aplicación y **qué hacer según el
caso**. Está escrito en lenguaje de uso, sin detalles técnicos. Para el
historial técnico completo mira [CHANGELOG.md](CHANGELOG.md); para el paso a
paso de cada pantalla, [GUIA_DE_USO.md](GUIA_DE_USO.md).

Cada novedad indica **quién la usa**: 🧾 cajeros y meseros · 🔑 administradores.

---

## Noviembre 2026

### 🧾 Traslado efectivo ↔ banco (Caja)

**Para qué sirve:** mover dinero de un lado a otro sin que cuente como ingreso ni
como gasto.

| Si te pasa esto… | Haz esto |
| --- | --- |
| Retiraste 100.000 del banco para unas compras, te dieron vuelto y quedó en efectivo, pero ese dinero debe estar en el banco. | Caja → **Traslado efectivo ↔ banco** → «Sale de»: **Efectivo** → monto del vuelto → Registrar. |
| Necesitas efectivo en el cajón y lo sacas del banco. | **Traslado efectivo ↔ banco** → «Sale de»: **Banco** → monto → Registrar. |
| Consignaste en el banco el efectivo del día. | **Traslado efectivo ↔ banco** → «Sale de»: **Efectivo** → monto → Registrar. |

**Ten en cuenta**
- Necesita **caja abierta** y **conexión**.
- No es un gasto ni una venta: no cambia el Balance ni los reportes de ventas.
- Aparece en la tabla de movimientos con la categoría **Traslado** (puedes filtrar
  por ella) y se considera en el saldo esperado de efectivo y banco al cerrar.
- Si el monto supera lo esperado en el lado de origen, la pantalla te avisa pero
  te deja continuar: revisa que el monto sea correcto.
- ¿Te equivocaste de monto? Registra el traslado contrario por la diferencia.

---

### 🧾 Abonar al saldo total de un cliente (Ventas)

**Para qué sirve:** pagar de una vez todas las facturas pendientes de un cliente,
sin ir factura por factura.

| Si te pasa esto… | Haz esto |
| --- | --- |
| Un cliente con varias facturas a crédito viene a pagar «lo que debe». | Ventas → **Abonar saldo de cliente** → elige al cliente → ingresa el monto → Registrar. |
| El cliente paga una parte, no todo. | Igual que arriba con el monto parcial: se aplica a las facturas **más antiguas primero**; la última queda como «Pagado Parcial». |
| El cliente paga mitad en efectivo y mitad por transferencia. | Combina los medios de pago en el mismo abono. |

**Ten en cuenta**
- Necesita **caja abierta** y **conexión**.
- Si la pantalla se queda cargando, **no repitas el abono**: revisa primero las
  facturas del cliente. El sistema evita duplicados, pero conviene confirmar.

---

### 🧾 Forma de pago visible en Ventas

En el listado de ventas ahora se ve **cómo se pagó** cada factura (o los medios
combinados). Si aún no tiene pagos, aparece **Crédito**. Úsalo para cuadrar la
caja sin abrir cada factura.

---

### 🔑 Bolsillos con saldo inicial (Balance)

**Para qué sirve:** registrar dinero que **ya estaba apartado** antes de usar la
aplicación.

| Si te pasa esto… | Haz esto |
| --- | --- |
| Ya tenías, por ejemplo, el arriendo apartado y el Caja disponible sale negativo. | Balance → Bolsillos → crea el bolsillo con su **Saldo inicial** (o usa «Saldo inicial» en uno existente). |
| Vas a apartar dinero **nuevo** de la caja. | Usa **Aporte**: ese sí descuenta de efectivo/banco. |

El saldo inicial suma al reservado pero **no** descuenta de efectivo ni banco. El
historial del bolsillo distingue los movimientos iniciales.

---

### 🧾 Trabajar con mala señal o sin internet

La app se puede **instalar** y abrir sin red.

**Instalarla:** en el celular o computador, toca **Instalar app** (barra
superior). Hazlo una vez con internet.

| Lo que ves | Qué significa | Qué hacer |
| --- | --- | --- |
| **Sin conexión** | El dispositivo no tiene red. | Sigue vendiendo: las ventas y cobros se guardan en el dispositivo. |
| **El servidor está tardando** | Hay red, pero el servidor está despertando o ocupado. | Espera; reintenta solo. No es un corte de internet. Si pasa seguido, avisa al administrador. |
| **N operación(es) pendiente(s) de sincronizar** | Hay ventas o cobros guardados sin enviar. | Se envían solos al volver la señal. Puedes forzarlo con **Sincronizar ahora**. |
| Una factura dice **Venta marcada para revisión** | Al sincronizar ya no alcanzaba el stock. La venta **no se perdió**. | Revisa el stock del producto y ajústalo desde Productos. |

**Qué funciona sin red:** crear ventas, cobrar y **agregar productos** a una
factura ya abierta.
**Qué necesita red:** cambiar cantidades, quitar productos, anular, caja
(abrir, cerrar, movimientos, traslados), abonos de saldo, inventario, reportes y
administración.

**Ten en cuenta**
- **No se puede cerrar la caja** con operaciones pendientes: sincroniza primero
  y vuelve a abrir el cierre para que los saldos se recalculen.
- Los datos pendientes viven en el navegador del dispositivo. **No borres los
  datos del sitio** ni cambies de navegador antes de sincronizar.
- Si venden el mismo producto desde dos dispositivos sin red, ambas ventas se
  conservan y quedan marcadas para revisión.
- Si pasaron más de 12 horas sin conexión, vuelve a iniciar sesión con red para
  que se envíe lo pendiente.

---

### 🧾 Ventas que se quedaban en «Guardando…»

Antes, si la señal fallaba justo al guardar, la pantalla quedaba cargando y no se
sabía si la venta existía. Ahora el sistema **reintenta una vez** de forma segura
y no duplica la venta ni el cobro.

| Si te pasa esto… | Haz esto |
| --- | --- |
| Te avisa que no se pudo confirmar el cobro. | **No cobres otra vez de inmediato.** Abre Ventas y revisa si la factura ya está cobrada; recién ahí decide. |

---

### 🔑 Rendimiento (nueva pantalla)

**Para qué sirve:** saber con datos **por qué la aplicación se siente lenta**.
Solo la ve quien tenga el permiso *Ver las métricas de rendimiento* (por defecto,
los administradores).

| Si te pasa esto… | Haz esto |
| --- | --- |
| Un usuario reporta «todo está lento». | Pídele que use la app unos minutos (mejor desde el celular donde la ve lenta) y revisa **Rendimiento** → «Últimas 24 horas». |
| Quieres saber si es el servidor dormido, la base de datos o la red. | Lee el **Diagnóstico** al inicio de la pantalla: lo dice en palabras. |
| Quieres saber qué pantalla es la más lenta. | Tabla **Rutas más lentas**: ordena por el p95 (lo que tardan las peticiones más lentas). |
| Quieres ver un caso concreto de lentitud. | Tabla **Peticiones lentas recientes** (2 s o más). |

**Cómo leerla**
- **p50** = tiempo típico. **p95** = lo que tarda 1 de cada 20 peticiones.
- **Servidor** = lo que tarda la API una vez despierta. **Navegador** = lo que
  realmente espera la persona (incluye su red y el arranque del servicio). Si el
  navegador espera mucho más que el servidor, la demora no está en el código.
- Los datos se acumulan con el uso: **espera unos días** de operación normal
  antes de sacar conclusiones, y se guardan 30 días.

**Qué hacer con el resultado**
- Predominan los *arranques en frío* → el servicio gratuito se duerme: considera
  el plan de pago o un monitor externo que lo mantenga despierto.
- Predomina *base de datos* → hay consultas pesadas: pásale la ruta a quien
  desarrolla para optimizarla.
- Predomina *red del dispositivo* → el problema es la señal de quien lo usa.

---

### 🔑 Avisos de feedback por Telegram

Cuando alguien envía un comentario con el botón flotante, puede llegar un aviso a
Telegram con tipo, prioridad, autor, pantalla y enlace a la bandeja. Es opcional:
si no está configurado, el feedback funciona igual en la bandeja **Feedback**.
Para activarlo hay que configurar el bot y el chat (ver [DEPLOY.md](DEPLOY.md)).

---

## ¿Algo no funciona como se describe aquí?

Usa el **botón flotante de feedback**: elige *Bug*, cuenta
qué hacías y adjunta una captura. Llega directo a la bandeja del equipo.
