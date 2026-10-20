import { apiFetch, apiJson } from './client'
import type { Pagina } from './types'

export type Proveedor = {
  id: number
  nombre: string
  documento: string | null
  celular: string | null
  correo: string | null
}

export type ProveedorCreate = {
  nombre: string
  documento?: string | null
  celular?: string | null
  correo?: string | null
}

export type ProveedorUpdate = {
  nombre?: string
  documento?: string | null
  celular?: string | null
  correo?: string | null
}

export async function listarProveedores(): Promise<Proveedor[]> {
  const r = await apiFetch<Pagina<Proveedor>>('/api/proveedores/?limit=1000')
  return r.items
}

export function paginaProveedores(params: {
  skip: number
  limit: number
  buscar?: string
  orden?: string
  direccion?: string
}): Promise<Pagina<Proveedor>> {
  const q = new URLSearchParams()
  q.set('skip', String(params.skip))
  q.set('limit', String(params.limit))
  if (params.buscar) q.set('buscar', params.buscar)
  if (params.orden) q.set('orden', params.orden)
  if (params.direccion) q.set('direccion', params.direccion)
  return apiFetch<Pagina<Proveedor>>(`/api/proveedores/?${q.toString()}`)
}

export function crearProveedor(data: ProveedorCreate): Promise<Proveedor> {
  return apiJson<Proveedor>('/api/proveedores/', 'POST', data)
}

export function actualizarProveedor(
  id: number,
  data: ProveedorUpdate,
): Promise<Proveedor> {
  return apiJson<Proveedor>(`/api/proveedores/${id}`, 'PUT', data)
}

export function eliminarProveedor(id: number): Promise<void> {
  return apiFetch<void>(`/api/proveedores/${id}`, { method: 'DELETE' })
}
