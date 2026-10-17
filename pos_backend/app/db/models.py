from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
import enum
from .base_class import Base
from app.core.timezone import get_colombia_time

class EstadoFactura(str, enum.Enum):
    PENDIENTE = "Pendiente"
    PAGADO_PARCIAL = "Pagado Parcial"
    PAGADA = "Pagada"
    ANULADA = "Anulada"

class FormaPago(str, enum.Enum):
    EFECTIVO = "Efectivo"
    TRANSFERENCIA = "Transferencia"
    TARJETA = "Tarjeta"
    OTRO = "Otro"

class TipoMovimientoCaja(str, enum.Enum):
    ENTRADA = "Entrada"
    SALIDA = "Salida"
    APERTURA = "Apertura"
    CIERRE = "Cierre"

class RolUsuario(str, enum.Enum):
    ADMIN = "Admin"
    CAJERO = "Cajero"

class TipoMovimientoInventario(str, enum.Enum):
    ENTRADA_COMPRA = "Entrada por Compra"
    SALIDA_VENTA = "Salida por Venta"
    DEVOLUCION = "Devolución"
    AJUSTE = "Ajuste"

class MotivoAjuste(str, enum.Enum):
    DERRAMA = "Derrama o pérdida"
    MAL_CONTEO = "Mal conteo"
    OTRO = "Otro"

class FormaPagoIngreso(str, enum.Enum):
    EFECTIVO = "Efectivo"
    TRANSFERENCIA = "Transferencia"
    CREDITO = "Crédito"
    DONACION = "Donación"

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
    facturas = relationship("Factura", back_populates="cliente")

class Producto(Base):
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True)
    nombre = Column(String, index=True)
    precio = Column(Float)
    stock = Column(Integer, default=0)

    movimientos_kardex = relationship("Kardex", back_populates="producto")

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
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    vendedor_id = Column(Integer, ForeignKey("usuarios.id"))
    fecha = Column(DateTime(timezone=True), default=get_colombia_time)
    total = Column(Float, default=0.0)
    saldo = Column(Float, default=0.0)
    estado = Column(Enum(EstadoFactura), default=EstadoFactura.PENDIENTE)

    # Trazabilidad de anulación
    motivo_anulacion = Column(String, nullable=True)
    fecha_anulacion = Column(DateTime(timezone=True), nullable=True)
    anulada_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    cliente = relationship("Cliente", back_populates="facturas")
    vendedor = relationship("Usuario", foreign_keys=[vendedor_id])
    anulada_por = relationship("Usuario", foreign_keys=[anulada_por_id])
    detalles = relationship("DetalleFactura", back_populates="factura")
    pagos = relationship("Pago", back_populates="factura")

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

    factura = relationship("Factura", back_populates="pagos")
    cajero = relationship("Usuario")

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

    turno = relationship("TurnoCaja", back_populates="movimientos")
    usuario = relationship("Usuario")

class IngresoInventario(Base):
    __tablename__ = "ingresos_inventario"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime(timezone=True), default=get_colombia_time)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    # El ingreso queda atado al turno de caja abierto cuando se registra.
    turno_caja_id = Column(Integer, ForeignKey("turnos_caja.id"), nullable=True)
    proveedor = Column(String, nullable=True)
    forma_pago = Column(Enum(FormaPagoIngreso))
    # Total declarado del ingreso: obligatorio y no editable después.
    total = Column(Float)
    estado = Column(Enum(EstadoIngreso), default=EstadoIngreso.PARCIAL)
    # Justificación que deja un administrador al resolver un ingreso inconsistente.
    justificacion = Column(String, nullable=True)
    observacion = Column(String, nullable=True)

    usuario = relationship("Usuario")
    turno = relationship("TurnoCaja")
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

class IngresoInventarioItem(Base):
    __tablename__ = "ingresos_inventario_items"
    id = Column(Integer, primary_key=True, index=True)
    ingreso_id = Column(Integer, ForeignKey("ingresos_inventario.id"))
    tipo = Column(Enum(TipoItemIngreso))
    # Producto existente o el creado a partir de un "producto nuevo".
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=True)
    # Nombre del producto nuevo o concepto del ítem "Otros".
    concepto = Column(String, nullable=True)
    cantidad = Column(Integer, nullable=True)
    # Costo unitario opcional: se puede completar después al editar el ingreso.
    costo_unitario = Column(Float, nullable=True)
    # Valor de la línea. Para "Otros" es el valor indicado; para productos es
    # cantidad * costo_unitario y queda nulo mientras no se conozca el costo.
    valor = Column(Float, nullable=True)

    ingreso = relationship("IngresoInventario", back_populates="items")
    producto = relationship("Producto")
