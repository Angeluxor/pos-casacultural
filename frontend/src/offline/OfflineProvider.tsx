import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useAuth } from '../auth/useAuth'
import {
  leerCola,
  normalizarCola,
  type OperacionOffline,
} from './almacen'
import { OfflineContext } from './context'
import { sincronizarPendientes } from './sync'

const INTERVALO_SINCRONIZACION_MS = 30_000

export function OfflineProvider({ children }: { children: ReactNode }) {
  const { usuario } = useAuth()
  const [enLinea, setEnLinea] = useState(
    () => typeof navigator === 'undefined' || navigator.onLine,
  )
  const [operaciones, setOperaciones] = useState<OperacionOffline[]>(() => leerCola())
  const [sincronizando, setSincronizando] = useState(false)
  const [ultimoError, setUltimoError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)
  const sincronizandoRef = useRef(false)

  const recargarCola = useCallback(() => {
    setOperaciones(leerCola())
  }, [])

  const sincronizarAhora = useCallback(async () => {
    if (!usuario) return null
    if (sincronizandoRef.current) return null
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      setEnLinea(false)
      return null
    }
    if (leerCola().length === 0) return null

    sincronizandoRef.current = true
    setSincronizando(true)
    setUltimoError(null)
    try {
      const resultado = await sincronizarPendientes(usuario.id)
      if (resultado.sinConexion) {
        setEnLinea(false)
      } else {
        setEnLinea(true)
      }
      if (resultado.sincronizadas > 0) {
        setVersion((v) => v + 1)
      }
      if (resultado.errores > 0) {
        setUltimoError(
          `${resultado.errores} operación(es) necesitan revisión.`,
        )
      } else if (resultado.pendientes > 0) {
        setUltimoError(
          `${resultado.pendientes} operación(es) siguen pendientes.`,
        )
      }
      return resultado
    } catch (err) {
      setUltimoError(
        err instanceof Error ? err.message : 'No se pudo sincronizar.',
      )
      return null
    } finally {
      sincronizandoRef.current = false
      setSincronizando(false)
      recargarCola()
    }
  }, [usuario, recargarCola])

  useEffect(() => {
    normalizarCola()
    recargarCola()
  }, [recargarCola])

  useEffect(() => {
    function alVolverLaRed() {
      setEnLinea(true)
      void sincronizarAhora()
    }
    function alPerderLaRed() {
      setEnLinea(false)
    }
    function alFallarPeticion() {
      setEnLinea(false)
    }
    function alResponderServidor() {
      setEnLinea(true)
    }

    window.addEventListener('online', alVolverLaRed)
    window.addEventListener('offline', alPerderLaRed)
    window.addEventListener('pos:sin-conexion', alFallarPeticion)
    window.addEventListener('pos:conexion', alResponderServidor)
    window.addEventListener('pos:cola-cambiada', recargarCola)
    return () => {
      window.removeEventListener('online', alVolverLaRed)
      window.removeEventListener('offline', alPerderLaRed)
      window.removeEventListener('pos:sin-conexion', alFallarPeticion)
      window.removeEventListener('pos:conexion', alResponderServidor)
      window.removeEventListener('pos:cola-cambiada', recargarCola)
    }
  }, [sincronizarAhora, recargarCola])

  // Al iniciar sesión o volver la conexión, se intenta vaciar la cola.
  useEffect(() => {
    if (usuario && enLinea) {
      void sincronizarAhora()
    }
  }, [usuario, enLinea, sincronizarAhora])

  // Reintento periódico: si la red está inestable, la cola no se queda
  // esperando a que el usuario recuerde pulsar el botón.
  useEffect(() => {
    if (!usuario) return
    const timer = window.setInterval(() => {
      if (navigator.onLine) void sincronizarAhora()
    }, INTERVALO_SINCRONIZACION_MS)
    return () => window.clearInterval(timer)
  }, [usuario, sincronizarAhora])

  const value = useMemo(
    () => ({
      enLinea,
      operaciones,
      pendientes: operaciones.length,
      sincronizando,
      ultimoError,
      version,
      sincronizarAhora,
      recargarCola,
    }),
    [
      enLinea,
      operaciones,
      sincronizando,
      ultimoError,
      version,
      sincronizarAhora,
      recargarCola,
    ],
  )

  return (
    <OfflineContext.Provider value={value}>{children}</OfflineContext.Provider>
  )
}
