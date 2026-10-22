import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { crearFactura, obtenerFactura, pagarFactura } from '../api/ventas'
import { encolarOperacion, leerCola } from './almacen'
import { crearOperacionPago, crearOperacionVenta } from './operaciones'
import { sincronizarPendientes } from './sync'

vi.mock('../api/ventas', () => ({
  crearFactura: vi.fn(),
  pagarFactura: vi.fn(),
  obtenerFactura: vi.fn(),
}))

const crearFacturaMock = vi.mocked(crearFactura)
const pagarFacturaMock = vi.mocked(pagarFactura)
const obtenerFacturaMock = vi.mocked(obtenerFactura)

function venta(pagos = false) {
  return crearOperacionVenta({
    usuarioId: 1,
    usuarioNombre: 'Cajero',
    turnoId: 4,
    clienteId: null,
    nombreEventual: 'Cliente',
    detalles: [
      {
        productoId: 2,
        codigo: 'P2',
        nombre: 'Producto',
        cantidad: 2,
        precioUnitario: 1500,
      },
    ],
    pagos: pagos ? [{ valor: 3000, formaPago: 'Efectivo' }] : [],
    total: 3000,
  })
}

describe('sincronizarPendientes', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
  })

  it('envía una venta offline conservando fecha, turno y precio', async () => {
    const op = venta()
    encolarOperacion(op)
    crearFacturaMock.mockResolvedValue({
      id: 10,
      estado: 'Abierta',
      saldo: 3000,
    } as never)

    const resultado = await sincronizarPendientes(1)

    expect(resultado.sincronizadas).toBe(1)
    expect(leerCola()).toHaveLength(0)
    expect(crearFacturaMock).toHaveBeenCalledWith(
      expect.objectContaining({
        fecha: op.fecha,
        turno_caja_id: 4,
        origen_offline: true,
        detalles: [
          { producto_id: 2, cantidad: 2, precio_unitario: 1500 },
        ],
      }),
      { claveIdempotencia: op.claveVenta, timeoutMs: 30_000 },
    )
  })

  it('crea la venta y luego registra el cobro con su fecha y turno', async () => {
    const op = venta(true)
    encolarOperacion(op)
    crearFacturaMock.mockResolvedValue({
      id: 11,
      estado: 'Abierta',
      saldo: 3000,
    } as never)
    pagarFacturaMock.mockResolvedValue({ id: 11, estado: 'Pagada' } as never)

    const resultado = await sincronizarPendientes(1)

    expect(resultado.sincronizadas).toBe(1)
    expect(pagarFacturaMock).toHaveBeenCalledWith(
      11,
      [{ valor: 3000, forma_pago: 'Efectivo', fecha: op.fecha }],
      {
        claveIdempotencia: op.clavePago,
        turnoId: 4,
        timeoutMs: 30_000,
      },
    )
    expect(leerCola()).toHaveLength(0)
  })

  it('deja la operación pendiente si se cae la red', async () => {
    const op = venta()
    encolarOperacion(op)
    crearFacturaMock.mockRejectedValue(new ApiError(0, 'Sin conexión'))

    const resultado = await sincronizarPendientes(1)

    expect(resultado.sinConexion).toBe(true)
    expect(resultado.pendientes).toBe(1)
    const [pendiente] = leerCola()
    expect(pendiente.estado).toBe('pendiente')
    expect(pendiente.intentos).toBe(1)
  })

  it('no sincroniza operaciones de otro usuario', async () => {
    encolarOperacion(venta())

    const resultado = await sincronizarPendientes(99)

    expect(resultado.errores).toBe(1)
    expect(crearFacturaMock).not.toHaveBeenCalled()
    expect(leerCola()[0].estado).toBe('error')
    expect(leerCola()[0].ultimoError).toContain('pertenece')
  })

  it('marca error y conserva la factura si el cobro es rechazado', async () => {
    const op = venta(true)
    encolarOperacion(op)
    crearFacturaMock.mockResolvedValue({
      id: 12,
      estado: 'Abierta',
      saldo: 3000,
    } as never)
    pagarFacturaMock.mockRejectedValue(
      new ApiError(400, 'No hay una caja abierta actualmente.'),
    )
    obtenerFacturaMock.mockResolvedValue({ estado: 'Abierta' } as never)

    const resultado = await sincronizarPendientes(1)

    expect(resultado.errores).toBe(1)
    const [pendiente] = leerCola()
    expect(pendiente.estado).toBe('error')
    expect(pendiente.facturaId).toBe(12)
    expect(pendiente.ultimoError).toContain('caja abierta')
  })

  it('sincroniza un cobro suelto sobre una factura existente', async () => {
    const op = crearOperacionPago({
      usuarioId: 1,
      usuarioNombre: 'Cajero',
      turnoId: 4,
      facturaId: 20,
      pagos: [{ valor: 500, formaPago: 'Transferencia' }],
      total: 500,
    })
    encolarOperacion(op)
    pagarFacturaMock.mockResolvedValue({ id: 20, estado: 'Pagado Parcial' } as never)

    const resultado = await sincronizarPendientes(1)

    expect(resultado.sincronizadas).toBe(1)
    expect(crearFacturaMock).not.toHaveBeenCalled()
    expect(pagarFacturaMock).toHaveBeenCalledWith(
      20,
      [{ valor: 500, forma_pago: 'Transferencia', fecha: op.fecha }],
      expect.objectContaining({ turnoId: 4 }),
    )
  })
})
