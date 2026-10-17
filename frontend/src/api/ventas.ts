import { apiFetch, apiJson } from './client'
import type { Pagina } from './types'
import type { FormaPago } from './types'

export type EstadoFactura = 'Abierta' | 'Pagado Parcial' | 'Pagada' | 'Crédito' | 'Anulada'

export const ESTADOS_FACTURA: EstadoFactura[] = [
  'Abierta',
  'Pagado Parcial',
  'Pagada',
  'Crédito',
  'Anulada',
]

export type DetalleFactura = {
  id: number
  producto_id: number
  cantidad: number
  precio_unitario: number
  subtotal: number
  anulado: boolean
}

export type Pago = {
  id: number
  fecha: string
  valor: number
  forma_pago: FormaPago
  cajero_id: number
}

export type Factura = {
  id: number
  cliente_id: number | null
  cliente_nombre: string | null
  nombre_eventual: string | null
  vendedor_id: number
  turno_caja_id: number | null
  fecha: string
  total: number
  saldo: number
  estado: EstadoFactura
  motivo_anulacion: string | null
  fecha_anulacion: string | null
  anulada_por_id: number | null
  detalles: DetalleFactura[]
  pagos: Pago[]
}

export type FacturaCreate = {
  cliente_id?: number | null
  nombre_eventual?: string | null
  detalles: { producto_id: number; cantidad: number }[]
}

export type PagoCreate = {
  valor: number
  forma_pago: FormaPago
}

export function listarFacturasPaginado(params: {
  skip: number
  limit: number
  buscar?: string
  desde?: string
  hasta?: string
  estado?: EstadoFactura | ''
}): Promise<Pagina<Factura>> {
  const q = new URLSearchParams()
  q.set('skip', String(params.skip))
  q.set('limit', String(params.limit))
  if (params.buscar) q.set('buscar', params.buscar)
  if (params.desde) q.set('desde', params.desde)
  if (params.hasta) q.set('hasta', params.hasta)
  if (params.estado) q.set('estado', params.estado)
  return apiFetch<Pagina<Factura>>(`/api/facturas/?${q.toString()}`)
}

export function obtenerFactura(id: number): Promise<Factura> {
  return apiFetch<Factura>(`/api/facturas/${id}`)
}

export function crearFactura(data: FacturaCreate): Promise<Factura> {
  return apiJson<Factura>('/api/facturas/', 'POST', data)
}

export function asignarClienteFactura(
  id: number,
  clienteId: number,
): Promise<Factura> {
  return apiJson<Factura>(`/api/facturas/${id}/cliente`, 'PUT', { cliente_id: clienteId })
}

export function pagarFactura(
  id: number,
  data: PagoCreate | PagoCreate[],
): Promise<Factura> {
  return apiJson<Factura>(`/api/facturas/${id}/pagos`, 'POST', data)
}

export function anularFactura(id: number, motivo?: string): Promise<Factura> {
  return apiJson<Factura>(`/api/facturas/${id}/anular`, 'POST', { motivo: motivo ?? null })
}

export function agregarItemFactura(
  id: number,
  data: { producto_id: number; cantidad: number },
): Promise<Factura> {
  return apiJson<Factura>(`/api/facturas/${id}/items`, 'POST', data)
}

export function actualizarItemFactura(
  id: number,
  detalleId: number,
  cantidad: number,
): Promise<Factura> {
  return apiJson<Factura>(`/api/facturas/${id}/items/${detalleId}`, 'PUT', { cantidad })
}

export function eliminarItemFactura(id: number, detalleId: number): Promise<Factura> {
  return apiFetch<Factura>(`/api/facturas/${id}/items/${detalleId}`, { method: 'DELETE' })
}
