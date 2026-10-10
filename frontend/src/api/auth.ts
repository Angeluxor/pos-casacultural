import { apiFetch, apiForm, apiJson, setToken } from './client'
import type { Usuario } from './types'

export type PerfilUpdate = { nombre?: string }
export type PasswordUpdate = { password_actual: string; password_nueva: string }

export async function iniciarSesion(username: string, password: string): Promise<void> {
  const data = await apiForm<{ access_token: string }>('/api/auth/login', { username, password })
  setToken(data.access_token)
}

export async function obtenerUsuarioActual(): Promise<Usuario> {
  return apiFetch<Usuario>('/api/auth/me')
}

export function actualizarPerfil(data: PerfilUpdate): Promise<Usuario> {
  return apiJson<Usuario>('/api/auth/me', 'PUT', data)
}

export function cambiarPassword(data: PasswordUpdate): Promise<void> {
  return apiJson<void>('/api/auth/me/password', 'PUT', data)
}
