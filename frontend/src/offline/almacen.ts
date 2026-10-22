/**
 * Almacenamiento local del modo offline.
 *
 * Es deliberadamente simple (localStorage) porque el POS maneja un catálogo
 * pequeño y una cola de operaciones acotada. La cola es la fuente de verdad
 * mientras no hay red; el servidor sigue siendo la fuente de verdad al
 * sincronizar.
 */
import type { Cliente } from '../api/clientes'
import type { RegistroCaja, TurnoCaja } from '../api/caja'
import type { Producto } from '../api/productos'
import type { FormaPago, UsuarioSesion } from '../api/types'
import type { PaginaFacturas } from '../api/ventas'

const CLAVE_SESION = 'pos_offline_sesion_v1'
const CLAVE_CATALOGO = 'pos_offline_catalogo_v1'
const CLAVE_COLA = 'pos_offline_cola_v1'
const CLAVE_FACTURAS = 'pos_offline_facturas_v1'
const CLAVE_MOVS_CAJA = 'pos_offline_caja_movs_v1'

const MAX_EDAD_SESION_MS = 12 * 60 * 60 * 1000
const MAX_CACHE_FACTURAS = 12

function leerJson<T>(clave: string): T | null {
  if (typeof localStorage === 'undefined') return null
  try {
    const crudo = localStorage.getItem(clave)
    return crudo ? (JSON.parse(crudo) as T) : null
  } catch {
    return null
  }
}

function guardarJson(clave: string, valor: unknown): boolean {
  if (typeof localStorage === 'undefined') return false
  try {
    localStorage.setItem(clave, JSON.stringify(valor))
    return true
  } catch {
    // Cuota llena o almacenamiento bloqueado: quien llama decide qué mostrar.
    return false
  }
}

function borrar(clave: string): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.removeItem(clave)
  } catch {
    /* sin almacenamiento disponible */
  }
}

function notificarColaCambiada(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('pos:cola-cambiada'))
  }
}

/* ----------------------------- Sesión ----------------------------- */

export type SesionOffline = {
  usuario: UsuarioSesion
  guardadoEn: string
}

export function guardarSesion(usuario: UsuarioSesion): void {
  guardarJson(CLAVE_SESION, { usuario, guardadoEn: new Date().toISOString() })
}

export function leerSesion(): UsuarioSesion | null {
  const sesion = leerJson<SesionOffline>(CLAVE_SESION)
  if (!sesion?.usuario || !sesion.guardadoEn) return null
  const edad = Date.now() - new Date(sesion.guardadoEn).getTime()
  if (!Number.isFinite(edad) || edad > MAX_EDAD_SESION_MS) {
    borrarSesion()
    return null
  }
  return sesion.usuario
}

export function borrarSesion(): void {
  borrar(CLAVE_SESION)
}

/* ----------------------------- Catálogo ----------------------------- */

export type CatalogoOffline = {
  productos: Producto[]
  clientes: Cliente[]
  caja: TurnoCaja | null
  guardadoEn: string
}

export function guardarCatalogo(datos: {
  productos: Producto[]
  clientes: Cliente[]
  caja: TurnoCaja | null
}): void {
  guardarJson(CLAVE_CATALOGO, {
    ...datos,
    guardadoEn: new Date().toISOString(),
  })
}

export function leerCatalogo(): CatalogoOffline | null {
  const datos = leerJson<CatalogoOffline>(CLAVE_CATALOGO)
  if (!datos || !Array.isArray(datos.productos) || !Array.isArray(datos.clientes)) {
    return null
  }
  return datos
}

export function guardarCajaActiva(caja: TurnoCaja | null): void {
  const catalogo = leerCatalogo()
  if (!catalogo) {
    // No crear un catálogo vacío: si aún no se cargaron productos/clientes,
    // la página de ventas debe saber que no hay caché utilizable.
    if (!caja) return
    guardarCatalogo({ productos: [], clientes: [], caja })
    return
  }
  guardarJson(CLAVE_CATALOGO, {
    ...catalogo,
    caja,
    guardadoEn: new Date().toISOString(),
  })
}

/* ----------------------------- Cola ----------------------------- */

export type EstadoOperacionOffline = 'pendiente' | 'sincronizando' | 'error'

export type DetalleOffline = {
  productoId: number
  codigo: string
  nombre: string
  cantidad: number
  precioUnitario: number
}

export type PagoOffline = {
  valor: number
  formaPago: FormaPago
}

export type OperacionOffline = {
  /** UUID local de la operación dentro de la cola. */
  id: string
  tipo: 'venta' | 'pago'
  creadaEn: string
  fecha: string
  usuarioId: number
  usuarioNombre: string
  turnoId: number | null
  facturaId: number | null
  clienteId: number | null
  nombreEventual: string | null
  detalles: DetalleOffline[]
  pagos: PagoOffline[]
  total: number
  estado: EstadoOperacionOffline
  intentos: number
  ultimoError: string | null
  pagoRegistrado: boolean
  claveVenta: string
  clavePago: string
}

export function leerCola(): OperacionOffline[] {
  const cola = leerJson<OperacionOffline[]>(CLAVE_COLA)
  return Array.isArray(cola) ? cola : []
}

export function guardarCola(cola: OperacionOffline[]): boolean {
  const ok = guardarJson(CLAVE_COLA, cola)
  if (ok) notificarColaCambiada()
  return ok
}

export function encolarOperacion(operacion: OperacionOffline): boolean {
  const cola = leerCola()
  cola.push(operacion)
  return guardarCola(cola)
}

export function actualizarOperacion(
  id: string,
  cambios: Partial<OperacionOffline>,
): void {
  const cola = leerCola()
  const indice = cola.findIndex((op) => op.id === id)
  if (indice < 0) return
  cola[indice] = { ...cola[indice], ...cambios }
  guardarCola(cola)
}

export function eliminarOperacion(id: string): void {
  guardarCola(leerCola().filter((op) => op.id !== id))
}

export function normalizarCola(): void {
  const cola = leerCola()
  let cambio = false
  const normalizada = cola.map((op) => {
    if (op.estado === 'sincronizando') {
      cambio = true
      return { ...op, estado: 'pendiente' as const }
    }
    return op
  })
  if (cambio) guardarCola(normalizada)
}

export function contarPendientes(cola = leerCola()): number {
  return cola.length
}

export function stockPendientePorProducto(
  cola = leerCola(),
): Map<number, number> {
  const pendiente = new Map<number, number>()
  for (const op of cola) {
    // Si la factura ya se creó en el servidor, el stock ya se descontó allí.
    if (op.tipo !== 'venta' || op.facturaId !== null) continue
    for (const detalle of op.detalles) {
      pendiente.set(
        detalle.productoId,
        (pendiente.get(detalle.productoId) ?? 0) + detalle.cantidad,
      )
    }
  }
  return pendiente
}

export function aplicarStockPendiente(
  productos: Producto[],
  cola = leerCola(),
): Producto[] {
  const pendiente = stockPendientePorProducto(cola)
  if (pendiente.size === 0) return productos
  return productos.map((producto) => {
    const reservado = pendiente.get(producto.id)
    return reservado ? { ...producto, stock: producto.stock - reservado } : producto
  })
}

/* ----------------------- Caché de listado de ventas ----------------------- */

type EntradaFacturas = { datos: PaginaFacturas; guardadoEn: string }
type CacheFacturas = Record<string, EntradaFacturas>

export function guardarFacturasCache(clave: string, datos: PaginaFacturas): void {
  const cache = leerJson<CacheFacturas>(CLAVE_FACTURAS) ?? {}
  cache[clave] = { datos, guardadoEn: new Date().toISOString() }
  const entradas = Object.entries(cache).sort(
    (a, b) =>
      new Date(b[1].guardadoEn).getTime() - new Date(a[1].guardadoEn).getTime(),
  )
  guardarJson(
    CLAVE_FACTURAS,
    Object.fromEntries(entradas.slice(0, MAX_CACHE_FACTURAS)),
  )
}

export function leerFacturasCache(clave: string): EntradaFacturas | null {
  return leerJson<CacheFacturas>(CLAVE_FACTURAS)?.[clave] ?? null
}

/* ----------------------- Caché de movimientos de caja ----------------------- */

type CacheMovsCaja = Record<string, { movimientos: RegistroCaja[]; guardadoEn: string }>

export function guardarMovimientosCaja(
  turnoId: number,
  movimientos: RegistroCaja[],
): void {
  const cache = leerJson<CacheMovsCaja>(CLAVE_MOVS_CAJA) ?? {}
  cache[String(turnoId)] = {
    movimientos,
    guardadoEn: new Date().toISOString(),
  }
  guardarJson(CLAVE_MOVS_CAJA, cache)
}

export function leerMovimientosCaja(turnoId: number): RegistroCaja[] | null {
  return leerJson<CacheMovsCaja>(CLAVE_MOVS_CAJA)?.[String(turnoId)]?.movimientos ?? null
}
