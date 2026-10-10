const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '')
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
