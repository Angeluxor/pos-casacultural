import { apiFetch, apiJson } from './client'
import type { Pagina } from './types'

export type FormaPagoIngreso = 'Efectivo' | 'Transferencia' | 'Crédito' | 'Donación'
export type EstadoIngreso = 'Completo' | 'Parcial' | 'Inconsistente'
export type TipoItemIngreso = 'Producto' | 'Producto nuevo' | 'Otros'

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
  proveedor: string | null
  forma_pago: FormaPagoIngreso
  total: number
  estado: EstadoIngreso
  justificacion: string | null
  observacion: string | null
  suma_items: number
  items: IngresoItem[]
}

export type IngresoCreate = {
  proveedor?: string
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
  proveedor?: string
  observacion?: string
  items?: IngresoItemUpdate[]
}

export function paginaIngresos(params: {
  skip: number
  limit: number
}): Promise<Pagina<Ingreso>> {
  const q = new URLSearchParams()
  q.set('skip', String(params.skip))
  q.set('limit', String(params.limit))
  return apiFetch<Pagina<Ingreso>>(`/api/ingresos/?${q.toString()}`)
}

export function crearIngreso(data: IngresoCreate): Promise<Ingreso> {
  return apiJson<Ingreso>('/api/ingresos/', 'POST', data)
}

export function editarIngreso(id: number, data: IngresoUpdate): Promise<Ingreso> {
  return apiJson<Ingreso>(`/api/ingresos/${id}`, 'PUT', data)
}

export function resolverIngreso(id: number, justificacion: string): Promise<Ingreso> {
  return apiJson<Ingreso>(`/api/ingresos/${id}/resolver`, 'POST', { justificacion })
}