export type Pagina<T> = {
  items: T[]
  total: number
  skip: number
  limit: number
}

export type FormaPago = 'Efectivo' | 'Transferencia' | 'Tarjeta' | 'Otro'

export type RolUsuario = 'Admin' | 'Cajero'

export type Usuario = {
  id: number
  username: string
  nombre: string
  rol: RolUsuario
  activo: boolean
}
