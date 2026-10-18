import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { clearToken, getToken } from '../api/client'
import { iniciarSesion, obtenerUsuarioActual } from '../api/auth'
import type { UsuarioSesion } from '../api/types'
import { AuthContext } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<UsuarioSesion | null>(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    void (async () => {
      if (getToken()) {
        try {
          setUsuario(await obtenerUsuarioActual())
        } catch {
          clearToken()
        }
      }
      setCargando(false)
    })()
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    await iniciarSesion(username, password)
    setUsuario(await obtenerUsuarioActual())
  }, [])

  const logout = useCallback(() => {
    clearToken()
    setUsuario(null)
  }, [])

  const refrescar = useCallback(async () => {
    setUsuario(await obtenerUsuarioActual())
  }, [])

  const tienePermiso = useCallback(
    (clave: string) => usuario?.permisos?.includes(clave) ?? false,
    [usuario],
  )

  const value = useMemo(
    () => ({ usuario, cargando, login, logout, refrescar, tienePermiso }),
    [usuario, cargando, login, logout, refrescar, tienePermiso],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
