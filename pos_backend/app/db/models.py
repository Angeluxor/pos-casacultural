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

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    nombre = Column(String)
    hashed_password = Column(String)
    rol = Column(Enum(RolUsuario), default=RolUsuario.CAJERO)
    activo = Column(Boolean, default=True)

class TurnoCaja(Base):
    __tablename__ = "turnos_caja"
    id = Column(Integer, primary_key=True, index=True)
    usuario_apertura_id = Column(Integer, ForeignKey("usuarios.id"))
    usuario_cierre_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_apertura = Column(DateTime(timezone=True), default=get_colombia_time)
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)
    saldo_inicial = Column(Float, default=0.0)
    saldo_final_real = Column(Float, nullable=True)
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
    forma_pago = Column(Enum(FormaPago), nullable=True)
    monto = Column(Float)
    observacion = Column(String, nullable=True)

    turno = relationship("TurnoCaja", back_populates="movimientos")
    usuario = relationship("Usuario")
