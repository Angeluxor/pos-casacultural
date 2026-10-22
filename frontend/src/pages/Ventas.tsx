import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import {
  actualizarItemFactura,
  agregarItemFactura,
  anularFactura,
  asignarClienteFactura,
  crearFactura,
  eliminarItemFactura,
  ESTADOS_FACTURA,
  listarFacturasPaginado,
  pagarFactura,
  type EstadoFactura,
  type Factura,
  type PaginaFacturas,
} from '../api/ventas'
import { listarProductos, type Producto } from '../api/productos'
import { listarClientes, type Cliente } from '../api/clientes'
import { obtenerCajaActiva, type TurnoCaja } from '../api/caja'
import type { FormaPago, UsuarioSesion } from '../api/types'
import { AyudaContextual } from '../components/AyudaContextual'
import { Paginacion } from '../components/Paginacion'
import { Stepper } from '../components/Stepper'
import { ThOrdenable } from '../components/ThOrdenable'
import { ApiError, esErrorRed } from '../api/client'
import { formatoFecha, moneda } from '../lib/formato'
import { crearClaveIdempotencia } from '../lib/idempotencia'
import { confirmarCierre } from '../lib/modal'
import { useOrdenServidor } from '../lib/orden'
import { Vacio } from '../components/Vacio'
import { useAuth } from '../auth/useAuth'
import { usePaginacion } from '../lib/usePaginacion'
import { useOffline } from '../offline/useOffline'
import {
  aplicarStockPendiente,
  encolarOperacion,
  guardarCatalogo,
  guardarFacturasCache,
  leerCatalogo,
  leerFacturasCache,
  type OperacionOffline,
} from '../offline/almacen'
import {
  crearOperacionPago,
  crearOperacionVenta,
  pagosDesdeLineas,
} from '../offline/operaciones'
import { FormCliente } from './Clientes'

const FORMAS_PAGO: FormaPago[] = ['Efectivo', 'Transferencia', 'Tarjeta']

const MOTIVOS_ANULACION = [
  'Error de digitación',
  'Devolución de producto',
  'Cliente canceló',
  'Producto agotado',
  'Duplicado',
  'Otro',
]

function contactoSecundario(c: Cliente): string {
  return c.celular || c.correo || ''
}

function claseEstado(estado: EstadoFactura): string {
  switch (estado) {
    case 'Pagada':
      return 'badge badge--on'
    case 'Pagado Parcial':
      return 'badge badge--info'
    case 'Crédito':
      return 'badge badge--credito'
    case 'Anulada':
      return 'badge badge--off'
    default:
      return 'badge badge--warn'
  }
}

export function Ventas() {
  const { usuario, tienePermiso } = useAuth()
  const {
    enLinea,
    operaciones,
    pendientes,
    sincronizando,
    sincronizarAhora,
    version,
  } = useOffline()
  const puedeCrear = tienePermiso('ventas.crear')
  const puedeCobrar = tienePermiso('ventas.cobrar')
  const puedeEditar = tienePermiso('ventas.editar')
  const puedeAnular = tienePermiso('ventas.anular')

  const [estado, setEstado] = useState<EstadoFactura | ''>('')
  const [listaDesdeCache, setListaDesdeCache] = useState(false)
  const cargarFacturas = useCallback(
    async (params: Parameters<typeof listarFacturasPaginado>[0]) => {
      const clave = JSON.stringify({ ...params, estado })
      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        const cache = leerFacturasCache(clave)
        if (cache) {
          setListaDesdeCache(true)
          return cache.datos
        }
        throw new ApiError(0, 'Sin conexión y no hay una lista de ventas guardada.')
      }
      try {
        const pagina = await listarFacturasPaginado({ ...params, estado }, 10_000)
        guardarFacturasCache(clave, pagina)
        setListaDesdeCache(false)
        return pagina
      } catch (err) {
        if (esErrorRed(err)) {
          const cache = leerFacturasCache(clave)
          if (cache) {
            setListaDesdeCache(true)
            return cache.datos
          }
        }
        throw err
      }
    },
    [estado],
  )

  const { orden, direccion, alternar } = useOrdenServidor()
  const {
    datos,
    skip,
    setSkip,
    buscar,
    setBuscar,
    desde,
    setDesde,
    hasta,
    setHasta,
    cargando,
    error,
    recargar,
    tamano,
  } = usePaginacion(cargarFacturas, 30, orden, direccion)
  const facturas = datos?.items ?? []
  const total = datos?.total ?? 0
  const totales = (datos as PaginaFacturas | null)?.totales
  const hayFiltros = buscar.trim() !== '' || desde !== '' || hasta !== '' || estado !== ''

  useEffect(() => {
    setSkip(0)
  }, [estado, setSkip])

  const [clientes, setClientes] = useState<Cliente[]>([])
  const [productos, setProductos] = useState<Producto[]>([])
  const [cajaActiva, setCajaActiva] = useState<TurnoCaja | null>(
    () => leerCatalogo()?.caja ?? null,
  )
  const enLineaPrevia = useRef(enLinea)
  const [cargandoCatalogo, setCargandoCatalogo] = useState(true)
  const [errorCatalogo, setErrorCatalogo] = useState('')
  const [mensaje, setMensaje] = useState('')

  const [nuevaAbierta, setNuevaAbierta] = useState(false)
  const [cobrar, setCobrar] = useState<Factura | null>(null)
  const [modoFactura, setModoFactura] = useState<'ver' | 'pagar'>('ver')

  const cargarCatalogo = useCallback(async () => {
    setCargandoCatalogo(true)
    const cacheLeido = leerCatalogo()
    // Un catálogo vacío puede ser solo la caja guardada por la página de Caja;
    // no sirve para vender.
    const cache =
      cacheLeido && cacheLeido.productos.length > 0 ? cacheLeido : null

    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      if (cache) {
        setClientes(cache.clientes)
        setProductos(cache.productos)
        setCajaActiva(cache.caja)
        setErrorCatalogo('')
      } else {
        setErrorCatalogo(
          'Sin conexión y no hay un catálogo guardado en este dispositivo. Abre la app una vez con conexión.',
        )
      }
      setCargandoCatalogo(false)
      return
    }

    try {
      const [c, p, caja] = await Promise.all([
        listarClientes({ timeoutMs: 10_000 }),
        listarProductos({ timeoutMs: 10_000 }),
        obtenerCajaActiva({ timeoutMs: 10_000 }),
      ])
      setClientes(c)
      setProductos(p)
      setCajaActiva(caja)
      guardarCatalogo({ productos: p, clientes: c, caja })
      setErrorCatalogo('')
    } catch (err) {
      if (esErrorRed(err) && cache) {
        setClientes(cache.clientes)
        setProductos(cache.productos)
        setCajaActiva(cache.caja)
        setErrorCatalogo(
          'Sin conexión: usando el catálogo guardado. Las ventas que registres quedarán pendientes de sincronizar.',
        )
      } else {
        setErrorCatalogo(
          err instanceof Error ? err.message : 'Error al cargar clientes y productos',
        )
      }
    } finally {
      setCargandoCatalogo(false)
    }
  }, [])

  useEffect(() => {
    void cargarCatalogo()
  }, [cargarCatalogo])

  // Después de una sincronización, el stock y el estado real de las facturas
  // pueden haber cambiado en el servidor.
  useEffect(() => {
    if (version > 0 && enLinea) {
      void cargarCatalogo()
      recargar()
    }
  }, [version, enLinea, cargarCatalogo, recargar])

  // Al recuperar la red también se refresca el catálogo aunque no hubiera
  // operaciones pendientes: los precios y el stock pueden haber cambiado.
  useEffect(() => {
    const recuperada = enLinea && !enLineaPrevia.current
    enLineaPrevia.current = enLinea
    if (recuperada) {
      void cargarCatalogo()
      recargar()
    }
  }, [enLinea, cargarCatalogo, recargar])

  const agregarCliente = useCallback((c: Cliente) => {
    setClientes((prev) => (prev.some((x) => x.id === c.id) ? prev : [...prev, c]))
  }, [])

  const productosConPendientes = useMemo(
    () => aplicarStockPendiente(productos, operaciones),
    [productos, operaciones],
  )
  const catalogoListo = !cargandoCatalogo && productos.length > 0

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Ventas</h1>
          <p className="ayuda">
            {total} facturas
            {pendientes > 0 ? ` · ${pendientes} pendiente(s) de sincronizar` : ''}
          </p>
        </div>
        {puedeCrear && (
          <button
            className="boton"
            onClick={() => setNuevaAbierta(true)}
            disabled={!catalogoListo || (!enLinea && !cajaActiva?.abierta)}
            title={
              !catalogoListo
                ? 'Cargando catálogo…'
                : !enLinea && !cajaActiva?.abierta
                  ? 'Para vender sin conexión necesitas una caja abierta guardada'
                  : undefined
            }
          >
            + Nueva venta
          </button>
        )}
      </header>

      <AyudaContextual
        titulo="Cómo registrar y cobrar"
        detalle="Crea facturas, cobra saldos y anula ventas. Para vender o cobrar debe haber una caja abierta. Una factura abierta se puede editar; al pagarse o pasar a crédito queda bloqueada. Anular devuelve el stock y exige un motivo."
      />

      {pendientes > 0 && (
        <OperacionesPendientes
          operaciones={operaciones}
          enLinea={enLinea}
          sincronizando={sincronizando}
          onSincronizar={() => void sincronizarAhora()}
        />
      )}

      {listaDesdeCache && (
        <p className="ayuda">
          Sin conexión: mostrando la última lista de ventas guardada en este
          dispositivo.
        </p>
      )}

      <div className="barra">
        <input
          className="campo-busqueda"
          placeholder="Buscar por # factura o cliente…"
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
        />
        <label className="campo-fecha">
          <span>Desde</span>
          <input
            type="date"
            value={desde}
            max={hasta || undefined}
            onChange={(e) => setDesde(e.target.value)}
          />
        </label>
        <label className="campo-fecha">
          <span>Hasta</span>
          <input
            type="date"
            value={hasta}
            min={desde || undefined}
            onChange={(e) => setHasta(e.target.value)}
          />
        </label>
        <label className="campo-fecha">
          <span>Estado</span>
          <select
            value={estado}
            onChange={(e) => setEstado(e.target.value as EstadoFactura | '')}
          >
            <option value="">Todas</option>
            {ESTADOS_FACTURA.map((op) => (
              <option key={op} value={op}>
                {op}
              </option>
            ))}
          </select>
        </label>
        {hayFiltros && (
          <button
            type="button"
            className="boton boton--mini boton--secundario"
            onClick={() => {
              setBuscar('')
              setDesde('')
              setHasta('')
              setEstado('')
            }}
          >
            Limpiar filtros
          </button>
        )}
      </div>

      {errorCatalogo && <p className="error">Catálogo: {errorCatalogo}</p>}
      {mensaje && <p className="aviso">{mensaje}</p>}

      {totales && total > 0 && !error && !cargando && (
        <>
          <p className="ayuda">
            Totales de todos los resultados que cumplen los filtros:
          </p>
          <div className="tarjetas">
            <div className="mini-tarjeta">
              <span className="mini-tarjeta__label">Total facturado</span>
              <strong>{moneda.format(totales.total_facturado)}</strong>
            </div>
            <div className="mini-tarjeta">
              <span className="mini-tarjeta__label">Saldo pendiente</span>
              <strong>{moneda.format(totales.saldo)}</strong>
            </div>
            <div className="mini-tarjeta">
              <span className="mini-tarjeta__label">Anulado</span>
              <strong>{moneda.format(totales.total_anulado)}</strong>
              {totales.facturas_anuladas > 0 && (
                <small>{totales.facturas_anuladas} factura(s)</small>
              )}
            </div>
            <div className="mini-tarjeta">
              <span className="mini-tarjeta__label">Neto</span>
              <strong>{moneda.format(totales.neto)}</strong>
            </div>
          </div>
        </>
      )}

      {cargando ? (
        <p className="ayuda">Cargando…</p>
      ) : error ? (
        <p className="error">{error}</p>
      ) : facturas.length === 0 ? (
        <Vacio
          titulo={hayFiltros ? 'Sin resultados' : 'Aún no hay ventas'}
          detalle={
            hayFiltros
              ? 'No hay facturas que coincidan con los filtros aplicados.'
              : 'Registra tu primera venta con «Nueva venta».'
          }
        />
      ) : (
        <>
          <div className="tabla-wrap tabla-wrap--cards">
            <table className="tabla tabla--cards">
              <thead>
                <tr>
                  <ThOrdenable campo="id" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    #
                  </ThOrdenable>
                  <ThOrdenable campo="fecha" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Fecha
                  </ThOrdenable>
                  <ThOrdenable campo="cliente" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Cliente
                  </ThOrdenable>
                  <ThOrdenable
                    campo="total"
                    orden={orden}
                    direccion={direccion}
                    onOrdenar={alternar}
                    className="derecha"
                  >
                    Total
                  </ThOrdenable>
                  <ThOrdenable
                    campo="saldo"
                    orden={orden}
                    direccion={direccion}
                    onOrdenar={alternar}
                    className="derecha"
                  >
                    Saldo
                  </ThOrdenable>
                  <ThOrdenable campo="estado" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Estado
                  </ThOrdenable>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {facturas.map((f) => (
                  <tr key={f.id}>
                    <td data-label="Factura">#{f.id}</td>
                    <td data-label="Fecha">{formatoFecha(f.fecha)}</td>
                    <td data-label="Cliente">{f.cliente_nombre || '—'}</td>
                    <td data-label="Total" className="derecha">
                      {moneda.format(f.total)}
                    </td>
                    <td data-label="Saldo" className="derecha">
                      {moneda.format(f.saldo)}
                    </td>
                    <td data-label="Estado">
                      <span className={claseEstado(f.estado)}>{f.estado}</span>
                      {f.requiere_revision && (
                        <span
                          className="badge badge--warn badge--revision"
                          title={f.nota_revision ?? 'Venta offline para revisar'}
                        >
                          Revisar
                        </span>
                      )}
                    </td>
                    <td className="celda-accion">
                      <div className="acciones-fila">
                        <button
                          className="boton boton--mini"
                          onClick={() => {
                            setModoFactura('ver')
                            setCobrar(f)
                          }}
                        >
                          Ver
                        </button>
                        {f.saldo > 0 && f.estado !== 'Anulada' && puedeCobrar && (
                          <button
                            className="boton boton--mini"
                            onClick={() => {
                              setModoFactura('pagar')
                              setCobrar(f)
                            }}
                          >
                            Pagar
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginacion
            total={total}
            skip={skip}
            limit={tamano}
            onCambiar={setSkip}
            cargando={cargando}
          />
        </>
      )}

      {nuevaAbierta && (
        <FormVenta
          clientes={clientes}
          productos={productosConPendientes}
          catalogoListo={catalogoListo}
          enLinea={enLinea}
          turnoId={cajaActiva?.abierta ? cajaActiva.id : null}
          usuario={usuario}
          onClienteCreado={agregarCliente}
          onCerrar={() => setNuevaAbierta(false)}
          onGuardado={(aviso) => {
            setNuevaAbierta(false)
            setMensaje(aviso ?? '')
            if (enLinea) recargar()
          }}
        />
      )}

      {cobrar && (
        <FormCobro
          factura={cobrar}
          productos={productosConPendientes}
          clientes={clientes}
          puedeEditar={puedeEditar}
          puedeAnular={puedeAnular}
          modo={modoFactura}
          enLinea={enLinea}
          turnoId={cajaActiva?.abierta ? cajaActiva.id : null}
          usuario={usuario}
          onCerrar={() => {
            setCobrar(null)
            if (enLinea) recargar()
          }}
          onGuardado={(aviso) => {
            setCobrar(null)
            setMensaje(aviso ?? '')
            if (enLinea) recargar()
          }}
        />
      )}
    </div>
  )
}

function OperacionesPendientes({
  operaciones,
  enLinea,
  sincronizando,
  onSincronizar,
}: {
  operaciones: OperacionOffline[]
  enLinea: boolean
  sincronizando: boolean
  onSincronizar: () => void
}) {
  return (
    <section className="operaciones-pendientes">
      <div className="operaciones-pendientes__head">
        <div>
          <strong>Operaciones guardadas sin conexión</strong>
          <p className="ayuda">
            Se enviarán al servidor cuando haya red. No cierres la caja hasta
            que esta lista quede vacía.
          </p>
        </div>
        <button
          type="button"
          className="boton boton--mini"
          onClick={onSincronizar}
          disabled={!enLinea || sincronizando}
        >
          {sincronizando ? 'Sincronizando…' : 'Sincronizar ahora'}
        </button>
      </div>
      <ul>
        {operaciones.map((op) => {
          const referencia = op.facturaId
            ? `Factura #${op.facturaId}`
            : `Ref. ${op.id.slice(0, 8)}`
          const cobro = op.pagos.length > 0 ? ' · cobro incluido' : ''
          return (
            <li key={op.id} className={`operacion-pendiente operacion-pendiente--${op.estado}`}>
              <div>
                <strong>
                  {op.tipo === 'venta' ? 'Venta' : 'Cobro'} {referencia}
                  {cobro}
                </strong>
                <span>
                  {formatoFecha(op.fecha)} · {moneda.format(op.total)} ·{' '}
                  {op.usuarioNombre}
                </span>
                {op.estado === 'error' && op.ultimoError && (
                  <small className="error">{op.ultimoError}</small>
                )}
              </div>
              <span className="badge badge--warn">
                {op.estado === 'error' ? 'Revisar' : 'Pendiente'}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

type ItemVenta = { producto: Producto; cantidad: number }

function round2(n: number): number {
  return Math.round(n * 100) / 100
}

function errorReintentable(err: unknown): boolean {
  // 0 = red caída o timeout; 503 = la base de datos no respondió a tiempo.
  // Ambos son seguros de reintentar porque la clave de idempotencia evita
  // duplicar la operación si el primer intento sí alcanzó a guardarse.
  return err instanceof ApiError && (err.status === 0 || err.status === 503)
}

/**
 * Envía un cobro con un reintento seguro.
 *
 * Si la primera petición alcanzó a guardarse pero la respuesta se perdió, el
 * reintento usa la misma clave y el backend devuelve la factura ya cobrada en
 * vez de insertar los pagos y los movimientos de caja otra vez.
 */
async function registrarPagoConReintento(
  facturaId: number,
  pagos: { valor: number; forma_pago: FormaPago }[],
  claveIdempotencia: string,
): Promise<Factura> {
  const enviar = () =>
    pagarFactura(facturaId, pagos, { claveIdempotencia, timeoutMs: 30_000 })
  try {
    return await enviar()
  } catch (err) {
    if (errorReintentable(err)) {
      return enviar()
    }
    throw err
  }
}

type LineaPago = { forma_pago: FormaPago; valor: string }

function MediosPago({
  total,
  lineas,
  onCambiar,
  disabled,
}: {
  total: number
  lineas: LineaPago[]
  onCambiar: (lineas: LineaPago[]) => void
  disabled?: boolean
}) {
  const asignado = round2(lineas.reduce((acc, l) => acc + (Number(l.valor) || 0), 0))
  const falta = round2(total - asignado)

  function setLinea(idx: number, parcial: Partial<LineaPago>) {
    onCambiar(lineas.map((l, i) => (i === idx ? { ...l, ...parcial } : l)))
  }

  function agregar() {
    const resto = Math.max(0, round2(total - asignado))
    onCambiar([...lineas, { forma_pago: 'Efectivo', valor: String(resto) }])
  }

  return (
    <div className="medios-pago">
      <p className="ayuda">Medios de pago</p>
      {lineas.map((l, idx) => (
        <div className="fila-pago" key={idx}>
          <select
            value={l.forma_pago}
            disabled={disabled}
            onChange={(e) => setLinea(idx, { forma_pago: e.target.value as FormaPago })}
          >
            {FORMAS_PAGO.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
          <input
            type="number"
            min="0"
            step="0.01"
            value={l.valor}
            disabled={disabled}
            onChange={(e) => setLinea(idx, { valor: e.target.value })}
          />
          {lineas.length > 1 && (
            <button
              type="button"
              className="boton boton--mini boton--secundario"
              disabled={disabled}
              onClick={() => onCambiar(lineas.filter((_, i) => i !== idx))}
            >
              Quitar
            </button>
          )}
        </div>
      ))}
      <div className="acciones-fila">
        <button
          type="button"
          className="boton boton--mini boton--secundario"
          onClick={agregar}
          disabled={disabled}
        >
          + Añadir medio de pago
        </button>
      </div>
      <p className={falta === 0 ? 'ayuda' : 'error'}>
        {falta === 0
          ? 'Reparto completo.'
          : falta > 0
            ? `Falta por asignar ${moneda.format(falta)}.`
            : `Excede por ${moneda.format(-falta)}.`}
      </p>
    </div>
  )
}


function FormVenta({
  clientes,
  productos,
  catalogoListo,
  enLinea,
  turnoId,
  usuario,
  onClienteCreado,
  onCerrar,
  onGuardado,
}: {
  clientes: Cliente[]
  productos: Producto[]
  catalogoListo: boolean
  enLinea: boolean
  turnoId: number | null
  usuario: UsuarioSesion | null
  onClienteCreado: (cliente: Cliente) => void
  onCerrar: () => void
  onGuardado: (aviso?: string) => void
}) {
  const { tienePermiso } = useAuth()
  const puedeCobrar = tienePermiso('ventas.cobrar')
  const [cliente, setCliente] = useState<Cliente | null>(null)
  const [nombreEventual, setNombreEventual] = useState('')
  const [creandoCliente, setCreandoCliente] = useState(false)
  const [buscarCliente, setBuscarCliente] = useState('')
  const [eligiendoCliente, setEligiendoCliente] = useState(false)
  const [items, setItems] = useState<ItemVenta[]>([])
  const [buscarProducto, setBuscarProducto] = useState('')
  const [cobrarAhora, setCobrarAhora] = useState(false)
  const [montoCobro, setMontoCobro] = useState('')
  const [montoEditado, setMontoEditado] = useState(false)
  const [pagos, setPagos] = useState<LineaPago[]>([])
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  const total = useMemo(
    () => items.reduce((acc, i) => acc + i.producto.precio * i.cantidad, 0),
    [items],
  )

  // Mantiene el monto a cobrar sincronizado con el total de la venta mientras el
  // usuario no lo haya editado a mano.
  useEffect(() => {
    if (cobrarAhora && !montoEditado) setMontoCobro(String(total))
  }, [total, cobrarAhora, montoEditado])

  // Con un único medio de pago, su valor sigue al monto a cobrar.
  useEffect(() => {
    if (!cobrarAhora) return
    setPagos((prev) => (prev.length === 1 ? [{ ...prev[0], valor: montoCobro }] : prev))
  }, [montoCobro, cobrarAhora])

  const resultados = useMemo(() => {
    const q = buscarProducto.trim().toLowerCase()
    if (!q) return []
    return productos
      .filter((p) => p.codigo.toLowerCase().includes(q) || p.nombre.toLowerCase().includes(q))
      .slice(0, 8)
  }, [productos, buscarProducto])

  const resultadosClientes = useMemo(() => {
    const q = buscarCliente.trim().toLowerCase()
    if (!q) return []
    return clientes
      .filter((c) => {
        const contacto = `${c.celular ?? ''} ${c.correo ?? ''}`.toLowerCase()
        return c.nombre.toLowerCase().includes(q) || contacto.includes(q)
      })
      .slice(0, 8)
  }, [clientes, buscarCliente])

  function agregar(p: Producto) {
    setItems((prev) => {
      const existente = prev.find((i) => i.producto.id === p.id)
      if (existente) {
        return prev.map((i) =>
          i.producto.id === p.id ? { ...i, cantidad: i.cantidad + 1 } : i,
        )
      }
      return [...prev, { producto: p, cantidad: 1 }]
    })
    setBuscarProducto('')
  }

  function cambiarCantidad(id: number, cantidad: number) {
    setItems((prev) => prev.map((i) => (i.producto.id === id ? { ...i, cantidad } : i)))
  }

  function quitar(id: number) {
    setItems((prev) => prev.filter((i) => i.producto.id !== id))
  }

  function alternarCobro(activo: boolean) {
    setCobrarAhora(activo)
    if (activo) {
      setMontoEditado(false)
      setMontoCobro(String(total))
      setPagos([{ forma_pago: 'Efectivo', valor: String(total) }])
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (items.length === 0) {
      setError('Agrega al menos un producto')
      return
    }
    if (cobrarAhora) {
      const monto = Number(montoCobro)
      if (!monto || monto <= 0 || monto > total) {
        setError(
          `El monto a cobrar debe ser mayor a 0 y no superar el total (${moneda.format(total)})`,
        )
        return
      }
      const suma = round2(pagos.reduce((acc, p) => acc + (Number(p.valor) || 0), 0))
      if (pagos.some((p) => (Number(p.valor) || 0) <= 0)) {
        setError('Cada medio de pago debe tener un valor mayor a 0')
        return
      }
      if (suma !== round2(monto)) {
        setError('La suma de los medios de pago debe coincidir con el monto a cobrar')
        return
      }
    }
    setGuardando(true)
    if (!usuario) {
      setError('No hay una sesión válida. Vuelve a iniciar sesión.')
      setGuardando(false)
      return
    }

    const detalles = items.map((i) => ({
      productoId: i.producto.id,
      codigo: i.producto.codigo,
      nombre: i.producto.nombre,
      cantidad: i.cantidad,
      precioUnitario: i.producto.precio,
    }))
    const pagosOperacion = cobrarAhora ? pagosDesdeLineas(pagos) : []
    const operacion = crearOperacionVenta({
      usuarioId: usuario.id,
      usuarioNombre: usuario.nombre || usuario.username,
      turnoId,
      clienteId: cliente?.id ?? null,
      nombreEventual: cliente ? null : nombreEventual.trim() || null,
      detalles,
      pagos: pagosOperacion,
      total: round2(total),
    })

    function guardarEnDispositivo(op: OperacionOffline = operacion): boolean {
      if (op.tipo === 'venta' && !turnoId) {
        setError(
          'Necesitas una caja abierta para vender sin conexión. Ábrela cuando tengas red y vuelve a intentarlo.',
        )
        return false
      }
      if (!encolarOperacion(op)) {
        setError(
          'No se pudo guardar la operación en este dispositivo (almacenamiento lleno o bloqueado). No se registró nada.',
        )
        return false
      }
      return true
    }

    if (!enLinea || (typeof navigator !== 'undefined' && !navigator.onLine)) {
      if (guardarEnDispositivo()) {
        onGuardado(
          'Venta guardada en el dispositivo. Se sincronizará automáticamente cuando vuelva la conexión.',
        )
      }
      setGuardando(false)
      return
    }

    const datos = {
      cliente_id: operacion.clienteId,
      nombre_eventual: operacion.nombreEventual,
      detalles: items.map((i) => ({
        producto_id: i.producto.id,
        cantidad: i.cantidad,
      })),
    }
    try {
      let factura: Factura
      try {
        factura = await crearFactura(datos, {
          claveIdempotencia: operacion.claveVenta,
          timeoutMs: 30_000,
        })
      } catch (err) {
        // Un timeout o una caída de red es ambiguo: el servidor pudo guardar
        // la venta. Reintentamos una vez con la misma clave; si ya existe, el
        // backend devuelve la factura original sin descontar stock otra vez.
        if (errorReintentable(err)) {
          factura = await crearFactura(datos, {
            claveIdempotencia: operacion.claveVenta,
            timeoutMs: 30_000,
          })
        } else {
          throw err
        }
      }
      if (
        cobrarAhora &&
        factura.saldo > 0 &&
        !['Pagada', 'Anulada', 'Crédito'].includes(factura.estado)
      ) {
        try {
          await registrarPagoConReintento(
            factura.id,
            pagosOperacion.map((p) => ({ valor: p.valor, forma_pago: p.formaPago })),
            operacion.clavePago,
          )
        } catch (err) {
          if (esErrorRed(err)) {
            const ahora = new Date().toISOString()
            const pagoPendiente: OperacionOffline = {
              ...operacion,
              id: crearClaveIdempotencia(),
              tipo: 'pago',
              creadaEn: ahora,
              fecha: ahora,
              facturaId: factura.id,
              detalles: [],
              total: round2(
                pagosOperacion.reduce((acc, p) => acc + p.valor, 0),
              ),
              estado: 'pendiente',
              intentos: 0,
              ultimoError: null,
              pagoRegistrado: false,
            }
            if (guardarEnDispositivo(pagoPendiente)) {
              onGuardado(
                `Venta #${factura.id} registrada. El cobro quedó guardado en el dispositivo y se sincronizará al volver la conexión.`,
              )
            } else {
              onGuardado(
                `La venta #${factura.id} quedó registrada, pero el cobro no se pudo guardar en el dispositivo. Cobra el saldo desde la lista cuando tengas conexión.`,
              )
            }
            return
          }
          const msg = err instanceof Error ? err.message : 'error desconocido'
          const motivo =
            err instanceof ApiError && err.timeout
              ? 'la conexión tardó demasiado y no se confirmó el cobro'
              : `el cobro falló: ${msg}`
          onGuardado(
            `Venta #${factura.id} registrada, pero ${motivo}. Revisa la factura en la lista antes de reintentar el cobro: puede que ya esté registrado.`,
          )
          return
        }
      }
      onGuardado()
    } catch (err) {
      if (esErrorRed(err)) {
        if (guardarEnDispositivo()) {
          onGuardado(
            'Sin conexión: la venta quedó guardada en el dispositivo y se sincronizará cuando vuelva la red.',
          )
        }
      } else {
        setError(err instanceof Error ? err.message : 'Error al registrar la venta')
      }
    } finally {
      setGuardando(false)
    }
  }

  return (
    <>
    <div className="modal-overlay modal-overlay--full" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal modal--ancho" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>Nueva venta</h2>
        {error && <p className="error">{error}</p>}
        {!catalogoListo && <p className="ayuda">Cargando catálogo de productos…</p>}

        <label htmlFor="venta-cliente">Cliente (opcional)</label>
        {cliente ? (
          <div className="seleccion-chip">
            <span>
              {cliente.nombre}
              {contactoSecundario(cliente) ? ` — ${contactoSecundario(cliente)}` : ''}
            </span>
            <button
              type="button"
              className="boton boton--mini"
              onClick={() => {
                setCliente(null)
                setEligiendoCliente(false)
              }}
            >
              Quitar
            </button>
          </div>
        ) : eligiendoCliente ? (
          <div className="buscador-producto">
            <input
              id="venta-cliente"
              autoFocus
              placeholder="Buscar cliente por nombre, celular o correo…"
              value={buscarCliente}
              onChange={(e) => setBuscarCliente(e.target.value)}
            />
            {resultadosClientes.length > 0 && (
              <ul className="sugerencias">
                {resultadosClientes.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setCliente(c)
                        setBuscarCliente('')
                        setEligiendoCliente(false)
                      }}
                    >
                      <span>{c.nombre}</span>
                      <span className="ayuda">{contactoSecundario(c)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {buscarCliente.trim() && resultadosClientes.length === 0 && (
              <p className="ayuda">Sin coincidencias para «{buscarCliente.trim()}».</p>
            )}
            <button
              type="button"
              className="boton boton--secundario boton--mini enlace-ver-mas"
              onClick={() => {
                setBuscarCliente('')
                setEligiendoCliente(false)
              }}
            >
              Usar cliente eventual
            </button>
          </div>
        ) : (
          <div className="cliente-venta">
            <div className="seleccion-chip seleccion-chip--defecto">
              <span className="cliente-defecto">
                Cliente eventual
                <span
                  className="info-tip"
                  tabIndex={0}
                  role="img"
                  aria-label="Sugerencia sobre clientes"
                >
                  i
                  <span className="info-tip__globito">
                    Se recomienda registrar y seleccionar al cliente siempre que sea posible, para
                    llevar su historial de compras.
                  </span>
                </span>
              </span>
              <div className="acciones-fila">
                <button
                  type="button"
                  className="boton boton--mini"
                  onClick={() => setEligiendoCliente(true)}
                >
                  Elegir cliente
                </button>
                <button
                  type="button"
                  className="boton boton--mini boton--secundario"
                  onClick={() => setCreandoCliente(true)}
                  disabled={!enLinea}
                  title={
                    enLinea
                      ? undefined
                      : 'Crear clientes requiere conexión. Puedes vender con un cliente existente o como eventual.'
                  }
                >
                  Crear cliente
                </button>
              </div>
            </div>
            <label htmlFor="venta-nombre-eventual" className="campo-nombre-eventual">
              <span>Nombre (opcional)</span>
              <input
                id="venta-nombre-eventual"
                placeholder="Nombre temporal del cliente"
                value={nombreEventual}
                onChange={(e) => setNombreEventual(e.target.value)}
                maxLength={100}
              />
            </label>
          </div>
        )}

        <div className="buscador-producto">
          <input
            placeholder="Buscar producto por código o nombre…"
            value={buscarProducto}
            onChange={(e) => setBuscarProducto(e.target.value)}
            disabled={!catalogoListo}
          />
          {resultados.length > 0 && (
            <ul className="sugerencias">
              {resultados.map((p) => (
                <li key={p.id}>
                  <button type="button" onClick={() => agregar(p)}>
                    <span>
                      {p.codigo} · {p.nombre}
                    </span>
                    <span className="ayuda">
                      {moneda.format(p.precio)} · stock {p.stock}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {catalogoListo && buscarProducto.trim() && resultados.length === 0 && (
            <p className="ayuda">Sin coincidencias para «{buscarProducto.trim()}».</p>
          )}
        </div>

        <div className="tabla-wrap tabla-wrap--cards">
          <table className="tabla tabla--cards">
            <thead>
              <tr>
                <th>Producto</th>
                <th className="derecha">Precio</th>
                <th className="derecha">Cant.</th>
                <th className="derecha">Subtotal</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.producto.id}>
                  <td data-label="Producto">{i.producto.nombre}</td>
                  <td data-label="Precio" className="derecha">
                    {moneda.format(i.producto.precio)}
                  </td>
                  <td data-label="Cant." className="derecha">
                    <Stepper
                      valor={i.cantidad}
                      disabled={guardando}
                      etiqueta={i.producto.nombre}
                      onCambiar={(n) => cambiarCantidad(i.producto.id, n)}
                    />
                  </td>
                  <td data-label="Subtotal" className="derecha">
                    {moneda.format(i.producto.precio * i.cantidad)}
                  </td>
                  <td className="celda-accion">
                    <div className="acciones-fila">
                      <button
                        type="button"
                        className="boton boton--mini boton--danger"
                        onClick={() => quitar(i.producto.id)}
                      >
                        Quitar
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={5} data-label="" className="ayuda">
                    Agrega productos a la venta
                  </td>
                </tr>
              )}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={3} className="derecha">
                  <strong>Total</strong>
                </td>
                <td className="derecha">
                  <strong>{moneda.format(total)}</strong>
                </td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>

        {puedeCobrar && (
          <label className="check">
            <input
              type="checkbox"
              checked={cobrarAhora}
              onChange={(e) => alternarCobro(e.target.checked)}
            />
            Cobrar ahora
          </label>
        )}

        {puedeCobrar && cobrarAhora && (
          <div className="bloque-pago">
            <label>
              Monto a cobrar
              <input
                type="number"
                min="0"
                step="0.01"
                value={montoCobro}
                onChange={(e) => {
                  setMontoEditado(true)
                  setMontoCobro(e.target.value)
                }}
              />
            </label>
            <MediosPago
              total={Number(montoCobro) || 0}
              lineas={pagos}
              onCambiar={setPagos}
              disabled={guardando}
            />
          </div>
        )}

        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button type="submit" className="boton" disabled={guardando || !catalogoListo}>
            {guardando ? 'Guardando…' : 'Registrar venta'}
          </button>
        </div>
      </form>
      </div>
      {creandoCliente && (
        <FormCliente
          cliente={null}
          onCerrar={() => setCreandoCliente(false)}
          onGuardado={(creado) => {
            setCreandoCliente(false)
            if (creado) {
              onClienteCreado(creado)
              setCliente(creado)
              setNombreEventual('')
            }
          }}
        />
      )}
    </>
  )
}

function FormCobro({
  factura,
  productos,
  clientes,
  puedeEditar,
  puedeAnular,
  modo,
  enLinea,
  turnoId,
  usuario,
  onCerrar,
  onGuardado,
}: {
  factura: Factura
  productos: Producto[]
  clientes: Cliente[]
  puedeEditar: boolean
  puedeAnular: boolean
  modo: 'ver' | 'pagar'
  enLinea: boolean
  turnoId: number | null
  usuario: UsuarioSesion | null
  onCerrar: () => void
  onGuardado: (aviso?: string) => void
}) {
  const [f, setF] = useState<Factura>(factura)
  const [monto, setMonto] = useState(String(factura.saldo))
  const [pagos, setPagos] = useState<LineaPago[]>([
    { forma_pago: 'Efectivo', valor: String(factura.saldo) },
  ])
  const [buscar, setBuscar] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [anulando, setAnulando] = useState(false)
  const [mostrandoAnular, setMostrandoAnular] = useState(false)
  const [motivoAnular, setMotivoAnular] = useState(MOTIVOS_ANULACION[0])
  const [motivoOtro, setMotivoOtro] = useState('')
  const [asignando, setAsignando] = useState(false)
  const [buscarCliente, setBuscarCliente] = useState('')

  const productosPorId = useMemo(() => new Map(productos.map((p) => [p.id, p])), [productos])
  const esPago = modo === 'pagar'
  const facturaAbierta = f.estado !== 'Anulada'
  const editable = facturaAbierta && modo === 'ver' && puedeEditar && enLinea
  const puedeAnularAqui = facturaAbierta && modo === 'ver' && puedeAnular && enLinea
  const puedePagar = facturaAbierta && modo === 'pagar' && f.saldo > 0
  const activos = f.detalles.filter((d) => !d.anulado)
  const unaSolaLinea = activos.length <= 1

  // Con un único medio de pago, su valor sigue al monto del pago.
  useEffect(() => {
    setPagos((prev) => (prev.length === 1 ? [{ ...prev[0], valor: monto }] : prev))
  }, [monto])

  const resultados = useMemo(() => {
    const q = buscar.trim().toLowerCase()
    if (!q) return []
    return productos
      .filter((p) => p.codigo.toLowerCase().includes(q) || p.nombre.toLowerCase().includes(q))
      .slice(0, 8)
  }, [productos, buscar])

  function aplicar(nueva: Factura) {
    setF(nueva)
    setMonto(String(nueva.saldo))
  }

  async function agregar(p: Producto) {
    setError('')
    setOcupado(true)
    try {
      aplicar(await agregarItemFactura(f.id, { producto_id: p.id, cantidad: 1 }))
      setBuscar('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo agregar el producto')
    } finally {
      setOcupado(false)
    }
  }

  async function cambiarCantidad(detalleId: number, cantidad: number) {
    setError('')
    setOcupado(true)
    try {
      aplicar(await actualizarItemFactura(f.id, detalleId, cantidad))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo actualizar la cantidad')
    } finally {
      setOcupado(false)
    }
  }

  async function quitar(detalleId: number, nombre: string) {
    if (!window.confirm(`¿Quitar «${nombre}» de la factura #${f.id}? Se reintegrará el stock.`))
      return
    setError('')
    setOcupado(true)
    try {
      aplicar(await eliminarItemFactura(f.id, detalleId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo quitar el producto')
    } finally {
      setOcupado(false)
    }
  }

  async function pagar() {
    setError('')
    const valor = Number(monto)
    if (!valor || valor <= 0 || valor > f.saldo) {
      setError(`El monto debe ser mayor a 0 y no superar el saldo (${moneda.format(f.saldo)})`)
      return
    }
    const suma = round2(pagos.reduce((acc, p) => acc + (Number(p.valor) || 0), 0))
    if (pagos.some((p) => (Number(p.valor) || 0) <= 0)) {
      setError('Cada medio de pago debe tener un valor mayor a 0')
      return
    }
    if (suma !== round2(valor)) {
      setError('La suma de los medios de pago debe coincidir con el monto del pago')
      return
    }
    if (!usuario) {
      setError('No hay una sesión válida. Vuelve a iniciar sesión.')
      return
    }

    const pagosOperacion = pagosDesdeLineas(pagos)
    const operacion = crearOperacionPago({
      usuarioId: usuario.id,
      usuarioNombre: usuario.nombre || usuario.username,
      turnoId,
      facturaId: f.id,
      pagos: pagosOperacion,
      total: round2(valor),
    })

    function guardarEnDispositivo(): boolean {
      if (!encolarOperacion(operacion)) {
        setError(
          'No se pudo guardar el cobro en este dispositivo (almacenamiento lleno o bloqueado). No se registró nada.',
        )
        return false
      }
      return true
    }

    if (!enLinea || (typeof navigator !== 'undefined' && !navigator.onLine)) {
      if (!turnoId) {
        setError(
          'Necesitas una caja abierta para cobrar sin conexión. Ábrela cuando tengas red y vuelve a intentarlo.',
        )
        return
      }
      if (guardarEnDispositivo()) {
        onGuardado(
          `Cobro de ${moneda.format(valor)} guardado en el dispositivo. Se sincronizará al volver la conexión.`,
        )
      }
      return
    }

    setGuardando(true)
    try {
      await registrarPagoConReintento(
        f.id,
        pagosOperacion.map((p) => ({ valor: p.valor, forma_pago: p.formaPago })),
        operacion.clavePago,
      )
      onGuardado()
    } catch (err) {
      if (esErrorRed(err)) {
        if (guardarEnDispositivo()) {
          onGuardado(
            `No se confirmó el cobro por la conexión. Quedó guardado en el dispositivo y se sincronizará automáticamente.`,
          )
        }
        return
      }
      if (err instanceof ApiError && err.timeout) {
        setError(
          'No pudimos confirmar el pago por un problema de conexión. Revisa la factura en la lista antes de reintentar: puede que ya esté registrado.',
        )
      } else {
        setError(err instanceof Error ? err.message : 'Error al registrar el pago')
      }
    } finally {
      setGuardando(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!esPago) return
    void pagar()
  }

  async function confirmarAnular() {
    const motivo = motivoAnular === 'Otro' ? motivoOtro.trim() || 'Otro' : motivoAnular
    setError('')
    setAnulando(true)
    try {
      await anularFactura(f.id, motivo)
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al anular la factura')
    } finally {
      setAnulando(false)
    }
  }

  async function asignar(id: number) {
    setError('')
    setOcupado(true)
    try {
      aplicar(await asignarClienteFactura(f.id, id))
      setAsignando(false)
      setBuscarCliente('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo asignar el cliente')
    } finally {
      setOcupado(false)
    }
  }

  const resultadosCliente = useMemo(() => {
    const q = buscarCliente.trim().toLowerCase()
    if (!q) return []
    return clientes
      .filter(
        (c) =>
          c.nombre.toLowerCase().includes(q) ||
          (c.celular ?? '').toLowerCase().includes(q) ||
          (c.correo ?? '').toLowerCase().includes(q),
      )
      .slice(0, 8)
  }, [clientes, buscarCliente])

  // Lo realmente cobrado son los pagos; el saldo se topa en 0, así que
  // `total - saldo` mentiría cuando la factura quedó pagada de más.
  const pagado = round2(f.pagos.reduce((acc, p) => acc + p.valor, 0))
  const saldoAFavor = Math.max(round2(pagado - f.total), 0)

  return (
    <div className="modal-overlay modal-overlay--full" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal modal--ancho" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>{esPago ? `Registrar pago · Factura #${f.id}` : `Factura #${f.id}`}</h2>
        {!enLinea && (
          <p className="aviso">
            Sin conexión: el cobro se guardará en este dispositivo. Editar o
            anular la factura requiere conexión.
          </p>
        )}
        {f.requiere_revision && (
          <p className="error">
            Venta marcada para revisión:{' '}
            {f.nota_revision ?? 'requiere revisión manual.'}
          </p>
        )}
        <p className="ayuda">
          {formatoFecha(f.fecha)} · Total {moneda.format(f.total)} · Pagado {moneda.format(pagado)}{' '}
          · Saldo {moneda.format(f.saldo)}{' '}
          <span className={claseEstado(f.estado)}>{f.estado}</span>
        </p>
        {saldoAFavor > 0 && (
          <p className="ayuda">
            Saldo a favor del cliente: <strong>{moneda.format(saldoAFavor)}</strong>. Ajustar
            cantidades no mueve la caja; si hay que devolver dinero, regístralo como movimiento de
            caja.
          </p>
        )}
        {f.estado === 'Anulada' && (f.motivo_anulacion || f.fecha_anulacion) && (
          <p className="ayuda">
            Anulada{f.fecha_anulacion ? ` el ${formatoFecha(f.fecha_anulacion)}` : ''}
            {f.motivo_anulacion ? ` · Motivo: ${f.motivo_anulacion}` : ''}
          </p>
        )}
        {error && <p className="error">{error}</p>}

        <p className="ayuda">Cliente: {f.cliente_nombre || '—'}</p>
        {facturaAbierta &&
          enLinea &&
          (asignando ? (
            <div className="buscador-producto">
              <input
                autoFocus
                placeholder="Buscar cliente por nombre, celular o correo…"
                value={buscarCliente}
                onChange={(e) => setBuscarCliente(e.target.value)}
                disabled={ocupado}
              />
              {resultadosCliente.length > 0 && (
                <ul className="sugerencias">
                  {resultadosCliente.map((c) => (
                    <li key={c.id}>
                      <button type="button" onClick={() => void asignar(c.id)}>
                        <span>{c.nombre}</span>
                        <span className="ayuda">{contactoSecundario(c)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {buscarCliente.trim() && resultadosCliente.length === 0 && (
                <p className="ayuda">Sin coincidencias para «{buscarCliente.trim()}».</p>
              )}
              <button
                type="button"
                className="boton boton--secundario boton--mini enlace-ver-mas"
                onClick={() => {
                  setAsignando(false)
                  setBuscarCliente('')
                }}
              >
                Cancelar
              </button>
            </div>
          ) : (
            <div className="acciones-fila">
              <button
                type="button"
                className="boton boton--mini boton--secundario"
                onClick={() => setAsignando(true)}
                disabled={ocupado}
              >
                Asignar cliente
              </button>
            </div>
          ))}

        {editable && (
          <>
            <p className="ayuda">
              Agrega productos o ajusta cantidades (servicio a la mesa). Los cambios ajustan el stock
              y el saldo, pero no registran movimientos de caja.
            </p>
            <div className="buscador-producto">
              <input
                placeholder="Buscar producto para agregar…"
                value={buscar}
                onChange={(e) => setBuscar(e.target.value)}
                disabled={ocupado}
              />
              {resultados.length > 0 && (
                <ul className="sugerencias">
                  {resultados.map((p) => (
                    <li key={p.id}>
                      <button type="button" onClick={() => void agregar(p)}>
                        <span>
                          {p.codigo} · {p.nombre}
                        </span>
                        <span className="ayuda">
                          {moneda.format(p.precio)} · stock {p.stock}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {buscar.trim() && resultados.length === 0 && (
                <p className="ayuda">Sin coincidencias para «{buscar.trim()}».</p>
              )}
            </div>
          </>
        )}

        <div className="tabla-wrap tabla-wrap--cards">
          <table className="tabla tabla--cards">
            <thead>
              <tr>
                <th>Producto</th>
                <th className="derecha">Precio</th>
                <th className="derecha">Cant.</th>
                <th className="derecha">Subtotal</th>
                {editable && <th></th>}
              </tr>
            </thead>
            <tbody>
              {f.detalles.map((d) => {
                const nombre = productosPorId.get(d.producto_id)?.nombre ?? `Producto #${d.producto_id}`
                if (d.anulado) {
                  return (
                    <tr key={d.id} className="fila-retirada">
                      <td data-label="Producto">
                        <span className="tachado">{nombre}</span>{' '}
                        <span className="etiqueta-retirado">Retirado</span>
                      </td>
                      <td data-label="Precio" className="derecha tachado">
                        {moneda.format(d.precio_unitario)}
                      </td>
                      <td data-label="Cant." className="derecha tachado">
                        {d.cantidad}
                      </td>
                      <td data-label="Subtotal" className="derecha tachado">
                        {moneda.format(d.subtotal)}
                      </td>
                      {editable && <td className="celda-accion"></td>}
                    </tr>
                  )
                }
                return (
                  <tr key={d.id}>
                    <td data-label="Producto">{nombre}</td>
                    <td data-label="Precio" className="derecha">
                      {moneda.format(d.precio_unitario)}
                    </td>
                    <td data-label="Cant." className="derecha">
                      {editable ? (
                        <Stepper
                          valor={d.cantidad}
                          min={(f.estado === 'Pagada' || f.estado === 'Crédito') ? d.cantidad : 1}
                          disabled={ocupado}
                          etiqueta={nombre}
                          onCambiar={(n) => void cambiarCantidad(d.id, n)}
                        />
                      ) : (
                        d.cantidad
                      )}
                    </td>
                    <td data-label="Subtotal" className="derecha">
                      {moneda.format(d.subtotal)}
                    </td>
                    {editable && (
                      <td className="celda-accion">
                        <div className="acciones-fila">
                          <button
                            type="button"
                            className="boton boton--mini boton--danger"
                            disabled={ocupado || unaSolaLinea || (f.estado === 'Pagada' || f.estado === 'Crédito')}
                            title={
                              f.estado === 'Pagada' || f.estado === 'Crédito'
                                ? 'En una factura pagada o a crédito solo se puede aumentar la cantidad'
                                : unaSolaLinea
                                  ? 'Usa Anular para dejar sin efecto la venta'
                                  : undefined
                            }
                            onClick={() => void quitar(d.id, nombre)}
                          >
                            Quitar
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={editable ? 3 : 2} className="derecha">
                  <strong>Total</strong>
                </td>
                <td className="derecha">
                  <strong>{moneda.format(f.total)}</strong>
                </td>
                {editable && <td></td>}
              </tr>
            </tfoot>
          </table>
        </div>

        {puedePagar ? (
          <>
            <div className="bloque-pago">
              <label>
                Monto del pago
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={monto}
                  onChange={(e) => setMonto(e.target.value)}
                />
              </label>
              <MediosPago
                total={Number(monto) || 0}
                lineas={pagos}
                onCambiar={setPagos}
                disabled={guardando || ocupado}
              />
            </div>
            <div className="acciones">
              <span className="espaciador" />
              <button type="button" className="boton boton--secundario" onClick={onCerrar}>
                Cerrar
              </button>
              <button type="submit" className="boton" disabled={guardando || ocupado}>
                {guardando ? 'Registrando…' : 'Registrar pago'}
              </button>
            </div>
          </>
        ) : (
          <>
            {esPago ? (
              <p className="ayuda">
                {f.estado === 'Anulada'
                  ? 'La factura está anulada.'
                  : 'Esta factura ya está paga.'}
              </p>
            ) : (
              <p className="ayuda">Los cambios en los productos se guardan al instante.</p>
            )}
            <div className="acciones">
              {puedeAnularAqui && (
                <button
                  type="button"
                  className="boton boton--danger"
                  onClick={() => setMostrandoAnular(true)}
                  disabled={anulando || ocupado}
                >
                  Anular factura
                </button>
              )}
              <span className="espaciador" />
              <button type="button" className="boton boton--secundario" onClick={onCerrar}>
                Cerrar
              </button>
            </div>
          </>
        )}

        {puedeAnular && f.estado !== 'Anulada' && mostrandoAnular && (
          <div className="panel-anular">
            <p className="ayuda">
              {pagado > 0
                ? `Se devolverán ${moneda.format(pagado)} desde la caja abierta y se reintegrará el stock de los productos activos.`
                : 'Se reintegrará el stock de los productos activos.'}{' '}
              Esta acción no se puede deshacer.
            </p>
            <div className="fila-campos">
              <label>
                Motivo de anulación
                <select value={motivoAnular} onChange={(e) => setMotivoAnular(e.target.value)}>
                  {MOTIVOS_ANULACION.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>
              {motivoAnular === 'Otro' && (
                <label>
                  Describe el motivo
                  <input value={motivoOtro} onChange={(e) => setMotivoOtro(e.target.value)} />
                </label>
              )}
            </div>
            <div className="acciones">
              <button
                type="button"
                className="boton boton--danger"
                onClick={() => void confirmarAnular()}
                disabled={anulando || ocupado || (motivoAnular === 'Otro' && !motivoOtro.trim())}
              >
                {anulando ? 'Anulando…' : 'Confirmar anulación'}
              </button>
              <span className="espaciador" />
              <button
                type="button"
                className="boton boton--secundario"
                onClick={() => setMostrandoAnular(false)}
                disabled={anulando}
              >
                Cancelar
              </button>
            </div>
          </div>
        )}
      </form>
    </div>
  )
}
