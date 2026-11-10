import { apiFetch, apiJson } from './client'
import type { MuestraCliente } from '../lib/metricasCliente'

export type ResumenServidor = {
  n: number
  p50: number
  p95: number
  max: number
  pct_lentas: number
  pct_db: number
  arranques_en_frio: number
  tras_inactividad: number
  conexiones_nuevas: number
  errores_5xx: number
}

export type ResumenCliente = {
  n: number
  p50: number
  p95: number
  max: number
  fallidas: number
}

export type RutaMetrica = {
  ruta: string
  n: number
  p50: number
  p95: number
  max: number
  db_prom: number
  pct_db: number
  consultas_prom: number
  errores_5xx: number
  cliente_p95: number | null
}

export type PuntoHora = { hora: string; n: number; p50: number; p95: number }

export type PeticionLenta = {
  creado_en: string
  metodo: string
  ruta: string
  estado: number
  ms_total: number
  ms_db: number
  consultas: number
  conexiones_nuevas: number
  inactivo_s: number | null
  primera_tras_arranque: boolean
}

export type ResumenMetricas = {
  horas: number
  generado: string
  proceso: {
    proceso_desde: string
    arranque_ms: number | null
    en_bufer: number
    descartadas: number
  }
  servidor: ResumenServidor
  cliente: ResumenCliente
  diagnostico: string[]
  rutas: RutaMetrica[]
  por_hora: PuntoHora[]
  lentas: PeticionLenta[]
}

export function obtenerResumenMetricas(horas: number): Promise<ResumenMetricas> {
  return apiFetch<ResumenMetricas>(`/api/metricas/resumen?horas=${horas}`)
}

/** Envía las mediciones del navegador. Es secundario: timeout corto. */
export async function enviarMuestrasCliente(muestras: MuestraCliente[]): Promise<void> {
  await apiJson<void>('/api/metricas/cliente', 'POST', { muestras }, { timeoutMs: 15_000 })
}
