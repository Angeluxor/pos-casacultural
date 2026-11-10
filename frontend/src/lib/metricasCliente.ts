// Mide cuánto tarda cada llamada a la API desde el navegador y lo envía por
// lotes al backend. El servidor solo ve el tiempo que tarda en responder una
// vez que despierta; esta medición incluye la red del dispositivo y el arranque
// en frío del hosting, que es lo que el usuario realmente siente.

const RUTAS_IGNORADAS = ['/api/metricas', '/api/health']
const MAX_PENDIENTES = 200
const LOTE_MAXIMO = 50
const INTERVALO_ENVIO_MS = 60_000

export type MuestraCliente = {
  metodo: string
  ruta: string
  estado: number
  ms: number
  conexion?: string
}

let pendientes: MuestraCliente[] = []
let temporizador: ReturnType<typeof setInterval> | null = null
let enviando = false

function tipoConexion(): string | undefined {
  if (typeof navigator === 'undefined') return undefined
  const info = (navigator as Navigator & { connection?: { effectiveType?: string } })
    .connection
  return info?.effectiveType
}

/** Quita el query string y los ids para agrupar rutas iguales. */
export function normalizarRuta(path: string): string {
  const sinQuery = path.split('?')[0]
  return sinQuery.replace(/\/\d+(?=\/|$)/g, '/{id}')
}

export function esRutaMedible(path: string): boolean {
  if (!path.startsWith('/api/')) return false
  return !RUTAS_IGNORADAS.some((ignorada) => path.startsWith(ignorada))
}

export function registrarMuestra(
  metodo: string,
  path: string,
  estado: number,
  ms: number,
): void {
  if (!esRutaMedible(path)) return
  if (pendientes.length >= MAX_PENDIENTES) pendientes.shift()
  pendientes.push({
    metodo: metodo.toUpperCase(),
    ruta: normalizarRuta(path),
    estado,
    ms: Math.round(ms),
    conexion: tipoConexion(),
  })
}

export function pendientesMetricas(): number {
  return pendientes.length
}

/** Envía el lote acumulado. Nunca lanza: medir no debe afectar a la app. */
export async function enviarMetricas(
  enviar: (lote: MuestraCliente[]) => Promise<void>,
): Promise<void> {
  if (enviando || pendientes.length === 0) return
  enviando = true
  const lote = pendientes.slice(0, LOTE_MAXIMO)
  pendientes = pendientes.slice(lote.length)
  try {
    await enviar(lote)
  } catch {
    // Se descarta el lote: los datos de diagnóstico no justifican reintentar.
  } finally {
    enviando = false
  }
}

export function iniciarMetricasCliente(
  enviar: (lote: MuestraCliente[]) => Promise<void>,
): void {
  if (typeof window === 'undefined' || temporizador) return
  temporizador = setInterval(() => void enviarMetricas(enviar), INTERVALO_ENVIO_MS)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') void enviarMetricas(enviar)
  })
}

/** Solo para pruebas. */
export function reiniciarMetricasCliente(): void {
  pendientes = []
  enviando = false
}
