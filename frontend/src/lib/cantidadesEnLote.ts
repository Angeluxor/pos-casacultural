/**
 * Envío en lote de cambios de cantidad por línea.
 *
 * Cada cambio se refleja de inmediato (vía `onCambio`) y se envía al servidor
 * tras una pausa sin nuevos cambios. Reglas:
 * - Solo hay una petición en vuelo por línea. Si llega un cambio mientras una
 *   petición está en curso, se envía el valor más reciente al terminar.
 * - Si la petición falla, el pendiente de esa línea se descarta (la línea vuelve
 *   al valor del servidor) y se avisa con `onError`.
 */
export type EnvioCantidades = {
  cambiar(detalleId: number, cantidad: number): void
  /** Envía de inmediato todos los pendientes (p. ej. al cerrar o cobrar). */
  vaciar(): Promise<void>
}

export type OpcionesEnvioCantidades = {
  enviar: (detalleId: number, cantidad: number) => Promise<void>
  onCambio: (pendientes: Record<number, number>) => void
  onError?: (err: unknown) => void
  demoraMs?: number
}

export function crearEnvioCantidades(opciones: OpcionesEnvioCantidades): EnvioCantidades {
  const demoraMs = opciones.demoraMs ?? 300
  let pendientes: Record<number, number> = {}
  const timers = new Map<number, ReturnType<typeof setTimeout>>()
  const enVuelo = new Set<number>()

  function publicar(siguiente: Record<number, number>) {
    pendientes = siguiente
    opciones.onCambio(pendientes)
  }

  function quitar(detalleId: number) {
    const siguiente = { ...pendientes }
    delete siguiente[detalleId]
    publicar(siguiente)
  }

  async function enviar(detalleId: number): Promise<void> {
    timers.delete(detalleId)
    // Hay una petición en vuelo: al terminar se reenvía el valor más reciente.
    if (enVuelo.has(detalleId)) return
    const cantidad = pendientes[detalleId]
    if (cantidad === undefined) return

    enVuelo.add(detalleId)
    try {
      await opciones.enviar(detalleId, cantidad)
      if (pendientes[detalleId] === cantidad && !timers.has(detalleId)) {
        quitar(detalleId)
      }
    } catch (err) {
      quitar(detalleId)
      opciones.onError?.(err)
    } finally {
      enVuelo.delete(detalleId)
    }
    if (pendientes[detalleId] !== undefined && !timers.has(detalleId)) {
      await enviar(detalleId)
    }
  }

  return {
    cambiar(detalleId, cantidad) {
      publicar({ ...pendientes, [detalleId]: cantidad })
      clearTimeout(timers.get(detalleId))
      timers.set(
        detalleId,
        setTimeout(() => void enviar(detalleId), demoraMs),
      )
    },
    async vaciar() {
      const ids = Object.keys(pendientes).map(Number)
      ids.forEach((id) => {
        clearTimeout(timers.get(id))
        timers.delete(id)
      })
      await Promise.all(ids.map((id) => enviar(id)))
    },
  }
}
