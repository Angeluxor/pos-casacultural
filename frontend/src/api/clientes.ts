import { apiFetch, apiJson } from './client'
import type { Pagina } from './types'

export type Cliente = {
  id: number
  nombre: string
  documento: string
}

export type ClienteCreate = {
  nombre: string
  documento: string
}

export type ClienteUpdate = {
  nombre?: string
  documento?: string
}

export async function listarClientes(): Promise<Cliente[]> {
  const r = await apiFetch<Pagina<Cliente>>('/api/clientes/?limit=1000')
  return r.items
}

export function paginaClientes(params: {
  skip: number
  limit: number
  buscar?: string
}): Promise<Pagina<Cliente>> {
  const q = new URLSearchParams()
  q.set('skip', String(params.skip))
  q.set('limit', String(params.limit))
  if (params.buscar) q.set('buscar', params.buscar)
  return apiFetch<Pagina<Cliente>>(`/api/clientes/?${q.toString()}`)
}

export function crearCliente(data: ClienteCreate): Promise<Cliente> {
  return apiJson<Cliente>('/api/clientes/', 'POST', data)
}

export function actualizarCliente(id: number, data: ClienteUpdate): Promise<Cliente> {
  return apiJson<Cliente>(`/api/clientes/${id}`, 'PUT', data)
}

export function eliminarCliente(id: number): Promise<void> {
  return apiFetch<void>(`/api/clientes/${id}`, { method: 'DELETE' })
}
