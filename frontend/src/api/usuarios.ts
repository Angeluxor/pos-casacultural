import { apiFetch, apiJson } from './client'
import type { Pagina } from './types'
import type { RolUsuario, Usuario } from './types'
import type { Cliente } from './clientes'
import type { FilaHistorialNomina } from './reportes'

export type UsuarioCreate = {
  username: string
  nombre: string
  password: string
  rol: RolUsuario
  activo: boolean
  cliente_id?: number | null
}

export type UsuarioUpdate = {
  nombre?: string
  password?: string
  rol?: RolUsuario
  activo?: boolean
  cliente_id?: number | null
}

export type DeudaNominaFila = {
  factura_id: number
  fecha: string
  total: number
  saldo: number
}

export type DeudaNomina = {
  usuario_id: number
  cliente_id: number
  cliente_nombre: string
  saldo_total: number
  facturas: DeudaNominaFila[]
}

export type DescuentoNominaResultado = {
  descuento_id: number
  usuario_id: number
  cliente_id: number
  cliente_nombre: string
  monto_aplicado: number
  saldo_pendiente: number
  facturas_afectadas: number
  nota: string | null
}

export type HistorialNomina = {
  usuario_id: number
  usuario_nombre: string
  cliente_id: number | null
  cliente_nombre: string | null
  saldo_total: number
  descuentos: number
  monto_total: number
  items: FilaHistorialNomina[]
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

// Clientes que se pueden vincular a un usuario (sin vínculo) y, si se indica
// `usuarioId`, también el que ya tiene ese usuario.
export function clientesDisponibles(usuarioId?: number): Promise<Cliente[]> {
  const q = usuarioId != null ? `?usuario_id=${usuarioId}` : ''
  return apiFetch<Cliente[]>(`/api/usuarios/clientes-disponibles${q}`)
}

export function obtenerDeudaNomina(usuarioId: number): Promise<DeudaNomina> {
  return apiFetch<DeudaNomina>(`/api/usuarios/${usuarioId}/nomina`)
}

export function obtenerHistorialNomina(
  usuarioId: number,
  limite = 100,
): Promise<HistorialNomina> {
  return apiFetch<HistorialNomina>(
    `/api/usuarios/${usuarioId}/nomina/historial?limite=${limite}`,
  )
}

export function aplicarDescuentoNomina(
  usuarioId: number,
  monto?: number | null,
  nota?: string,
): Promise<DescuentoNominaResultado> {
  const body: { monto?: number; nota?: string } = {}
  if (monto != null) body.monto = monto
  const limpia = nota?.trim()
  if (limpia) body.nota = limpia
  return apiJson<DescuentoNominaResultado>(
    `/api/usuarios/${usuarioId}/nomina/descuento`,
    'POST',
    body,
  )
}
