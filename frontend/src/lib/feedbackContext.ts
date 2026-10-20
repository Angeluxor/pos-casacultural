import { APP_VERSION } from './version'

type UsuarioContexto = {
  rol?: string
} | null

let instalado = false
let ultimoError: string | null = null

function guardarError(mensaje: string) {
  ultimoError = mensaje.slice(0, 500)
}

export function instalarCapturaErrores(): void {
  if (instalado || typeof window === 'undefined') return
  instalado = true

  window.addEventListener('error', (evento) => {
    const ubicacion = evento.filename
      ? ` (${evento.filename}:${evento.lineno ?? 0})`
      : ''
    guardarError(`${evento.message || 'Error de JavaScript'}${ubicacion}`)
  })

  window.addEventListener('unhandledrejection', (evento) => {
    const motivo = evento.reason
    const mensaje =
      motivo instanceof Error ? motivo.message : typeof motivo === 'string' ? motivo : 'Promesa rechazada sin detalle'
    guardarError(mensaje)
  })
}

export function obtenerUltimoError(): string | null {
  return ultimoError
}

export function contextoFeedback(usuario: UsuarioContexto): Record<string, unknown> {
  return {
    // Solo la ruta: los parámetros de búsqueda pueden contener nombres o datos
    // de clientes y no son necesarios para reproducir el problema.
    ruta: window.location.pathname,
    titulo: document.title,
    rol: usuario?.rol ?? null,
    version: APP_VERSION,
    navegador: navigator.userAgent,
    idioma: navigator.language,
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    zona_horaria: Intl.DateTimeFormat().resolvedOptions().timeZone,
    ultimo_error: obtenerUltimoError(),
  }
}
