import { apiFetch, apiJson } from './client'
import type { RolUsuario } from './types'

export type PermisoItem = { clave: string; etiqueta: string }
export type ModuloPermisos = { modulo: string; permisos: PermisoItem[] }
export type PermisosResponse = {
  modulos: ModuloPermisos[]
  roles: Record<string, string[]>
  todos: string[]
}

export function obtenerPermisos(): Promise<PermisosResponse> {
  return apiFetch<PermisosResponse>('/api/permisos/')
}

export function guardarPermisosRol(
  rol: RolUsuario,
  permisos: string[],
): Promise<{ rol: string; permisos: string[] }> {
  return apiJson<{ rol: string; permisos: string[] }>(`/api/permisos/${rol}`, 'PUT', { permisos })
}
