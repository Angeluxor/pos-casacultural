import { apiFetch, apiJson, ApiError } from './client'
import type { FormaPago } from './types'

export type TipoMovimientoCaja = 'Entrada' | 'Salida' | 'Apertura' | 'Cierre'

export type TurnoCaja = {
  id: number
  usuario_apertura_id: number
  usuario_cierre_id: number | null
  fecha_apertura: string
  fecha_cierre: string | null
  saldo_inicial: number
  saldo_final_real: number | null
  abierta: boolean
}

export type RegistroCaja = {
  id: number
  turno_caja_id: number
  usuario_id: number
  fecha: string
  tipo: TipoMovimientoCaja
  referencia: string
  forma_pago: FormaPago | null
  monto: number
  observacion: string | null
}

export type MovimientoCajaCreate = {
  tipo: TipoMovimientoCaja
  referencia: string
  monto: number
  forma_pago?: FormaPago
  observacion?: string
}

export async function obtenerCajaActiva(): Promise<TurnoCaja | null> {
  try {
    return await apiFetch<TurnoCaja>('/api/caja/activa')
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

export function abrirCaja(saldo_inicial: number): Promise<TurnoCaja> {
  return apiJson<TurnoCaja>('/api/caja/abrir', 'POST', { saldo_inicial })
}

export function cerrarCaja(turnoId: number, saldoFinalReal: number): Promise<TurnoCaja> {
  return apiJson<TurnoCaja>(`/api/caja/${turnoId}/cerrar`, 'PUT', {
    saldo_final_real: saldoFinalReal,
  })
}

export function registrarMovimiento(data: MovimientoCajaCreate): Promise<RegistroCaja> {
  return apiJson<RegistroCaja>('/api/caja/movimientos', 'POST', data)
}

export function obtenerMovimientos(turnoId: number): Promise<RegistroCaja[]> {
  return apiFetch<RegistroCaja[]>(`/api/caja/${turnoId}/movimientos`)
}
