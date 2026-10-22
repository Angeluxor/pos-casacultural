import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './client'
import { crearFactura, pagarFactura } from './ventas'

const FACTURA = {
  id: 7,
  cliente_id: null,
  cliente_nombre: 'Cliente eventual',
  nombre_eventual: null,
  vendedor_id: 1,
  turno_caja_id: null,
  fecha: '2026-10-22T12:00:00-05:00',
  total: 5000,
  saldo: 5000,
  estado: 'Abierta',
  motivo_anulacion: null,
  fecha_anulacion: null,
  anulada_por_id: null,
  detalles: [],
  pagos: [],
}

const DATOS = {
  detalles: [{ producto_id: 3, cantidad: 1 }],
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('crearFactura', () => {
  it('envía la clave de idempotencia al backend', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(FACTURA), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await crearFactura(DATOS, { claveIdempotencia: 'venta-abc' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init.headers).get('Idempotency-Key')).toBe('venta-abc')
  })

  it('convierte un timeout en un ApiError marcado como tal', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener('abort', () => {
              reject(new DOMException('Aborted', 'AbortError'))
            })
          }),
      ),
    )

    await expect(
      crearFactura(DATOS, { claveIdempotencia: 'venta-timeout', timeoutMs: 10 }),
    ).rejects.toMatchObject<Partial<ApiError>>({
      status: 0,
      timeout: true,
    })
  })
})

describe('pagarFactura', () => {
  it('envía la clave de idempotencia al backend', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...FACTURA, saldo: 3000 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await pagarFactura(7, { valor: 2000, forma_pago: 'Efectivo' }, {
      claveIdempotencia: 'pago-abc',
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init.headers).get('Idempotency-Key')).toBe('pago-abc')
  })

  it('convierte un timeout del cobro en un ApiError marcado como tal', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener('abort', () => {
              reject(new DOMException('Aborted', 'AbortError'))
            })
          }),
      ),
    )

    await expect(
      pagarFactura(7, { valor: 2000, forma_pago: 'Efectivo' }, {
        claveIdempotencia: 'pago-timeout',
        timeoutMs: 10,
      }),
    ).rejects.toMatchObject<Partial<ApiError>>({
      status: 0,
      timeout: true,
    })
  })
})
