import { apiDescargar, apiFetch } from './client'

export type TipoReporte = 'ventas' | 'top-productos' | 'cartera' | 'caja' | 'inventario'

export type FormaPagoMonto = {
  forma_pago: string
  monto: number
}

export type VentaPorDia = {
  fecha: string
  facturas: number
  anuladas: number
  total: number
  total_anulado: number
}

export type FilaVenta = {
  id: number
  fecha: string
  cliente: string | null
  vendedor: string
  estado: string
  total: number
  saldo: number
}

export type ReporteVentas = {
  desde: string | null
  hasta: string | null
  generado: string
  facturas: number
  facturas_anuladas: number
  total_vendido: number
  total_anulado: number
  neto: number
  por_dia: VentaPorDia[]
  por_forma_pago: FormaPagoMonto[]
  detalle: FilaVenta[]
}

export type FilaTopProducto = {
  codigo: string
  nombre: string
  cantidad: number
  total: number
  precio_promedio: number
}

export type ReporteTopProductos = {
  desde: string | null
  hasta: string | null
  generado: string
  renglones: number
  cantidad_total: number
  total_vendido: number
  items: FilaTopProducto[]
}

export type FilaCartera = {
  cliente_id: number
  nombre: string
  documento: string | null
  facturas: number
  total: number
  pagado: number
  saldo: number
}

export type ReporteCartera = {
  generado: string
  clientes_con_saldo: number
  total_cartera: number
  items: FilaCartera[]
}

export type FilaCierreCaja = {
  id: number
  fecha_apertura: string
  fecha_cierre: string | null
  usuario_apertura: string | null
  usuario_cierre: string | null
  saldo_inicial: number
  entradas: number
  salidas: number
  esperado: number
  saldo_final_real: number | null
  diferencia: number | null
}

export type ReporteCaja = {
  desde: string | null
  hasta: string | null
  generado: string
  turnos: number
  saldo_inicial_total: number
  entradas_total: number
  salidas_total: number
  esperado_total: number
  saldo_final_total: number
  diferencia_total: number
  por_forma_pago: FormaPagoMonto[]
  items: FilaCierreCaja[]
}

export type FilaInventario = {
  id: number
  codigo: string
  nombre: string
  precio: number
  stock: number
  valor: number
}

export type ReporteInventario = {
  generado: string
  productos: number
  unidades_totales: number
  valor_inventario: number
  items: FilaInventario[]
}

function qs(desde?: string, hasta?: string, extra?: Record<string, string>): string {
  const q = new URLSearchParams({ ...(extra ?? {}) })
  if (desde) q.set('desde', desde)
  if (hasta) q.set('hasta', hasta)
  const s = q.toString()
  return s ? `?${s}` : ''
}

export function consultarVentas(desde?: string, hasta?: string): Promise<ReporteVentas> {
  return apiFetch<ReporteVentas>(`/api/reportes/ventas${qs(desde, hasta)}`)
}

export function consultarTopProductos(desde?: string, hasta?: string): Promise<ReporteTopProductos> {
  return apiFetch<ReporteTopProductos>(`/api/reportes/top-productos${qs(desde, hasta)}`)
}

export function consultarCartera(): Promise<ReporteCartera> {
  return apiFetch<ReporteCartera>('/api/reportes/cartera')
}

export function consultarCaja(desde?: string, hasta?: string): Promise<ReporteCaja> {
  return apiFetch<ReporteCaja>(`/api/reportes/caja${qs(desde, hasta)}`)
}

export function consultarInventario(): Promise<ReporteInventario> {
  return apiFetch<ReporteInventario>('/api/reportes/inventario')
}

export async function descargarReporte(
  tipo: TipoReporte,
  formato: 'excel' | 'pdf',
  desde?: string,
  hasta?: string,
): Promise<void> {
  const q = new URLSearchParams()
  q.set('formato', formato)
  if (desde) q.set('desde', desde)
  if (hasta) q.set('hasta', hasta)
  const ext = formato === 'excel' ? 'xlsx' : 'pdf'
  const marca = `${desde ?? 'todo'}_${hasta ?? 'hoy'}`
  await apiDescargar(`/api/reportes/${tipo}/exportar?${q.toString()}`, `${tipo}_${marca}.${ext}`)
}