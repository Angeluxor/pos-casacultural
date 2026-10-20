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
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY)
export const setToken = (token: string): void => localStorage.setItem(TOKEN_KEY, token)
export const clearToken = (): void => localStorage.removeItem(TOKEN_KEY)

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = getToken()
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, { ...options, headers })
  } catch {
    throw new ApiError(0, 'No se pudo conectar con el servidor')
  }

  if (res.status === 401) {
    clearToken()
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

export async function apiJson<T>(path: string, method: string, cuerpo: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
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
