import { createContext } from 'react'
import type { UsuarioSesion } from '../api/types'

export type AuthContextType = {
  usuario: UsuarioSesion | null
  cargando: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refrescar: () => Promise<void>
  /** Indica si el usuario de la sesión tiene un permiso concreto. */
  tienePermiso: (clave: string) => boolean
}

export const AuthContext = createContext<AuthContextType | null>(null)
