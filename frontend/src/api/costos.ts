import { apiFetch, apiJson } from './client'

export type ResumenCosto = {
  producto_id: number
  codigo: string
  nombre: string
  precio: number
  stock: number
  misma_unidad_compra_venta: boolean
  tiene_receta: boolean
  mostrar_cmv: boolean
  costo_vigente: number | null
  origen_costo: string | null
  costo_completo: boolean
  faltantes: string[]
  mejor_precio_6s: number | null
  mejor_proveedor: string | null
  mejor_fecha: string | null
  mejor_origen: string | null
  variacion_6s: number | null
  puntos_6s: number
  cmv_pct: number | null
  margen: number | null
  margen_pct: number | null
}

export type HistorialCosto = {
  fecha: string
  costo_unitario: number
  origen: string
  cantidad: number | null
  proveedor: string | null
  referencia: string | null
  nota: string | null
}

export type InsumoOpcion = {
  producto_id: number
  codigo: string
  nombre: string
  precio: number
  costo: number | null
  origen: string | null
  tiene_receta: boolean
  completo: boolean
  faltantes: string[]
}

export type RecetaItem = {
  producto_id: number
  codigo: string
  nombre: string
  cantidad: number
  costo_unitario: number | null
  subtotal: number | null
  origen: string | null
}

export type Receta = {
  producto_id: number
  codigo: string
  nombre: string
  precio: number
  rendimiento: number
  notas: string | null
  costo_total: number | null
  costo_unitario: number | null
  completo: boolean
  faltantes: string[]
  cmv_pct: number | null
  margen: number | null
  margen_pct: number | null
  items: RecetaItem[]
}

export type RecetaUpsert = {
  rendimiento: number
  notas?: string | null
  items: { producto_id: number; cantidad: number }[]
}

export type CostoManual = {
  id: number
  producto_id: number
  producto_codigo: string
  producto_nombre: string
  fecha: string
  costo_unitario: number
  nota: string | null
  usuario_id: number | null
  usuario_nombre: string | null
}

export type CostoManualCreate = {
  producto_id: number
  fecha?: string | null
  costo_unitario: number
  nota?: string | null
}

export function listarResumenCostos(buscar?: string): Promise<ResumenCosto[]> {
  const q = new URLSearchParams()
  if (buscar) q.set('buscar', buscar)
  const sufijo = q.toString() ? `?${q.toString()}` : ''
  return apiFetch<ResumenCosto[]>(`/api/costos/resumen${sufijo}`)
}

export function historialProducto(
  productoId: number,
  params: { desde?: string; hasta?: string } = {},
): Promise<HistorialCosto[]> {
  const q = new URLSearchParams()
  if (params.desde) q.set('desde', params.desde)
  if (params.hasta) q.set('hasta', params.hasta)
  const sufijo = q.toString() ? `?${q.toString()}` : ''
  return apiFetch<HistorialCosto[]>(
    `/api/costos/productos/${productoId}/historial${sufijo}`,
  )
}

export function listarInsumos(): Promise<InsumoOpcion[]> {
  return apiFetch<InsumoOpcion[]>('/api/costos/insumos')
}

export function listarRecetas(): Promise<Receta[]> {
  return apiFetch<Receta[]>('/api/costos/recetas')
}

export function obtenerReceta(productoId: number): Promise<Receta> {
  return apiFetch<Receta>(`/api/costos/recetas/${productoId}`)
}

export function guardarReceta(
  productoId: number,
  datos: RecetaUpsert,
): Promise<Receta> {
  return apiJson<Receta>(`/api/costos/recetas/${productoId}`, 'PUT', datos)
}

export function eliminarReceta(productoId: number): Promise<void> {
  return apiFetch<void>(`/api/costos/recetas/${productoId}`, { method: 'DELETE' })
}

export function listarCostosManuales(): Promise<CostoManual[]> {
  return apiFetch<CostoManual[]>('/api/costos/manuales')
}

export function crearCostoManual(datos: CostoManualCreate): Promise<CostoManual> {
  return apiJson<CostoManual>('/api/costos/manuales', 'POST', datos)
}

export function eliminarCostoManual(id: number): Promise<void> {
  return apiFetch<void>(`/api/costos/manuales/${id}`, { method: 'DELETE' })
}
