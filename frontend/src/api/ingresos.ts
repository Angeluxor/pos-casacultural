import { apiFetch, apiJson } from './client'
import type { FormaPago, Pagina } from './types'

export type FormaPagoIngreso = 'Efectivo' | 'Transferencia' | 'Crédito' | 'Donación'
export type FuentePagoIngreso = 'Caja activa' | 'Balance general'
export type EstadoIngreso = 'Completo' | 'Parcial' | 'Inconsistente'
export type TipoItemIngreso = 'Producto' | 'Producto nuevo' | 'Otros'

export const FUENTES_PAGO_INGRESO: FuentePagoIngreso[] = [
  'Caja activa',
  'Balance general',
]

export const FORMAS_PAGO_INGRESO: FormaPagoIngreso[] = [
  'Efectivo',
  'Transferencia',
  'Crédito',
  'Donación',
]

export const TIPOS_ITEM_INGRESO: TipoItemIngreso[] = ['Producto', 'Producto nuevo', 'Otros']

export type IngresoItem = {
  id: number
  ingreso_id: number
  tipo: TipoItemIngreso
  producto_id: number | null
  concepto: string | null
  cantidad: number | null
  costo_unitario: number | null
  valor: number | null
}

export type IngresoItemCreate = {
  tipo: TipoItemIngreso
  producto_id?: number
  concepto?: string
  cantidad?: number
  costo_unitario?: number
  valor?: number
  precio?: number
}

export type Ingreso = {
  id: number
  fecha: string
  usuario_id: number
  turno_caja_id: number | null
  fuente_pago: FuentePagoIngreso
  proveedor_id: number | null
  proveedor: string | null
  forma_pago: FormaPagoIngreso
  total: number
  estado: EstadoIngreso
  justificacion: string | null
  observacion: string | null
  suma_items: number
  pagado: boolean
  estado_pago: 'Pagado' | 'Pendiente' | 'No aplica'
  fecha_pago: string | null
  pagado_por_id: number | null
  pagado_por_nombre: string | null
  forma_pago_pago: FormaPago | null
  items: IngresoItem[]
}

export type FormaPagoCredito = 'Efectivo' | 'Transferencia'

export type IngresoCreate = {
  proveedor_id?: number | null
  proveedor?: string
  fuente_pago?: FuentePagoIngreso
  forma_pago: FormaPagoIngreso
  total: number
  observacion?: string
  items: IngresoItemCreate[]
}

export type IngresoItemUpdate = {
  id: number
  costo_unitario?: number
}

export type IngresoUpdate = {
  proveedor_id?: number | null
  proveedor?: string
  observacion?: string
  items?: IngresoItemUpdate[]
}

export function paginaIngresos(params: {
  skip: number
  limit: number
  desde?: string
  hasta?: string
  orden?: string
  direccion?: string
}): Promise<Pagina<Ingreso>> {
  const q = new URLSearchParams()
  q.set('skip', String(params.skip))
  q.set('limit', String(params.limit))
  if (params.desde) q.set('desde', params.desde)
  if (params.hasta) q.set('hasta', params.hasta)
  if (params.orden) q.set('orden', params.orden)
  if (params.direccion) q.set('direccion', params.direccion)
  return apiFetch<Pagina<Ingreso>>(`/api/ingresos/?${q.toString()}`)
}

export function crearIngreso(data: IngresoCreate): Promise<Ingreso> {
  return apiJson<Ingreso>('/api/ingresos/', 'POST', data)
}

export function obtenerIngreso(id: number): Promise<Ingreso> {
  return apiFetch<Ingreso>(`/api/ingresos/${id}`)
}

export function editarIngreso(id: number, data: IngresoUpdate): Promise<Ingreso> {
  return apiJson<Ingreso>(`/api/ingresos/${id}`, 'PUT', data)
}

export function pagarIngreso(
  id: number,
  forma_pago: FormaPagoCredito,
): Promise<Ingreso> {
  return apiJson<Ingreso>(`/api/ingresos/${id}/pagar`, 'POST', { forma_pago })
}

export function resolverIngreso(id: number, justificacion: string): Promise<Ingreso> {
  return apiJson<Ingreso>(`/api/ingresos/${id}/resolver`, 'POST', { justificacion })
}