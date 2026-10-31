import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { crearEnvioCantidades } from './cantidadesEnLote'

function deferred() {
  let resolve!: () => void
  let reject!: (err: unknown) => void
  const promise = new Promise<void>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('crearEnvioCantidades', () => {
  it('agrupa varios toques seguidos en una sola petición con el último valor', async () => {
    const enviar = vi.fn(async () => {})
    const envio = crearEnvioCantidades({ enviar, onCambio: () => {}, demoraMs: 300 })

    envio.cambiar(7, 2)
    envio.cambiar(7, 3)
    envio.cambiar(7, 4)
    expect(enviar).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(300)
    expect(enviar).toHaveBeenCalledTimes(1)
    expect(enviar).toHaveBeenCalledWith(7, 4)
  })

  it('muestra el valor pendiente al instante y lo limpia al confirmar', async () => {
    const cambios: Record<number, number>[] = []
    const envio = crearEnvioCantidades({
      enviar: async () => {},
      onCambio: (p) => cambios.push({ ...p }),
      demoraMs: 300,
    })

    envio.cambiar(7, 5)
    expect(cambios.at(-1)).toEqual({ 7: 5 })

    await vi.advanceTimersByTimeAsync(300)
    expect(cambios.at(-1)).toEqual({})
  })

  it('no manda dos peticiones a la vez para la misma línea; reenvía el valor más reciente', async () => {
    const primera = deferred()
    const enviar = vi
      .fn<(id: number, cantidad: number) => Promise<void>>()
      .mockImplementationOnce(() => primera.promise)
      .mockImplementationOnce(async () => {})
    const envio = crearEnvioCantidades({ enviar, onCambio: () => {}, demoraMs: 300 })

    envio.cambiar(7, 2)
    await vi.advanceTimersByTimeAsync(300)
    expect(enviar).toHaveBeenCalledWith(7, 2)

    // Cambio mientras la primera petición sigue en vuelo.
    envio.cambiar(7, 6)
    await vi.advanceTimersByTimeAsync(300)
    expect(enviar).toHaveBeenCalledTimes(1)

    primera.resolve()
    await vi.advanceTimersByTimeAsync(0)
    expect(enviar).toHaveBeenCalledTimes(2)
    expect(enviar).toHaveBeenLastCalledWith(7, 6)
  })

  it('si falla, descarta el pendiente y avisa del error', async () => {
    const cambios: Record<number, number>[] = []
    const error = new Error('Stock insuficiente')
    const onError = vi.fn()
    const envio = crearEnvioCantidades({
      enviar: async () => {
        throw error
      },
      onCambio: (p) => cambios.push({ ...p }),
      onError,
      demoraMs: 300,
    })

    envio.cambiar(7, 9)
    await vi.advanceTimersByTimeAsync(300)

    expect(onError).toHaveBeenCalledWith(error)
    expect(cambios.at(-1)).toEqual({})
  })

  it('vaciar envía de inmediato los pendientes sin esperar la pausa', async () => {
    const enviar = vi.fn(async () => {})
    const envio = crearEnvioCantidades({ enviar, onCambio: () => {}, demoraMs: 300 })

    envio.cambiar(7, 3)
    envio.cambiar(8, 1)
    await envio.vaciar()

    expect(enviar).toHaveBeenCalledTimes(2)
    expect(enviar).toHaveBeenCalledWith(7, 3)
    expect(enviar).toHaveBeenCalledWith(8, 1)

    // El temporizador original ya no debe disparar otra petición.
    await vi.advanceTimersByTimeAsync(500)
    expect(enviar).toHaveBeenCalledTimes(2)
  })
})
