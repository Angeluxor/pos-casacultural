import { apiFetch, apiJson } from './client'
import type { Pagina } from './types'

export type Producto = {
  id: number
  codigo: string
  nombre: string
  precio: number
  stock: number
}

export type ProductoCreate = {
  codigo: string
  nombre: string
  precio: number
  stock_inicial: number
}

export type ProductoUpdate = {
  nombre?: string
  precio?: number
}

export type TipoMovimientoInventario =
  | 'Entrada por Compra'
  | 'Salida por Venta'
  | 'Devolución'
  | 'Ajuste'

export type MovimientoInventario = {
  tipo_movimiento: TipoMovimientoInventario
  cantidad: number
  referencia?: string
}

export type KardexMovimiento = {
  id: number
  producto_id: number
  usuario_id: number
  fecha: string
  cantidad: number
  saldo_stock: number
  referencia: string | null
  tipo_movimiento: TipoMovimientoInventario
}

export async function listarProductos(): Promise<Producto[]> {
  const r = await apiFetch<Pagina<Producto>>('/api/productos/?limit=1000')
  return r.items
}

export function paginaProductos(params: {
  skip: number
  limit: number
  buscar?: string
}): Promise<Pagina<Producto>> {
  const q = new URLSearchParams()
  q.set('skip', String(params.skip))
  q.set('limit', String(params.limit))
  if (params.buscar) q.set('buscar', params.buscar)
  return apiFetch<Pagina<Producto>>(`/api/productos/?${q.toString()}`)
}

export function crearProducto(data: ProductoCreate): Promise<Producto> {
  return apiJson<Producto>('/api/productos/', 'POST', data)
}

export function actualizarProducto(id: number, data: ProductoUpdate): Promise<Producto> {
  return apiJson<Producto>(`/api/productos/${id}`, 'PUT', data)
}

export function registrarMovimiento(
  productoId: number,
  data: MovimientoInventario,
): Promise<KardexMovimiento> {
  return apiJson<KardexMovimiento>(`/api/productos/${productoId}/kardex`, 'POST', data)
}

export function historialKardex(productoId: number): Promise<KardexMovimiento[]> {
  return apiFetch<KardexMovimiento[]>(`/api/productos/${productoId}/kardex`)
}
