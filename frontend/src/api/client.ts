// En producción usamos la URL configurada en Vercel. En los previews de
// Vercel preferimos el proxy /api del propio despliegue (ver vercel.json):
// así el navegador no hace una petición cross-origin y el preview no depende
// de que su dominio esté en CORS_ORIGINS ni de variables de entorno Preview.
export function resolverApiUrl(configurada: string, hostname: string): string {
  const url = configurada.replace(/\/+$/, '')
  const esPreviewVercel =
    hostname.endsWith('.vercel.app') && hostname !== 'pos-casacultural.vercel.app'
  return esPreviewVercel ? '' : url
}

const API_URL = resolverApiUrl(
  import.meta.env.VITE_API_URL ?? '',
  typeof window === 'undefined' ? '' : window.location.hostname,
)
const TOKEN_KEY = 'pos_token'

export class ApiError extends Error {
  status: number
  timeout: boolean
  constructor(status: number, message: string, timeout = false) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.timeout = timeout
  }
}

export type ApiOpciones = RequestInit & {
  /** Tiempo máximo de espera. 0 desactiva el límite. */
  timeoutMs?: number
}

// Sin límite, un fetch con la red móvil caída o un cold start de Render puede
// dejar la UI en "Guardando…" indefinidamente.
const TIEMPO_MAXIMO_MS = 30_000
// El plan free de Render duerme el servicio tras unos minutos de inactividad.
// La primera petición después de ese descanso (arranque en frío) puede tardar
// bastante más que una petición normal; por eso el "despertar" tiene su propio
// margen y no se confunde con una caída de red.
const TIEMPO_MAXIMO_DESPERTAR_MS = 75_000

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY)
export const setToken = (token: string): void => localStorage.setItem(TOKEN_KEY, token)
export const clearToken = (): void => localStorage.removeItem(TOKEN_KEY)

function notificarRed(
  evento: 'pos:sin-conexion' | 'pos:conexion' | 'pos:servidor-lento',
): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(evento))
  }
}

/**
 * Error de red o de disponibilidad: la operación puede reintentarse o
 * guardarse para enviarla luego.
 *
 * Incluye los timeouts a propósito: si el servidor no confirma una venta, lo
 * seguro es encolarla con su clave de idempotencia. Distinguir "sin conexión"
 * de "servidor lento" para la UI es responsabilidad de ``apiFetch``.
 */
export function esErrorRed(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 0 || err.status >= 500)
}

/** La petición agotó el tiempo de espera (servidor lento o dormido). */
export function esErrorTiempo(err: unknown): boolean {
  return err instanceof ApiError && err.timeout
}

/** Error seguro de reintentar con la misma clave de idempotencia. */
export function esErrorReintentable(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 0 || err.status === 503)
}

export async function apiFetch<T>(path: string, options: ApiOpciones = {}): Promise<T> {
  const { timeoutMs = TIEMPO_MAXIMO_MS, signal: signalExterno, ...init } = options
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const controller = new AbortController()
  if (signalExterno) {
    if (signalExterno.aborted) controller.abort()
    else signalExterno.addEventListener('abort', () => controller.abort(), { once: true })
  }
  const timer =
    timeoutMs > 0 ? setTimeout(() => controller.abort(), timeoutMs) : null

  try {
    let res: Response
    try {
      res = await fetch(`${API_URL}${path}`, {
        ...init,
        headers,
        signal: controller.signal,
      })
    } catch {
      if (signalExterno?.aborted) {
        throw new ApiError(0, 'La operación fue cancelada')
      }
      if (controller.signal.aborted) {
        // Se agotó nuestro tiempo de espera. La red puede estar perfecta: el
        // servidor simplemente no contestó (p. ej. arranque en frío). No se
        // marca la app como "sin conexión".
        notificarRed('pos:servidor-lento')
        throw new ApiError(
          0,
          'El servidor tardó demasiado en responder. Reintentando…',
          true,
        )
      }
      if (typeof navigator !== 'undefined' && navigator.onLine === false) {
        notificarRed('pos:sin-conexion')
      } else {
        // Hay red, pero el servidor no responde: tampoco es "sin conexión".
        notificarRed('pos:servidor-lento')
      }
      throw new ApiError(0, 'No se pudo conectar con el servidor')
    }

    // Llegó una respuesta HTTP (aunque sea de error): hay conexión.
    notificarRed('pos:conexion')

    if (res.status === 401) {
      clearToken()
      if (!path.includes('/auth/login') && typeof window !== 'undefined') {
        window.dispatchEvent(new Event('pos:sesion-expirada'))
      }
      let detalle = 'Sesión no válida o expirada'
      if (path.includes('/auth/login')) {
        try {
          const data = await res.json()
          if (typeof data.detail === 'string' && data.detail) detalle = data.detail
        } catch {
          /* respuesta sin JSON */
        }
      }
      throw new ApiError(401, detalle)
    }
    if (!res.ok) {
      let detalle = `Error ${res.status}`
      try {
        const data = await res.json()
        if (typeof data.detail === 'string') detalle = data.detail
      } catch {
        /* respuesta sin JSON */
      }
      throw new ApiError(res.status, detalle)
    }
    if (res.status === 204) return undefined as T
    return (await res.json()) as T
  } catch (err) {
    // El límite también cubre la lectura del cuerpo: una respuesta puede
    // llegar con cabeceras y quedarse colgada a mitad de la descarga.
    if (controller.signal.aborted && !(err instanceof ApiError)) {
      if (signalExterno?.aborted) {
        throw new ApiError(0, 'La operación fue cancelada')
      }
      notificarRed('pos:servidor-lento')
      throw new ApiError(
        0,
        'El servidor tardó demasiado en responder. Reintentando…',
        true,
      )
    }
    throw err
  } finally {
    if (timer) clearTimeout(timer)
  }
}

let despertandoServidor: Promise<boolean> | null = null

/**
 * Despierta al servidor con una petición ligera a ``/api/health``.
 *
 * El plan free de Render duerme el backend tras unos minutos sin tráfico. La
 * primera petición después del descanso puede superar el timeout normal; si se
 * tratara como "sin conexión" la UI mentiría al cajero. Este ping se hace al
 * recuperar el foco y mientras la app se cree offline, con un margen mayor.
 * Las llamadas concurrentes comparten la misma petición.
 */
export function despertarServidor(
  timeoutMs = TIEMPO_MAXIMO_DESPERTAR_MS,
): Promise<boolean> {
  if (typeof window === 'undefined') return Promise.resolve(false)
  if (despertandoServidor) return despertandoServidor

  despertandoServidor = (async () => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const res = await fetch(`${API_URL}/api/health`, {
        signal: controller.signal,
        cache: 'no-store',
      })
      if (res.ok) {
        notificarRed('pos:conexion')
        return true
      }
      return false
    } catch {
      return false
    } finally {
      clearTimeout(timer)
      despertandoServidor = null
    }
  })()

  return despertandoServidor
}

export async function apiBlob(path: string): Promise<Blob> {
  const headers = new Headers()
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, { headers })
  } catch {
    throw new ApiError(0, 'No se pudo conectar con el servidor')
  }
  if (res.status === 401) {
    clearToken()
    throw new ApiError(401, 'Sesión no válida o expirada')
  }
  if (!res.ok) {
    let detalle = `Error ${res.status}`
    try {
      const data = await res.json()
      if (typeof data.detail === 'string') detalle = data.detail
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(res.status, detalle)
  }
  return res.blob()
}

export async function apiJson<T>(
  path: string,
  method: string,
  cuerpo: unknown,
  options: Omit<ApiOpciones, 'method' | 'body'> = {},
): Promise<T> {
  const headers = new Headers(options.headers)
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  return apiFetch<T>(path, {
    ...options,
    method,
    headers,
    body: JSON.stringify(cuerpo),
  })
}

export async function apiForm<T>(path: string, form: Record<string, string>): Promise<T> {
  return apiFetch<T>(path, { method: 'POST', body: new URLSearchParams(form) })
}

export async function apiDescargar(path: string, nombreArchivo: string): Promise<void> {
  const headers = new Headers()
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, { headers })
  } catch {
    throw new ApiError(0, 'No se pudo conectar con el servidor')
  }
  if (!res.ok) {
    let detalle = `Error ${res.status}`
    try {
      const data = await res.json()
      if (typeof data.detail === 'string') detalle = data.detail
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(res.status, detalle)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nombreArchivo
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
