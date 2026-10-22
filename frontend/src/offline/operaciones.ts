import type { FormaPago } from '../api/types'
import { crearClaveIdempotencia } from '../lib/idempotencia'
import type { DetalleOffline, OperacionOffline, PagoOffline } from './almacen'

function ahoraIso(): string {
  return new Date().toISOString()
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

export function pagosDesdeLineas(
  lineas: { valor: string; forma_pago: FormaPago }[],
): PagoOffline[] {
  return lineas.map((p) => ({
    valor: Number(p.valor),
    formaPago: p.forma_pago,
  }))
}
