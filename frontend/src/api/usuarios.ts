import { apiFetch, apiJson } from './client'
import type { Pagina } from './types'
import type { RolUsuario, Usuario } from './types'

export type UsuarioCreate = {
  username: string
  nombre: string
  password: string
  rol: RolUsuario
  activo: boolean
}

export type UsuarioUpdate = {
  nombre?: string
  password?: string
  rol?: RolUsuario
  activo?: boolean
}

export function paginaUsuarios(params: {
  skip: number
  limit: number
  buscar?: string
  orden?: string
  direccion?: string
}): Promise<Pagina<Usuario>> {
  const q = new URLSearchParams()
  q.set('skip', String(params.skip))
  q.set('limit', String(params.limit))
  if (params.buscar) q.set('buscar', params.buscar)
  if (params.orden) q.set('orden', params.orden)
  if (params.direccion) q.set('direccion', params.direccion)
  return apiFetch<Pagina<Usuario>>(`/api/usuarios/?${q.toString()}`)
}

export function crearUsuario(data: UsuarioCreate): Promise<Usuario> {
  return apiJson<Usuario>('/api/usuarios/', 'POST', data)
}

export function actualizarUsuario(id: number, data: UsuarioUpdate): Promise<Usuario> {
  return apiJson<Usuario>(`/api/usuarios/${id}`, 'PUT', data)
}

export function eliminarUsuario(id: number): Promise<void> {
  return apiFetch<void>(`/api/usuarios/${id}`, { method: 'DELETE' })
}
