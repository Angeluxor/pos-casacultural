import { apiFetch } from './client'

export type VentaDia = {
  fecha: string
  total: number
  cantidad: number
}

export type VentaMes = {
  mes: string
  total: number
  cantidad: number
}

export type ProductoBajoStock = {
  id: number
  codigo: string
  nombre: string
  stock: number
}

export type CajaResumen = {
  abierta: boolean
  turno_id: number | null
  saldo_inicial_efectivo: number
  saldo_inicial_banco: number
  entradas_efectivo: number
  entradas_banco: number
  salidas_efectivo: number
  salidas_banco: number
  esperado_efectivo: number
  esperado_banco: number
  reservado: number
  disponible: number
}

export type DashboardKpis = {
  ventas_hoy_total: number
  ventas_hoy_cantidad: number
  ventas_7d_total: number
  ventas_mes_total: number
  ventas_mes_cantidad: number
  cartera_total: number
  facturas_pendientes: number
  facturas_credito: number
}

export type DashboardResumen = {
  kpis: DashboardKpis
  ventas_ultimos_7_dias: VentaDia[]
  ventas_ultimos_12_meses: VentaMes[]
  productos_bajo_stock: ProductoBajoStock[]
  facturas_por_estado: Record<string, number>
  caja: CajaResumen
  total_clientes: number
  total_productos: number
}

export function obtenerDashboard(): Promise<DashboardResumen> {
  return apiFetch<DashboardResumen>('/api/dashboard/')
}
