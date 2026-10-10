import { createContext } from 'react'
import type { Usuario } from '../api/types'

export type AuthContextType = {
  usuario: Usuario | null
  cargando: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refrescar: () => Promise<void>
}

export const AuthContext = createContext<AuthContextType | null>(null)
