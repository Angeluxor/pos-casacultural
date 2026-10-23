import { beforeEach, describe, expect, it } from 'vitest'
import {
  actualizarOperacion,
  aplicarStockPendiente,
  contarPendientes,
  encolarOperacion,
  guardarCatalogo,
  guardarFacturasCache,
  guardarSesion,
  leerCatalogo,
  leerCola,
  leerFacturasCache,
  leerSesion,
  normalizarCola,
  stockPendientePorProducto,
} from './almacen'
import {
  contarItemsPendientesFactura,
  crearOperacionItem,
  crearOperacionVenta,
  facturaConItemsPendientes,
} from './operaciones'
import type { Producto } from '../api/productos'
import type { Factura, PaginaFacturas } from '../api/ventas'
import type { UsuarioSesion } from '../api/types'

const PRODUCTO: Producto = {
  id: 1,
  codigo: 'P1',
  nombre: 'Producto',
  precio: 1000,
  stock: 10,
  misma_unidad_compra_venta: true,
}

const USUARIO: UsuarioSesion = {
  id: 7,
  username: 'cajero',
  nombre: 'Cajero',
  rol: 'Cajero',
  activo: true,
  cliente_id: null,
  cliente_nombre: null,
  permisos: [],
}

function operacionVenta() {
  return crearOperacionVenta({
    usuarioId: 7,
    usuarioNombre: 'Cajero',
    turnoId: 3,
    clienteId: null,
    nombreEventual: 'Cliente',
    detalles: [
      {
        productoId: 1,
        codigo: 'P1',
        nombre: 'Producto',
        cantidad: 2,
        precioUnitario: 1000,
      },
    ],
    pagos: [],
    total: 2000,
  })
}

describe('almacen offline', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('encola operaciones y descuenta el stock pendiente', () => {
    const op = operacionVenta()
    expect(encolarOperacion(op)).toBe(true)
    expect(contarPendientes()).toBe(1)

    expect(stockPendientePorProducto().get(1)).toBe(2)
    expect(aplicarStockPendiente([PRODUCTO])[0].stock).toBe(8)

    actualizarOperacion(op.id, { facturaId: 99 })
    expect(stockPendientePorProducto().get(1)).toBeUndefined()
    expect(aplicarStockPendiente([PRODUCTO])[0].stock).toBe(10)
  })

  it('descuenta el stock de un ítem pendiente de una factura existente', () => {
    const op = crearOperacionItem({
      usuarioId: 7,
      usuarioNombre: 'Cajero',
      turnoId: 3,
      facturaId: 42,
      detalle: {
        productoId: 1,
        codigo: 'P1',
        nombre: 'Producto',
        cantidad: 1,
        precioUnitario: 1000,
      },
    })
    encolarOperacion(op)

    expect(stockPendientePorProducto().get(1)).toBe(1)
    expect(aplicarStockPendiente([PRODUCTO])[0].stock).toBe(9)
  })

  it('suma los ítems pendientes al total y saldo de la factura', () => {
    const op = crearOperacionItem({
      usuarioId: 7,
      usuarioNombre: 'Cajero',
      turnoId: 3,
      facturaId: 42,
      detalle: {
        productoId: 1,
        codigo: 'P1',
        nombre: 'Producto',
        cantidad: 2,
        precioUnitario: 1000,
      },
    })
    encolarOperacion(op)

    const factura = {
      id: 42,
      total: 3000,
      saldo: 3000,
      estado: 'Abierta',
      pagos: [],
      detalles: [
        {
          id: 1,
          producto_id: 2,
          cantidad: 3,
          precio_unitario: 1000,
          subtotal: 3000,
          anulado: false,
        },
      ],
    } as unknown as Factura

    const conPendientes = facturaConItemsPendientes(factura, leerCola())
    expect(conPendientes.total).toBe(5000)
    expect(conPendientes.saldo).toBe(5000)
    expect(conPendientes.detalles).toHaveLength(2)
    expect(contarItemsPendientesFactura(42, leerCola())).toBe(2)
  })

  it('normaliza operaciones que quedaron sincronizando tras un cierre', () => {
    const op = operacionVenta()
    encolarOperacion({ ...op, estado: 'sincronizando' })
    normalizarCola()
    expect(leerCola()[0].estado).toBe('pendiente')
  })

  it('guarda catálogo, sesión y última página de ventas', () => {
    guardarCatalogo({ productos: [PRODUCTO], clientes: [], caja: null })
    expect(leerCatalogo()?.productos[0].id).toBe(1)

    guardarSesion(USUARIO)
    expect(leerSesion()?.id).toBe(7)

    const pagina = {
      items: [],
      total: 0,
      skip: 0,
      limit: 30,
      totales: {
        total_facturado: 0,
        saldo: 0,
        total_anulado: 0,
        neto: 0,
        facturas_anuladas: 0,
      },
    } as PaginaFacturas
    guardarFacturasCache('default', pagina)
    expect(leerFacturasCache('default')?.datos.total).toBe(0)
  })
})

describe('tipos de factura offline', () => {
  it('la factura expone la marca de revisión', () => {
    const factura = {
      id: 1,
      origen: 'offline',
      requiere_revision: true,
      nota_revision: 'Stock insuficiente',
    } as Factura
    expect(factura.requiere_revision).toBe(true)
  })
})
