from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
import enum
from .base_class import Base
from app.core.timezone import get_colombia_time

class EstadoFactura(str, enum.Enum):
    ABIERTA = "Abierta"
    PAGADO_PARCIAL = "Pagado Parcial"
    PAGADA = "Pagada"
    # Las facturas con saldo pendiente al cerrar la caja pasan a "Crédito"
    # (deuda del cliente). Sigue admitiendo abonos posteriores.
    CREDITO = "Crédito"
    ANULADA = "Anulada"

class FormaPago(str, enum.Enum):
    EFECTIVO = "Efectivo"
    TRANSFERENCIA = "Transferencia"
    TARJETA = "Tarjeta"
    OTRO = "Otro"
    # Abono a una factura a crédito descontado de la nómina de un empleado. No
    # entra a caja como efectivo/banco: es una compensación, no un cobro.
    NOMINA = "Nómina"

class TipoMovimientoCaja(str, enum.Enum):
    ENTRADA = "Entrada"
    SALIDA = "Salida"
    APERTURA = "Apertura"
    CIERRE = "Cierre"

class TipoMovimientoBolsillo(str, enum.Enum):
    """Movimientos virtuales de un bolsillo de gastos vitales.

    Un aporte aparta dinero que sigue en caja/banco; un retiro lo vuelve a
    dejar disponible. No son entradas ni salidas reales de efectivo.
    """

    APORTE = "Aporte"
    RETIRO = "Retiro"

class RolUsuario(str, enum.Enum):
    ADMIN = "Admin"
    CAJERO = "Cajero"
    # Rol de salón: toma pedidos y cobra, sin acceso a administración.
    MESERO = "Mesero"

class TipoMovimientoInventario(str, enum.Enum):
    ENTRADA_COMPRA = "Entrada por Compra"
    SALIDA_VENTA = "Salida por Venta"
    DEVOLUCION = "Devolución"
    AJUSTE = "Ajuste"
    # Reversión del stock cuando se anula un ingreso de inventario.
    SALIDA_ANULACION = "Salida por anulación"

class MotivoAjuste(str, enum.Enum):
    DERRAMA = "Derrama o pérdida"
    MAL_CONTEO = "Mal conteo"
    OTRO = "Otro"

class FormaPagoIngreso(str, enum.Enum):
    EFECTIVO = "Efectivo"
    TRANSFERENCIA = "Transferencia"
    CREDITO = "Crédito"
    DONACION = "Donación"

class FuentePagoIngreso(str, enum.Enum):
    """De dónde sale el dinero o cómo se registra el ingreso.

    ``CAJA`` exige un turno abierto y, en efectivo/transferencia, genera una
    salida de caja. ``BALANCE`` no toca la caja: se usa para compras ya pagadas
    por fuera del POS o para saldos iniciales; el efectivo/transferencia queda
    como pagado por fuera y el crédito como cuenta por pagar.
    """

    CAJA = "Caja activa"
    BALANCE = "Balance general"

class EstadoIngreso(str, enum.Enum):
    COMPLETO = "Completo"
    PARCIAL = "Parcial"
    INCONSISTENTE = "Inconsistente"

class TipoItemIngreso(str, enum.Enum):
    PRODUCTO = "Producto"
    PRODUCTO_NUEVO = "Producto nuevo"
    OTROS = "Otros"

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    nombre = Column(String)
    hashed_password = Column(String)
    rol = Column(Enum(RolUsuario), default=RolUsuario.CAJERO)
    activo = Column(Boolean, default=True)
    # Versión de los tokens de este usuario. Al cambiar la contraseña se
    # incrementa y los tokens emitidos antes dejan de ser válidos (revocación).
    token_version = Column(Integer, default=0, nullable=False)
    # Cliente al que se vincula este usuario, por ejemplo para descontar de su
    # nómina las compras a crédito. La unicidad garantiza el vínculo uno a uno:
    # un cliente no puede quedar vinculado a dos usuarios.
    cliente_id = Column(
        Integer,
        ForeignKey("clientes.id", ondelete="SET NULL"),
        unique=True,
        index=True,
        nullable=True,
    )

    cliente = relationship("Cliente")

    @property
    def cliente_nombre(self) -> str | None:
        """Nombre del cliente vinculado (para las respuestas de la API)."""
        return self.cliente.nombre if self.cliente else None

class PermisoRol(Base):
    """Permisos configurados para un rol (solo Cajero y Mesero).

    El rol Admin siempre tiene todos los permisos y no se guarda aquí. Si un rol
    no tiene fila se usan los permisos por defecto de `app/core/permisos.py`.
    """
    __tablename__ = "permisos_rol"
    id = Column(Integer, primary_key=True, index=True)
    rol = Column(Enum(RolUsuario), index=True, unique=True, nullable=False)
    # Lista de claves de permiso concedidas (ver `app/core/permisos.py`).
    permisos = Column(JSON, nullable=False, default=list)

class Feedback(Base):
    """Comentarios, ideas y reportes de error enviados desde la aplicación.

    La captura se guarda en la base de datos (no en disco) para que viaje con
    el resto del registro y solo se sirva por un endpoint autenticado. El
    contexto técnico es un JSON pequeño (ruta, navegador, versión, etc.) que
    ayuda a reproducir el problema sin pedirle al usuario que lo escriba.
    """

    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Foto del nombre al momento de enviar: el feedback sigue siendo legible
    # aunque luego se renombre o desactive la cuenta.
    usuario_nombre = Column(String, nullable=False)
    tipo = Column(String, nullable=False, index=True)
    comentario = Column(Text, nullable=False)
    contexto = Column(JSON, nullable=False, default=dict)
    estado = Column(String, nullable=False, default="Nuevo", index=True)
    prioridad = Column(String, nullable=False, default="Media", index=True)
    # Etiquetas simples separadas por coma; se muestran como chips en la UI.
    etiquetas = Column(String, nullable=True)
    responsable_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notas_internas = Column(Text, nullable=True)
    # ``tiene_captura`` evita cargar el binario en los listados de la bandeja.
    tiene_captura = Column(Boolean, nullable=False, default=False)
    captura = Column(LargeBinary, nullable=True)
    captura_mime = Column(String, nullable=True)
    captura_nombre = Column(String, nullable=True)
    creado_en = Column(
        DateTime(timezone=True), default=get_colombia_time, nullable=False, index=True
    )
    actualizado_en = Column(
        DateTime(timezone=True),
        default=get_colombia_time,
        onupdate=get_colombia_time,
        nullable=False,
    )
    resuelto_en = Column(DateTime(timezone=True), nullable=True)

    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    responsable = relationship("Usuario", foreign_keys=[responsable_id])

    @property
    def responsable_nombre(self) -> str | None:
        if not self.responsable:
            return None
        return self.responsable.nombre or self.responsable.username or "Usuario"


class TurnoCaja(Base):
    __tablename__ = "turnos_caja"
    id = Column(Integer, primary_key=True, index=True)
    usuario_apertura_id = Column(Integer, ForeignKey("usuarios.id"))
    usuario_cierre_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_apertura = Column(DateTime(timezone=True), default=get_colombia_time)
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)
    # La caja se lleva desdoblada en dos bolsillos: efectivo y banco
    # (banco agrupa transferencia, tarjeta y "otro").
    saldo_inicial_efectivo = Column(Float, default=0.0, nullable=False)
    saldo_inicial_banco = Column(Float, default=0.0, nullable=False)
    saldo_final_real_efectivo = Column(Float, nullable=True)
    saldo_final_real_banco = Column(Float, nullable=True)
    abierta = Column(Boolean, default=True)

    usuario_apertura = relationship("Usuario", foreign_keys=[usuario_apertura_id])
    usuario_cierre = relationship("Usuario", foreign_keys=[usuario_cierre_id])
    movimientos = relationship("RegistroCaja", back_populates="turno")

class Cliente(Base):
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    documento = Column(String, unique=True, index=True, nullable=True)
    celular = Column(String, nullable=True)
    correo = Column(String, nullable=True)
    # Marca al único registro genérico "Cliente eventual" (reemplaza al
    # antiguo "Consumidor final"). No se gestiona como un cliente normal.
    es_eventual = Column(Boolean, default=False, nullable=False)
    # passive_deletes="all": al borrar el cliente, SQLAlchemy no carga ni pone
    # en NULL las facturas; deja que la FK con ON DELETE RESTRICT de la base de
    # datos rechace la operación si existen ventas asociadas.
    facturas = relationship(
        "Factura", back_populates="cliente", passive_deletes="all"
    )

class Producto(Base):
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True)
    nombre = Column(String, index=True)
    precio = Column(Float)
    stock = Column(Integer, default=0)
    # True cuando la unidad de compra es la misma que la de venta. Solo en ese
    # caso tiene sentido comparar directamente el costo de compra con el precio
    # de venta (relación CMV/precio 1:1).
    misma_unidad_compra_venta = Column(Boolean, default=True, nullable=False)

    movimientos_kardex = relationship("Kardex", back_populates="producto")
    receta = relationship(
        "Receta",
        back_populates="producto",
        uselist=False,
        cascade="all, delete-orphan",
    )
    costos_manuales = relationship(
        "CostoManual",
        back_populates="producto",
        cascade="all, delete-orphan",
    )

class Kardex(Base):
    __tablename__ = "kardex"
    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    fecha = Column(DateTime(timezone=True), default=get_colombia_time)
    tipo_movimiento = Column(Enum(TipoMovimientoInventario))
    cantidad = Column(Integer)
    saldo_stock = Column(Integer)
    referencia = Column(String, nullable=True)
    # Solo aplican a los movimientos manuales de tipo Ajuste.
    motivo = Column(Enum(MotivoAjuste), nullable=True)
    motivo_detalle = Column(String, nullable=True)

    producto = relationship("Producto", back_populates="movimientos_kardex")
    usuario = relationship("Usuario")

class Factura(Base):
    __tablename__ = "facturas"
    id = Column(Integer, primary_key=True, index=True)
    # RESTRICT: la base de datos impide borrar un cliente con facturas. El
    # historial de ventas es la razón de ser del POS y no debe quedar huérfano.
    cliente_id = Column(
        Integer, ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=True
    )
    vendedor_id = Column(Integer, ForeignKey("usuarios.id"))
    fecha = Column(DateTime(timezone=True), default=get_colombia_time)
    total = Column(Float, default=0.0)
    saldo = Column(Float, default=0.0)
    estado = Column(Enum(EstadoFactura), default=EstadoFactura.ABIERTA)
    # Turno de caja en el que se registró la venta (para el paso a crédito al
    # cerrar caja). Puede ser nulo en ventas hechas sin caja abierta.
    turno_caja_id = Column(Integer, ForeignKey("turnos_caja.id"), nullable=True)
    # Nombre temporal/eventual que da el cajero cuando el cliente no se
    # registra (solo texto; no crea un cliente real).
    nombre_eventual = Column(String, nullable=True)

    # Trazabilidad de anulación
    motivo_anulacion = Column(String, nullable=True)
    fecha_anulacion = Column(DateTime(timezone=True), nullable=True)
    anulada_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    cliente = relationship("Cliente", back_populates="facturas")
    turno = relationship("TurnoCaja")
    vendedor = relationship("Usuario", foreign_keys=[vendedor_id])
    anulada_por = relationship("Usuario", foreign_keys=[anulada_por_id])
    detalles = relationship("DetalleFactura", back_populates="factura")
    pagos = relationship("Pago", back_populates="factura")

    @property
    def cliente_nombre(self) -> str | None:
        """Nombre a mostrar: el temporal/eventual si existe, si no el del cliente."""
        if self.nombre_eventual:
            return self.nombre_eventual
        return self.cliente.nombre if self.cliente else None

class DetalleFactura(Base):
    __tablename__ = "detalles_factura"
    id = Column(Integer, primary_key=True, index=True)
    factura_id = Column(Integer, ForeignKey("facturas.id"))
    producto_id = Column(Integer, ForeignKey("productos.id"))
    cantidad = Column(Integer, default=1)
    precio_unitario = Column(Float)
    subtotal = Column(Float)
    # Un producto retirado de la factura no se borra: se marca para conservar
    # la traza (control de fraude) y se descuenta del total.
    anulado = Column(Boolean, default=False, nullable=False)

    factura = relationship("Factura", back_populates="detalles")
    producto = relationship("Producto")

class Pago(Base):
    __tablename__ = "pagos"
    id = Column(Integer, primary_key=True, index=True)
    factura_id = Column(Integer, ForeignKey("facturas.id"))
    cajero_id = Column(Integer, ForeignKey("usuarios.id"))
    fecha = Column(DateTime(timezone=True), default=get_colombia_time)
    valor = Column(Float)
    forma_pago = Column(Enum(FormaPago))
    # Evento de auditoría al que pertenece el abono (solo para Nómina).
    descuento_nomina_id = Column(
        Integer,
        ForeignKey("descuentos_nomina.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    factura = relationship("Factura", back_populates="pagos")
    cajero = relationship("Usuario")
    descuento_nomina = relationship("DescuentoNomina", back_populates="pagos")


class DescuentoNomina(Base):
    """Evento de auditoría de un descuento de nómina.

    Guarda una foto del empleado, el cliente y el usuario que aplicó el
    descuento. Así el historial sigue siendo legible aunque luego se renombre el
    cliente, se desvincule el usuario o se elimine la cuenta de acceso.
    """

    __tablename__ = "descuentos_nomina"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    usuario_nombre = Column(String, nullable=False)
    cliente_id = Column(
        Integer, ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True
    )
    cliente_nombre = Column(String, nullable=False)
    registrado_por_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    registrado_por_nombre = Column(String, nullable=False)
    fecha = Column(DateTime(timezone=True), default=get_colombia_time)
    monto = Column(Float, nullable=False)
    saldo_pendiente = Column(Float, nullable=False)
    facturas_afectadas = Column(Integer, nullable=False, default=0)
    nota = Column(String, nullable=True)

    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    registrado_por = relationship("Usuario", foreign_keys=[registrado_por_id])
    cliente = relationship("Cliente")
    pagos = relationship("Pago", back_populates="descuento_nomina")

class RegistroCaja(Base):
    __tablename__ = "caja"
    id = Column(Integer, primary_key=True, index=True)
    turno_caja_id = Column(Integer, ForeignKey("turnos_caja.id"))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    fecha = Column(DateTime(timezone=True), default=get_colombia_time)
    tipo = Column(Enum(TipoMovimientoCaja))
    referencia = Column(String)
    forma_pago = Column(Enum(FormaPago), nullable=False)
    monto = Column(Float)
    observacion = Column(String, nullable=True)
    # Clasificación del movimiento (p. ej. Aporte cultural, Arriendo). Los
    # movimientos anteriores a esta función quedan sin categoría.
    categoria = Column(String, nullable=True, index=True)

    turno = relationship("TurnoCaja", back_populates="movimientos")
    usuario = relationship("Usuario")

class Bolsillo(Base):
    """Bolsillo virtual para apartar dinero de la liquidez diaria.

    El dinero no sale de la caja: el bolsillo solo marca una parte del saldo
    como reservada para gastos vitales. El saldo se calcula siempre desde sus
    movimientos para no guardar valores desactualizados.
    """

    __tablename__ = "bolsillos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False, index=True)
    descripcion = Column(String, nullable=True)
    activo = Column(Boolean, default=True, nullable=False, index=True)
    fecha_creacion = Column(DateTime(timezone=True), default=get_colombia_time, nullable=False)
    creado_por_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )

    movimientos = relationship(
        "BolsilloMovimiento",
        back_populates="bolsillo",
        cascade="all, delete-orphan",
        order_by="BolsilloMovimiento.fecha",
    )
    creado_por = relationship("Usuario")

class BolsilloMovimiento(Base):
    """Aporte o retiro virtual de un bolsillo."""

    __tablename__ = "bolsillo_movimientos"
    __table_args__ = (
        Index("ix_bolsillo_movimientos_bolsillo_fecha", "bolsillo_id", "fecha"),
    )

    id = Column(Integer, primary_key=True, index=True)
    bolsillo_id = Column(
        Integer, ForeignKey("bolsillos.id", ondelete="CASCADE"), nullable=False
    )
    fecha = Column(DateTime(timezone=True), default=get_colombia_time, nullable=False)
    tipo = Column(Enum(TipoMovimientoBolsillo), nullable=False)
    monto = Column(Float, nullable=False)
    nota = Column(String, nullable=True)
    usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )

    bolsillo = relationship("Bolsillo", back_populates="movimientos")
    usuario = relationship("Usuario")

    @property
    def usuario_nombre(self) -> str | None:
        return self.usuario.nombre if self.usuario else None

class Proveedor(Base):
    __tablename__ = "proveedores"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False, index=True)
    documento = Column(String, unique=True, index=True, nullable=True)
    celular = Column(String, nullable=True)
    correo = Column(String, nullable=True)

    ingresos = relationship("IngresoInventario", back_populates="proveedor_rel")

class IngresoInventario(Base):
    __tablename__ = "ingresos_inventario"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime(timezone=True), default=get_colombia_time)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    # El ingreso queda atado al turno de caja abierto cuando se registra desde
    # la caja. En modo balance general no hay turno asociado.
    turno_caja_id = Column(Integer, ForeignKey("turnos_caja.id"), nullable=True)
    # Fuente de pago/registro: caja activa o balance general.
    fuente_pago = Column(
        Enum(FuentePagoIngreso),
        default=FuentePagoIngreso.CAJA,
        nullable=False,
    )
    proveedor_id = Column(
        Integer,
        ForeignKey("proveedores.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    forma_pago = Column(Enum(FormaPagoIngreso))
    # Total declarado del ingreso: obligatorio y no editable después.
    total = Column(Float)
    estado = Column(Enum(EstadoIngreso), default=EstadoIngreso.PARCIAL)
    # Justificación que deja un administrador al resolver un ingreso inconsistente.
    justificacion = Column(String, nullable=True)
    observacion = Column(String, nullable=True)
    # Control de pago para las compras a crédito. Las compras pagadas de
    # contado quedan con ``pagado=True`` desde su creación.
    pagado = Column(Boolean, default=False, nullable=False)
    fecha_pago = Column(DateTime(timezone=True), nullable=True)
    pagado_por_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Forma en que se pagó una compra a crédito (Efectivo/Transferencia).
    forma_pago_pago = Column(Enum(FormaPago), nullable=True)

    # Anulación: un ingreso anulado se conserva para auditoría, pero deja de
    # contar en inventario, caja, costos y cuentas por pagar.
    anulada = Column(Boolean, default=False, nullable=False, index=True)
    motivo_anulacion = Column(String, nullable=True)
    fecha_anulacion = Column(DateTime(timezone=True), nullable=True)
    anulada_por_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    turno = relationship("TurnoCaja")
    pagado_por = relationship("Usuario", foreign_keys=[pagado_por_id])
    anulada_por = relationship("Usuario", foreign_keys=[anulada_por_id])
    proveedor_rel = relationship("Proveedor", back_populates="ingresos")
    items = relationship(
        "IngresoInventarioItem",
        back_populates="ingreso",
        cascade="all, delete-orphan",
        order_by="IngresoInventarioItem.id",
    )

    @property
    def suma_items(self) -> float:
        """Valor acumulado de las líneas (para el estado y la vista)."""
        return round(sum(item.valor or 0.0 for item in self.items), 2)

    @property
    def proveedor(self) -> str | None:
        """Nombre del proveedor (compatibilidad con respuestas y reportes)."""
        return self.proveedor_rel.nombre if self.proveedor_rel else None

    @property
    def pagado_por_nombre(self) -> str | None:
        return self.pagado_por.nombre if self.pagado_por else None

    @property
    def anulada_por_nombre(self) -> str | None:
        return self.anulada_por.nombre if self.anulada_por else None

    @property
    def estado_pago(self) -> str:
        """Estado legible para la lista y el detalle de ingresos."""
        if self.anulada:
            return "No aplica"
        if self.forma_pago == FormaPagoIngreso.CREDITO:
            return "Pagado" if self.pagado else "Pendiente"
        if self.forma_pago == FormaPagoIngreso.DONACION:
            return "No aplica"
        return "Pagado"

class IngresoInventarioItem(Base):
    __tablename__ = "ingresos_inventario_items"
    id = Column(Integer, primary_key=True, index=True)
    ingreso_id = Column(Integer, ForeignKey("ingresos_inventario.id"))
    tipo = Column(Enum(TipoItemIngreso))
    # Producto existente o el creado a partir de un "producto nuevo".
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=True)
    # Nombre del producto nuevo o concepto del ítem "Otros".
    concepto = Column(String, nullable=True)
    # Cantidad total en unidades de venta (el stock y el kardex usan esta
    # cifra, no la cantidad de cajas o paquetes).
    cantidad = Column(Integer, nullable=True)
    # Compra por formato: por ejemplo 2 cajas de 12 unidades. ``cantidad``
    # guarda 24 y estos campos conservan cómo se digitó la compra para poder
    # mostrarla y auditarla. Son nulos cuando se compra por unidad.
    cantidad_formatos = Column(Integer, nullable=True)
    unidades_por_formato = Column(Integer, nullable=True)
    costo_formato = Column(Float, nullable=True)
    # Costo unitario opcional: se puede completar después al editar el ingreso.
    # Si la compra fue por formato, se calcula como costo_formato / unidades
    # y se conserva con más decimales que el dinero (es un valor derivado).
    costo_unitario = Column(Float, nullable=True)
    # Valor de la línea. Para "Otros" es el valor indicado; para productos es
    # el monto real de la compra (cantidad * costo_unitario, o el costo de los
    # formatos). Es la fuente autoritativa para totales y promedios; queda nulo
    # mientras no se conozca el costo.
    valor = Column(Float, nullable=True)

    ingreso = relationship("IngresoInventario", back_populates="items")
    producto = relationship("Producto")


class Receta(Base):
    """Receta estándar de un producto transformado (preparación).

    ``rendimiento`` es cuántas unidades vendibles produce la receta completa.
    El costo unitario de la preparación es el costo total de los insumos
    dividido por el rendimiento.
    """

    __tablename__ = "recetas"
    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(
        Integer,
        ForeignKey("productos.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    rendimiento = Column(Float, nullable=False, default=1.0)
    notas = Column(String, nullable=True)

    producto = relationship("Producto", back_populates="receta")
    items = relationship(
        "RecetaItem",
        back_populates="receta",
        cascade="all, delete-orphan",
        order_by="RecetaItem.id",
    )


class RecetaItem(Base):
    __tablename__ = "receta_items"
    __table_args__ = (
        UniqueConstraint(
            "receta_id", "producto_id", name="uq_receta_items_receta_producto"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    receta_id = Column(
        Integer, ForeignKey("recetas.id", ondelete="CASCADE"), nullable=False
    )
    producto_id = Column(
        Integer,
        ForeignKey("productos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cantidad = Column(Float, nullable=False)

    receta = relationship("Receta", back_populates="items")
    producto = relationship("Producto")


class CostoManual(Base):
    """Costo unitario registrado a mano para un insumo.

    El registro más reciente (por fecha y luego por id) es el costo manual
    vigente y reemplaza al promedio ponderado de las compras.
    """

    __tablename__ = "costos_manuales"
    __table_args__ = (
        Index("ix_costos_manuales_producto_fecha", "producto_id", "fecha"),
    )

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(
        Integer, ForeignKey("productos.id", ondelete="CASCADE"), nullable=False
    )
    fecha = Column(DateTime(timezone=True), default=get_colombia_time, nullable=False)
    costo_unitario = Column(Float, nullable=False)
    nota = Column(String, nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    producto = relationship("Producto", back_populates="costos_manuales")
    usuario = relationship("Usuario")
