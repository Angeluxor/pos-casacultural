import type { DetalleFactura, Factura } from '../api/ventas'
import type { FormaPago } from '../api/types'
import { crearClaveIdempotencia } from '../lib/idempotencia'
import type { DetalleOffline, OperacionOffline, PagoOffline } from './almacen'

function ahoraIso(): string {
  return new Date().toISOString()
}

function redondear(n: number): number {
  return Math.round(n * 100) / 100
}

export function crearOperacionVenta(params: {
  usuarioId: number
  usuarioNombre: string
  turnoId: number | null
  clienteId: number | null
  nombreEventual: string | null
  detalles: DetalleOffline[]
  pagos: PagoOffline[]
  total: number
}): OperacionOffline {
  const id = crearClaveIdempotencia()
  return {
    id,
    tipo: 'venta',
    creadaEn: ahoraIso(),
    // Fecha real de la venta en el dispositivo. El backend la conserva para
    // que la venta quede en el turno y el día correctos.
    fecha: ahoraIso(),
    usuarioId: params.usuarioId,
    usuarioNombre: params.usuarioNombre,
    turnoId: params.turnoId,
    facturaId: null,
    clienteId: params.clienteId,
    nombreEventual: params.nombreEventual,
    detalles: params.detalles,
    pagos: params.pagos,
    total: params.total,
    estado: 'pendiente',
    intentos: 0,
    ultimoError: null,
    pagoRegistrado: params.pagos.length === 0,
    claveVenta: crearClaveIdempotencia(),
    clavePago: crearClaveIdempotencia(),
  }
}

export function crearOperacionPago(params: {
  usuarioId: number
  usuarioNombre: string
  turnoId: number | null
  facturaId: number
  pagos: PagoOffline[]
  total: number
}): OperacionOffline {
  return {
    id: crearClaveIdempotencia(),
    tipo: 'pago',
    creadaEn: ahoraIso(),
    fecha: ahoraIso(),
    usuarioId: params.usuarioId,
    usuarioNombre: params.usuarioNombre,
    turnoId: params.turnoId,
    facturaId: params.facturaId,
    clienteId: null,
    nombreEventual: null,
    detalles: [],
    pagos: params.pagos,
    total: params.total,
    estado: 'pendiente',
    intentos: 0,
    ultimoError: null,
    pagoRegistrado: false,
    claveVenta: crearClaveIdempotencia(),
    clavePago: crearClaveIdempotencia(),
  }
}

export function crearOperacionItem(params: {
  usuarioId: number
  usuarioNombre: string
  turnoId: number | null
  facturaId: number
  detalle: DetalleOffline
}): OperacionOffline {
  const total = redondear(params.detalle.precioUnitario * params.detalle.cantidad)
  return {
    id: crearClaveIdempotencia(),
    tipo: 'item',
    creadaEn: ahoraIso(),
    fecha: ahoraIso(),
    usuarioId: params.usuarioId,
    usuarioNombre: params.usuarioNombre,
    turnoId: params.turnoId,
    facturaId: params.facturaId,
    clienteId: null,
    nombreEventual: null,
    detalles: [params.detalle],
    pagos: [],
    total,
    estado: 'pendiente',
    intentos: 0,
    ultimoError: null,
    pagoRegistrado: true,
    claveVenta: crearClaveIdempotencia(),
    clavePago: crearClaveIdempotencia(),
    claveItem: crearClaveIdempotencia(),
  }
}

function recalcularFacturaLocal(factura: Factura): Factura {
  if (factura.estado === 'Anulada') return factura

  const total = redondear(
    factura.detalles
      .filter((d) => !d.anulado)
      .reduce((acc, d) => acc + d.subtotal, 0),
  )
  const pagado = redondear(factura.pagos.reduce((acc, p) => acc + p.valor, 0))
  const saldo = redondear(total - pagado)

  let estado: Factura['estado'] = factura.estado
  let saldoFinal = saldo
  if (saldo <= 0) {
    estado = 'Pagada'
    saldoFinal = 0
  } else if (pagado > 0) {
    estado = 'Pagado Parcial'
  } else if (factura.estado === 'Crédito') {
    estado = 'Crédito'
  } else {
    estado = 'Abierta'
  }

  return { ...factura, total, saldo: saldoFinal, estado }
}

/** Refleja localmente un ítem agregado sin conexión, sin esperar al servidor. */
export function aplicarItemAFactura(
  factura: Factura,
  detalle: DetalleOffline,
): Factura {
  if (factura.estado === 'Anulada') return factura

  const precio = redondear(detalle.precioUnitario)
  const detalles = [...factura.detalles]
  const existente = detalles.findIndex(
    (d) =>
      !d.anulado &&
      d.producto_id === detalle.productoId &&
      redondear(d.precio_unitario) === precio,
  )

  if (existente >= 0) {
    const linea = detalles[existente]
    const cantidad = linea.cantidad + detalle.cantidad
    detalles[existente] = {
      ...linea,
      cantidad,
      subtotal: redondear(precio * cantidad),
    }
  } else {
    const nuevoId = Math.min(0, ...detalles.map((d) => d.id)) - 1
    const nueva: DetalleFactura = {
      id: nuevoId,
      producto_id: detalle.productoId,
      cantidad: detalle.cantidad,
      precio_unitario: precio,
      subtotal: redondear(precio * detalle.cantidad),
      anulado: false,
    }
    detalles.push(nueva)
  }

  return recalcularFacturaLocal({ ...factura, detalles })
}

/** Aplica al vuelo los ítems que todavía están pendientes de sincronizar. */
export function facturaConItemsPendientes(
  factura: Factura,
  operaciones: OperacionOffline[],
): Factura {
  return operaciones
    .filter((op) => op.tipo === 'item' && op.facturaId === factura.id)
    .reduce(
      (actual, op) =>
        op.detalles.reduce(
          (conDetalle, detalle) => aplicarItemAFactura(conDetalle, detalle),
          actual,
        ),
      factura,
    )
}

export function contarItemsPendientesFactura(
  facturaId: number,
  operaciones: OperacionOffline[],
): number {
  return operaciones
    .filter((op) => op.tipo === 'item' && op.facturaId === facturaId)
    .reduce(
      (acc, op) =>
        acc + op.detalles.reduce((suma, detalle) => suma + detalle.cantidad, 0),
      0,
    )
}

export function pagosDesdeLineas(
  lineas: { valor: string; forma_pago: FormaPago }[],
): PagoOffline[] {
  return lineas.map((p) => ({
    valor: Number(p.valor),
    formaPago: p.forma_pago,
  }))
}
