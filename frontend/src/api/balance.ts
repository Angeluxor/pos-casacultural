import { apiDescargar, apiFetch, apiJson } from './client'

export type SaldosCaja = {
  efectivo: number
  banco: number
  reservado: number
  disponible: number
  abierta: boolean
  turno_id: number | null
  origen: string
}

export type FilaInventarioBalance = {
  producto_id: number
  codigo: string
  nombre: string
  stock: number
  costo_unitario: number
  valor: number
  origen: 'Costo promedio' | 'Precio de venta'
}

export type CuentaPorPagar = {
  ingreso_id: number
  fecha: string
  proveedor: string | null
  total: number
  estado_ingreso: string
  forma_pago_pago: string | null
  fecha_pago: string | null
}

export type BolsilloBalance = {
  id: number
  nombre: string
  descripcion: string | null
  reservado: number
  fecha_creacion: string
}

export type BolsilloMovimiento = {
  id: number
  bolsillo_id: number
  fecha: string
  tipo: 'Aporte' | 'Retiro'
  monto: number
  nota: string | null
  usuario_id: number | null
  usuario_nombre: string | null
}

export type BalanceActivos = {
  efectivo: number
  banco: number
  reservado: number
  disponible: number
  inventario: number
  cartera: number
  total: number
}

export type BalancePasivos = {
  cuentas_por_pagar: number
  total: number
}

export type ResultadosPeriodo = {
  desde: string | null
  hasta: string | null
  ventas_netas: number
  costo_ventas: number
  utilidad_bruta: number
  gastos: number
  gastos_caja: number
  gastos_otros: number
  utilidad: number
  margen: number
  facturas: number
  productos_vendidos_sin_costo: number
}

export type BalanceGeneral = {
  generado: string
  fecha_corte: string
  caja: SaldosCaja
  activos: BalanceActivos
  pasivos: BalancePasivos
  patrimonio: { total: number }
  resultados: ResultadosPeriodo
  inventario: FilaInventarioBalance[]
  cuentas_por_pagar: CuentaPorPagar[]
  bolsillos: BolsilloBalance[]
  total_reservado: number
  productos_sin_costo: number
  valor_inventario_precio_venta: number
  compras_credito_pendientes: number
}

function consulta(desde?: string, hasta?: string): string {
  const q = new URLSearchParams()
  if (desde) q.set('desde', desde)
  if (hasta) q.set('hasta', hasta)
  const s = q.toString()
  return s ? `?${s}` : ''
}

export function obtenerBalance(desde?: string, hasta?: string): Promise<BalanceGeneral> {
  return apiFetch<BalanceGeneral>(`/api/balance${consulta(desde, hasta)}`)
}

export async function descargarBalance(
  formato: 'excel' | 'pdf',
  desde?: string,
  hasta?: string,
): Promise<void> {
  const q = new URLSearchParams({ formato })
  if (desde) q.set('desde', desde)
  if (hasta) q.set('hasta', hasta)
  const ext = formato === 'excel' ? 'xlsx' : 'pdf'
  const marca = `${desde ?? 'todo'}_${hasta ?? 'hoy'}`
  await apiDescargar(`/api/balance/exportar?${q.toString()}`, `balance_${marca}.${ext}`)
}

export function crearBolsillo(datos: {
  nombre: string
  descripcion?: string
}): Promise<BolsilloBalance> {
  return apiJson<BolsilloBalance>('/api/balance/bolsillos', 'POST', datos)
}

export function registrarMovimientoBolsillo(
  bolsilloId: number,
  datos: { tipo: 'Aporte' | 'Retiro'; monto: number; nota?: string },
): Promise<BolsilloMovimiento> {
  return apiJson<BolsilloMovimiento>(
    `/api/balance/bolsillos/${bolsilloId}/movimientos`,
    'POST',
    datos,
  )
}

export function historialBolsillo(bolsilloId: number): Promise<BolsilloMovimiento[]> {
  return apiFetch<BolsilloMovimiento[]>(
    `/api/balance/bolsillos/${bolsilloId}/movimientos`,
  )
}

export async function archivarBolsillo(bolsilloId: number): Promise<void> {
  await apiFetch<void>(`/api/balance/bolsillos/${bolsilloId}`, { method: 'DELETE' })
}
