import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ApiError, clearToken, getToken } from '../api/client'
import { iniciarSesion, obtenerUsuarioActual } from '../api/auth'
import type { UsuarioSesion } from '../api/types'
import { borrarSesion, guardarSesion, leerSesion } from '../offline/almacen'
import { AuthContext } from './context'

// La restauración silenciosa no debe dejar la pantalla bloqueada demasiado.
const TIEMPO_RESTAURACION_MS = 8_000
// Login y refresco manual pueden coincidir con un cold start de Render.
const TIEMPO_SESION_MS = 20_000

function errorDeRed(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 0 || err.status >= 500)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<UsuarioSesion | null>(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    void (async () => {
      if (!getToken()) {
        setCargando(false)
        return
      }
      try {
        const actual = await obtenerUsuarioActual({ timeoutMs: TIEMPO_RESTAURACION_MS })
        guardarSesion(actual)
        setUsuario(actual)
      } catch (err) {
        if (errorDeRed(err)) {
          // Si la red falla al recargar, se conserva la sesión del último
          // inicio exitoso. El token no se borra: al volver la red se
          // revalida y, si expiró, el backend responderá 401.
          const cache = leerSesion()
          if (cache) setUsuario(cache)
        } else {
          clearToken()
          borrarSesion()
        }
      }
      setCargando(false)
    })()
  }, [])

  // Una petición cualquiera puede descubrir que el token expiró (por ejemplo,
  // al sincronizar la cola offline). Se cierra la sesión local para que la UI
  // no siga mostrando datos de un usuario no autenticado.
  useEffect(() => {
    function alExpirarSesion() {
      clearToken()
      borrarSesion()
      setUsuario(null)
    }
    window.addEventListener('pos:sesion-expirada', alExpirarSesion)
    return () =>
      window.removeEventListener('pos:sesion-expirada', alExpirarSesion)
  }, [])

  // Si se abrió la app sin red y no había sesión cacheada, al recuperar la
  // conexión se intenta revalidar el token sin obligar a recargar la página.
  useEffect(() => {
    if (usuario) return
    async function revalidar() {
      if (!getToken()) return
      try {
        const actual = await obtenerUsuarioActual({
          timeoutMs: TIEMPO_RESTAURACION_MS,
        })
        guardarSesion(actual)
        setUsuario(actual)
      } catch {
        /* se reintenta en el próximo evento online o al recargar */
      }
    }
    window.addEventListener('online', revalidar)
    return () => window.removeEventListener('online', revalidar)
  }, [usuario])

  const login = useCallback(async (username: string, password: string) => {
    await iniciarSesion(username, password)
    try {
      const actual = await obtenerUsuarioActual({ timeoutMs: TIEMPO_SESION_MS })
      guardarSesion(actual)
      setUsuario(actual)
    } catch (err) {
      // No dejar un token almacenado si la sesión no quedó válida (p. ej.
      // usuario desactivado entre el login y /me).
      clearToken()
      borrarSesion()
      throw err
    }
  }, [])

  const logout = useCallback(() => {
    clearToken()
    borrarSesion()
    setUsuario(null)
  }, [])

  const refrescar = useCallback(async () => {
    const actual = await obtenerUsuarioActual({ timeoutMs: TIEMPO_SESION_MS })
    guardarSesion(actual)
    setUsuario(actual)
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
