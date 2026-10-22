import { apiFetch, apiJson, ApiError } from './client'
import type { FormaPago, Pagina } from './types'

export type TipoMovimientoCaja = 'Entrada' | 'Salida' | 'Apertura' | 'Cierre'

export type TurnoCaja = {
  id: number
  usuario_apertura_id: number
  usuario_cierre_id: number | null
  fecha_apertura: string
  fecha_cierre: string | null
  saldo_inicial_efectivo: number
  saldo_inicial_banco: number
  saldo_final_real_efectivo: number | null
  saldo_final_real_banco: number | null
  abierta: boolean
}

export type TurnoCajaHistorial = TurnoCaja & {
  usuario_apertura_nombre: string | null
  usuario_cierre_nombre: string | null
  entradas_efectivo: number
  entradas_banco: number
  salidas_efectivo: number
  salidas_banco: number
  esperado_efectivo: number
  esperado_banco: number
  diferencia_efectivo: number | null
  diferencia_banco: number | null
}

export type RegistroCaja = {
  id: number
  turno_caja_id: number
  usuario_id: number
  fecha: string
  tipo: TipoMovimientoCaja
  referencia: string
  forma_pago: FormaPago
  monto: number
  categoria: string | null
  observacion: string | null
}

export type MovimientoCajaCreate = {
  tipo: TipoMovimientoCaja
  referencia: string
  monto: number
  forma_pago: FormaPago
  categoria?: string
  observacion?: string
}

export const CATEGORIAS_ENTRADA = [
  'Aporte cultural',
  'Donación',
  'Evento',
  'Otro ingreso',
] as const

export const CATEGORIAS_SALIDA = [
  'Arriendo',
  'Servicios',
  'Nómina',
  'Gasto menor',
  'Pago a proveedor',
  'Devolución',
  'Otro gasto',
] as const

export function categoriasDe(tipo: 'Entrada' | 'Salida'): readonly string[] {
  return tipo === 'Entrada' ? CATEGORIAS_ENTRADA : CATEGORIAS_SALIDA
}

export type AbrirCajaDatos = {
  saldo_inicial_efectivo: number
  saldo_inicial_banco: number
}

export type CerrarCajaDatos = {
  saldo_final_real_efectivo: number
  saldo_final_real_banco: number
}

// El bolsillo "banco" agrupa todo lo que no entra al cajón físico.
const FORMAS_BANCO: FormaPago[] = ['Transferencia', 'Tarjeta', 'Otro']

export function esFormaBanco(forma_pago: FormaPago): boolean {
  return FORMAS_BANCO.includes(forma_pago)
}

export async function obtenerCajaActiva(
  opciones: { timeoutMs?: number } = {},
): Promise<TurnoCaja | null> {
  try {
    return await apiFetch<TurnoCaja>('/api/caja/activa', {
      timeoutMs: opciones.timeoutMs,
    })
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

export function abrirCaja(datos: AbrirCajaDatos): Promise<TurnoCaja> {
  return apiJson<TurnoCaja>('/api/caja/abrir', 'POST', datos)
}

export function cerrarCaja(turnoId: number, datos: CerrarCajaDatos): Promise<TurnoCaja> {
  return apiJson<TurnoCaja>(`/api/caja/${turnoId}/cerrar`, 'PUT', datos)
}

export function registrarMovimiento(data: MovimientoCajaCreate): Promise<RegistroCaja> {
  return apiJson<RegistroCaja>('/api/caja/movimientos', 'POST', data)
}

export function obtenerMovimientos(
  turnoId: number,
  opciones: { timeoutMs?: number } = {},
): Promise<RegistroCaja[]> {
  return apiFetch<RegistroCaja[]>(`/api/caja/${turnoId}/movimientos`, {
    timeoutMs: opciones.timeoutMs,
  })
}

export type FacturaPendienteCierre = {
  id: number
  cliente_id: number | null
  cliente_nombre: string | null
  nombre_eventual: string | null
  total: number
  saldo: number
  es_eventual: boolean
}

export function obtenerFacturasPendientes(turnoId: number): Promise<FacturaPendienteCierre[]> {
  return apiFetch<FacturaPendienteCierre[]>(`/api/caja/${turnoId}/pendientes`)
}

export type ResumenVentasTurno = {
  ventas: number
  creditos: number
  cobrado: number
}

export function obtenerResumenVentasTurno(turnoId: number): Promise<ResumenVentasTurno> {
  return apiFetch<ResumenVentasTurno>(`/api/caja/${turnoId}/resumen-ventas`)
}

export function listarTurnos(params: {
  skip: number
  limit: number
  desde?: string
  hasta?: string
  orden?: string
  direccion?: string
}): Promise<Pagina<TurnoCajaHistorial>> {
  const q = new URLSearchParams()
  q.set('skip', String(params.skip))
  q.set('limit', String(params.limit))
  if (params.desde) q.set('desde', params.desde)
  if (params.hasta) q.set('hasta', params.hasta)
  if (params.orden) q.set('orden', params.orden)
  if (params.direccion) q.set('direccion', params.direccion)
  return apiFetch<Pagina<TurnoCajaHistorial>>(`/api/caja/turnos?${q.toString()}`)
}
