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

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY)
export const setToken = (token: string): void => localStorage.setItem(TOKEN_KEY, token)
export const clearToken = (): void => localStorage.removeItem(TOKEN_KEY)

function notificarRed(evento: 'pos:sin-conexion' | 'pos:conexion'): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(evento))
  }
}

/** Error de red o de disponibilidad: la operación puede reintentarse. */
export function esErrorRed(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 0 || err.status >= 500)
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
      // Un timeout o un fallo de red activa el modo offline de la UI. Cualquier
      // respuesta posterior del servidor lo desactiva.
      notificarRed('pos:sin-conexion')
      if (controller.signal.aborted) {
        throw new ApiError(
          0,
          'La operación tardó demasiado. Revisa tu conexión e inténtalo de nuevo.',
          true,
        )
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
      notificarRed('pos:sin-conexion')
      throw new ApiError(
        0,
        'La operación tardó demasiado. Revisa tu conexión e inténtalo de nuevo.',
        true,
      )
    }
    throw err
  } finally {
    if (timer) clearTimeout(timer)
  }
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
