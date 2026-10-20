export type Pagina<T> = {
  items: T[]
  total: number
  skip: number
  limit: number
}

export type FormaPago = 'Efectivo' | 'Transferencia' | 'Tarjeta' | 'Otro' | 'Nómina'

export type RolUsuario = 'Admin' | 'Cajero' | 'Mesero'

export type Usuario = {
  id: number
  username: string
  nombre: string
  rol: RolUsuario
  activo: boolean
  cliente_id: number | null
  cliente_nombre: string | null
}

// Usuario de la sesión: incluye los permisos efectivos que devuelve /api/auth/me.
export type UsuarioSesion = Usuario & { permisos: string[] }
