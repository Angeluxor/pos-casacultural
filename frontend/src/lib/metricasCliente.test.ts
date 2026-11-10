import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  enviarMetricas,
  esRutaMedible,
  normalizarRuta,
  pendientesMetricas,
  registrarMuestra,
  reiniciarMetricasCliente,
} from './metricasCliente'

beforeEach(() => reiniciarMetricasCliente())

describe('metricasCliente', () => {
  it('agrupa rutas con ids y quita el query string', () => {
    expect(normalizarRuta('/api/facturas/15/pagos?x=1')).toBe('/api/facturas/{id}/pagos')
  })

  it('no mide la salud ni las propias métricas', () => {
    expect(esRutaMedible('/api/health')).toBe(false)
    expect(esRutaMedible('/api/metricas/cliente')).toBe(false)
    expect(esRutaMedible('/api/ventas')).toBe(true)
  })

  it('acumula muestras y las envía por lote una sola vez', async () => {
    registrarMuestra('get', '/api/facturas/3', 200, 123.6)
    registrarMuestra('get', '/api/health', 200, 5)
    expect(pendientesMetricas()).toBe(1)

    const enviar = vi.fn().mockResolvedValue(undefined)
    await enviarMetricas(enviar)
    expect(enviar).toHaveBeenCalledWith([
      expect.objectContaining({
        metodo: 'GET',
        ruta: '/api/facturas/{id}',
        estado: 200,
        ms: 124,
      }),
    ])
    expect(pendientesMetricas()).toBe(0)
  })

  it('descarta el lote si el envío falla, sin lanzar', async () => {
    registrarMuestra('get', '/api/x', 0, 30000)
    await expect(
      enviarMetricas(() => Promise.reject(new Error('red'))),
    ).resolves.toBeUndefined()
    expect(pendientesMetricas()).toBe(0)
  })
})
