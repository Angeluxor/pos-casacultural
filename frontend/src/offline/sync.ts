import { ApiError, esErrorRed } from '../api/client'
import {
  agregarItemFacturaOffline,
  crearFactura,
  obtenerFactura,
  pagarFactura,
} from '../api/ventas'
import {
  actualizarOperacion,
  eliminarOperacion,
  leerCola,
  type OperacionOffline,
} from './almacen'

export type ResultadoSincronizacion = {
  sincronizadas: number
  pendientes: number
  errores: number
  sinConexion: boolean
}

function mensajeError(err: unknown): string {
  return err instanceof Error ? err.message : 'Error desconocido'
}

async function facturaYaPagada(facturaId: number): Promise<boolean> {
  try {
    const factura = await obtenerFactura(facturaId)
    return factura.estado === 'Pagada'
  } catch {
    return false
  }
}

async function sincronizarOperacion(
  op: OperacionOffline,
  usuarioId: number,
): Promise<'ok' | 'red' | 'error' | 'sesion'> {
  if (op.usuarioId !== usuarioId) {
    actualizarOperacion(op.id, {
      estado: 'error',
      ultimoError: `Esta operación pertenece a ${op.usuarioNombre}. Inicia sesión con ese usuario para sincronizarla.`,
    })
    return 'error'
  }

  actualizarOperacion(op.id, { estado: 'sincronizando', ultimoError: null })

  try {
    let facturaId = op.facturaId

    if (op.tipo === 'venta' && !facturaId) {
      const factura = await crearFactura(
        {
          cliente_id: op.clienteId,
          nombre_eventual: op.nombreEventual,
          fecha: op.fecha,
          turno_caja_id: op.turnoId,
          origen_offline: true,
          detalles: op.detalles.map((detalle) => ({
            producto_id: detalle.productoId,
            cantidad: detalle.cantidad,
            precio_unitario: detalle.precioUnitario,
          })),
        },
        { claveIdempotencia: op.claveVenta, timeoutMs: 30_000 },
      )
      facturaId = factura.id
      actualizarOperacion(op.id, { facturaId })
      if (factura.estado === 'Pagada') {
        eliminarOperacion(op.id)
        return 'ok'
      }
    }

    if (!facturaId) {
      throw new Error('La operación no tiene una factura asociada.')
    }

    if (op.tipo === 'item') {
      const detalle = op.detalles[0]
      if (!detalle) {
        throw new Error('La operación no tiene un producto asociado.')
      }
      await agregarItemFacturaOffline(
        facturaId,
        {
          producto_id: detalle.productoId,
          cantidad: detalle.cantidad,
          precio_unitario: detalle.precioUnitario,
        },
        {
          claveIdempotencia: op.claveItem ?? op.claveVenta,
          timeoutMs: 30_000,
        },
      )
      eliminarOperacion(op.id)
      return 'ok'
    }

    if (op.pagos.length > 0 && !op.pagoRegistrado) {
      try {
        await pagarFactura(
          facturaId,
          op.pagos.map((pago) => ({
            valor: pago.valor,
            forma_pago: pago.formaPago,
            fecha: op.fecha,
          })),
          {
            claveIdempotencia: op.clavePago,
            turnoId: op.turnoId ?? undefined,
            timeoutMs: 30_000,
          },
        )
      } catch (err) {
        // Si otro dispositivo ya cobró la factura, el objetivo de esta
        // operación está cumplido. Si fue anulada, hay que revisarla.
        if (err instanceof ApiError && err.status === 400) {
          if (await facturaYaPagada(facturaId)) {
            eliminarOperacion(op.id)
            return 'ok'
          }
        }
        throw err
      }
    }

    eliminarOperacion(op.id)
    return 'ok'
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      actualizarOperacion(op.id, {
        estado: 'error',
        intentos: op.intentos + 1,
        ultimoError:
          'La sesión expiró. Inicia sesión de nuevo para sincronizar esta operación.',
      })
      return 'sesion'
    }

    if (esErrorRed(err)) {
      actualizarOperacion(op.id, {
        estado: 'pendiente',
        intentos: op.intentos + 1,
        ultimoError: mensajeError(err),
      })
      return 'red'
    }

    actualizarOperacion(op.id, {
      estado: 'error',
      intentos: op.intentos + 1,
      ultimoError: mensajeError(err),
    })
    return 'error'
  }
}

/**
 * Envía al servidor las ventas y cobros guardados sin conexión.
 *
 * Es seguro ejecutarlo varias veces: cada operación lleva su propia clave de
 * idempotencia y el backend devuelve el resultado original si ya se guardó.
 */
export async function sincronizarPendientes(
  usuarioId: number,
): Promise<ResultadoSincronizacion> {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return {
      sincronizadas: 0,
      pendientes: leerCola().length,
      errores: 0,
      sinConexion: true,
    }
  }

  let sincronizadas = 0
  let errores = 0
  let sinConexion = false

  // Se usa una copia: la cola real se va modificando durante el recorrido.
  const operaciones = leerCola()
  for (const op of operaciones) {
    const resultado = await sincronizarOperacion(op, usuarioId)
    if (resultado === 'ok') {
      sincronizadas += 1
    } else if (resultado === 'error') {
      errores += 1
    } else if (resultado === 'red') {
      sinConexion = true
      break
    } else if (resultado === 'sesion') {
      errores += 1
      break
    }
  }

  return {
    sincronizadas,
    pendientes: leerCola().length,
    errores,
    sinConexion,
  }
}
