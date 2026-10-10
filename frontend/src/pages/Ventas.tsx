import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  actualizarItemFactura,
  agregarItemFactura,
  anularFactura,
  crearFactura,
  eliminarItemFactura,
  listarFacturasPaginado,
  pagarFactura,
  type EstadoFactura,
  type Factura,
} from '../api/ventas'
import { listarProductos, type Producto } from '../api/productos'
import { listarClientes, type Cliente } from '../api/clientes'
import type { FormaPago } from '../api/types'
import { Paginacion } from '../components/Paginacion'
import { formatoFecha, moneda } from '../lib/formato'
import { Vacio } from '../components/Vacio'
import { useAuth } from '../auth/useAuth'
import { usePaginacion } from '../lib/usePaginacion'

const FORMAS_PAGO: FormaPago[] = ['Efectivo', 'Transferencia', 'Tarjeta', 'Otro']

function claseEstado(estado: EstadoFactura): string {
  switch (estado) {
    case 'Pagada':
      return 'badge badge--on'
    case 'Pagado Parcial':
      return 'badge badge--info'
    case 'Anulada':
      return 'badge badge--off'
    default:
      return 'badge badge--warn'
  }
}

export function Ventas() {
  const { usuario } = useAuth()
  const esAdmin = usuario?.rol === 'Admin'

  const { datos, skip, setSkip, buscar, setBuscar, cargando, error, recargar, tamano } =
    usePaginacion(listarFacturasPaginado, 30)
  const facturas = datos?.items ?? []
  const total = datos?.total ?? 0

  const [clientes, setClientes] = useState<Cliente[]>([])
  const [productos, setProductos] = useState<Producto[]>([])
  const [cargandoCatalogo, setCargandoCatalogo] = useState(true)
  const [errorCatalogo, setErrorCatalogo] = useState('')
  const [mensaje, setMensaje] = useState('')

  const [nuevaAbierta, setNuevaAbierta] = useState(false)
  const [cobrar, setCobrar] = useState<Factura | null>(null)

  const cargarCatalogo = useCallback(async () => {
    setCargandoCatalogo(true)
    try {
      const [c, p] = await Promise.all([listarClientes(), listarProductos()])
      setClientes(c)
      setProductos(p)
      setErrorCatalogo('')
    } catch (err) {
      setErrorCatalogo(
        err instanceof Error ? err.message : 'Error al cargar clientes y productos',
      )
    } finally {
      setCargandoCatalogo(false)
    }
  }, [])

  useEffect(() => {
    void cargarCatalogo()
  }, [cargarCatalogo])

  const clientesPorId = useMemo(() => new Map(clientes.map((c) => [c.id, c])), [clientes])

  const catalogoListo = !cargandoCatalogo && productos.length > 0

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Ventas</h1>
          <p className="ayuda">{total} facturas</p>
        </div>
        <button
          className="boton"
          onClick={() => setNuevaAbierta(true)}
          disabled={!catalogoListo}
          title={catalogoListo ? undefined : 'Cargando catálogo…'}
        >
          + Nueva venta
        </button>
      </header>

      <div className="barra">
        <input
          className="campo-busqueda"
          placeholder="Buscar por # factura o cliente…"
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
        />
      </div>

      {errorCatalogo && <p className="error">Catálogo: {errorCatalogo}</p>}
      {mensaje && <p className="aviso">{mensaje}</p>}

      {cargando ? (
        <p className="ayuda">Cargando…</p>
      ) : error ? (
        <p className="error">{error}</p>
      ) : facturas.length === 0 ? (
        <Vacio
          titulo={buscar.trim() ? 'Sin resultados' : 'Aún no hay ventas'}
          detalle={
            buscar.trim()
              ? `Nada coincide con «${buscar.trim()}».`
              : 'Registra tu primera venta con «Nueva venta».'
          }
        />
      ) : (
        <>
          <div className="tabla-wrap">
            <table className="tabla">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Fecha</th>
                  <th>Cliente</th>
                  <th className="derecha">Total</th>
                  <th className="derecha">Saldo</th>
                  <th>Estado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {facturas.map((f) => (
                  <tr key={f.id}>
                    <td>{f.id}</td>
                    <td>{formatoFecha(f.fecha)}</td>
                    <td>
                      {f.cliente_id
                        ? clientesPorId.get(f.cliente_id)?.nombre ?? f.cliente_id
                        : '—'}
                    </td>
                    <td className="derecha">{moneda.format(f.total)}</td>
                    <td className="derecha">{moneda.format(f.saldo)}</td>
                    <td>
                      <span className={claseEstado(f.estado)}>{f.estado}</span>
                    </td>
                    <td>
                      <div className="acciones-fila">
                        <button className="boton boton--mini" onClick={() => setCobrar(f)}>
                          Ver
                        </button>
                        {f.saldo > 0 && f.estado !== 'Anulada' && (
                          <button className="boton boton--mini" onClick={() => setCobrar(f)}>
                            Cobrar
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
          productos={productos}
          catalogoListo={catalogoListo}
          onCerrar={() => setNuevaAbierta(false)}
          onGuardado={(aviso) => {
            setNuevaAbierta(false)
            setMensaje(aviso ?? '')
            recargar()
          }}
        />
      )}

      {cobrar && (
        <FormCobro
          factura={cobrar}
          productos={productos}
          esAdmin={esAdmin}
          onCerrar={() => {
            setCobrar(null)
            recargar()
          }}
          onGuardado={() => {
            setCobrar(null)
            setMensaje('')
            recargar()
          }}
        />
      )}
    </div>
  )
}

type ItemVenta = { producto: Producto; cantidad: number }

function FormVenta({
  clientes,
  productos,
  catalogoListo,
  onCerrar,
  onGuardado,
}: {
  clientes: Cliente[]
  productos: Producto[]
  catalogoListo: boolean
  onCerrar: () => void
  onGuardado: (aviso?: string) => void
}) {
  const [cliente, setCliente] = useState<Cliente | null>(null)
  const [buscarCliente, setBuscarCliente] = useState('')
  const [items, setItems] = useState<ItemVenta[]>([])
  const [buscarProducto, setBuscarProducto] = useState('')
  const [cobrarAhora, setCobrarAhora] = useState(false)
  const [formaPago, setFormaPago] = useState<FormaPago>('Efectivo')
  const [montoCobro, setMontoCobro] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  const total = useMemo(
    () => items.reduce((acc, i) => acc + i.producto.precio * i.cantidad, 0),
    [items],
  )

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
      .filter((c) => c.nombre.toLowerCase().includes(q) || c.documento.toLowerCase().includes(q))
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
    if (activo && !montoCobro) setMontoCobro(String(total))
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
    }
    setGuardando(true)
    try {
      const factura = await crearFactura({
        cliente_id: cliente?.id ?? null,
        detalles: items.map((i) => ({ producto_id: i.producto.id, cantidad: i.cantidad })),
      })
      if (cobrarAhora) {
        try {
          await pagarFactura(factura.id, { valor: Number(montoCobro), forma_pago: formaPago })
        } catch (err) {
          const msg = err instanceof Error ? err.message : 'error desconocido'
          onGuardado(`Venta #${factura.id} registrada, pero el cobro falló: ${msg}`)
          return
        }
      }
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al registrar la venta')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onCerrar}>
      <form className="modal modal--ancho" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>Nueva venta</h2>
        {error && <p className="error">{error}</p>}
        {!catalogoListo && <p className="ayuda">Cargando catálogo de productos…</p>}

        <label htmlFor="venta-cliente">Cliente (opcional)</label>
        {cliente ? (
          <div className="seleccion-chip">
            <span>
              {cliente.nombre} — {cliente.documento}
            </span>
            <button type="button" className="boton boton--mini" onClick={() => setCliente(null)}>
              Quitar
            </button>
          </div>
        ) : (
          <div className="buscador-producto">
            <input
              id="venta-cliente"
              placeholder="Buscar cliente por nombre o documento… (vacío = Consumidor final)"
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
                      }}
                    >
                      <span>{c.nombre}</span>
                      <span className="ayuda">{c.documento}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {buscarCliente.trim() && resultadosClientes.length === 0 && (
              <p className="ayuda">Sin coincidencias para «{buscarCliente.trim()}».</p>
            )}
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

        <div className="tabla-wrap">
          <table className="tabla">
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
                  <td>{i.producto.nombre}</td>
                  <td className="derecha">{moneda.format(i.producto.precio)}</td>
                  <td className="derecha">
                    <input
                      className="input-mini"
                      type="number"
                      min={1}
                      value={i.cantidad}
                      onChange={(e) => cambiarCantidad(i.producto.id, Number(e.target.value))}
                    />
                  </td>
                  <td className="derecha">{moneda.format(i.producto.precio * i.cantidad)}</td>
                  <td>
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
                  <td colSpan={5} className="ayuda">
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

        <label className="check">
          <input
            type="checkbox"
            checked={cobrarAhora}
            onChange={(e) => alternarCobro(e.target.checked)}
          />
          Cobrar ahora
        </label>

        {cobrarAhora && (
          <div className="fila-campos">
            <label>
              Monto a cobrar
              <input
                type="number"
                min="0"
                step="0.01"
                value={montoCobro}
                onChange={(e) => setMontoCobro(e.target.value)}
              />
            </label>
            <label>
              Forma de pago
              <select
                value={formaPago}
                onChange={(e) => setFormaPago(e.target.value as FormaPago)}
              >
                {FORMAS_PAGO.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </label>
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
  )
}

function FormCobro({
  factura,
  productos,
  esAdmin,
  onCerrar,
  onGuardado,
}: {
  factura: Factura
  productos: Producto[]
  esAdmin: boolean
  onCerrar: () => void
  onGuardado: () => void
}) {
  const [f, setF] = useState<Factura>(factura)
  const [monto, setMonto] = useState(String(factura.saldo))
  const [formaPago, setFormaPago] = useState<FormaPago>('Efectivo')
  const [buscar, setBuscar] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [anulando, setAnulando] = useState(false)

  const productosPorId = useMemo(() => new Map(productos.map((p) => [p.id, p])), [productos])
  const editable = f.estado !== 'Anulada'
  const unaSolaLinea = f.detalles.length <= 1

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

  async function pagar(e: FormEvent) {
    e.preventDefault()
    setError('')
    const valor = Number(monto)
    if (!valor || valor <= 0 || valor > f.saldo) {
      setError(`El monto debe ser mayor a 0 y no superar el saldo (${moneda.format(f.saldo)})`)
      return
    }
    setGuardando(true)
    try {
      await pagarFactura(f.id, { valor, forma_pago: formaPago })
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al registrar el pago')
    } finally {
      setGuardando(false)
    }
  }

  async function anular() {
    const pagado = f.total - f.saldo
    const aviso =
      pagado > 0
        ? `La factura #${f.id} tiene ${moneda.format(pagado)} cobrados. Se devolverá ese dinero desde la caja abierta y se reintegrará el stock. ¿Anular?`
        : `¿Anular la factura #${f.id}? Se reintegrará el stock.`
    if (!window.confirm(aviso)) return
    setError('')
    setAnulando(true)
    try {
      await anularFactura(f.id)
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al anular la factura')
    } finally {
      setAnulando(false)
    }
  }

  const pagado = f.total - f.saldo

  return (
    <div className="modal-overlay" onClick={onCerrar}>
      <form className="modal modal--ancho" onClick={(e) => e.stopPropagation()} onSubmit={pagar}>
        <h2>Factura #{f.id}</h2>
        <p className="ayuda">
          {formatoFecha(f.fecha)} · Total {moneda.format(f.total)} · Pagado {moneda.format(pagado)}{' '}
          · Saldo {moneda.format(f.saldo)}{' '}
          <span className={claseEstado(f.estado)}>{f.estado}</span>
        </p>
        {error && <p className="error">{error}</p>}

        {editable && (
          <>
            <p className="ayuda">
              Agrega productos o ajusta cantidades (servicio a la mesa). Los cambios ajustan el stock
              y, si hay dinero de más, se devuelve desde la caja.
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

        <div className="tabla-wrap">
          <table className="tabla">
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
                return (
                  <tr key={d.id}>
                    <td>{nombre}</td>
                    <td className="derecha">{moneda.format(d.precio_unitario)}</td>
                    <td className="derecha">
                      {editable ? (
                        <div className="stepper">
                          <button
                            type="button"
                            className="boton boton--mini"
                            disabled={ocupado || d.cantidad <= 1}
                            onClick={() => void cambiarCantidad(d.id, d.cantidad - 1)}
                          >
                            −
                          </button>
                          <span>{d.cantidad}</span>
                          <button
                            type="button"
                            className="boton boton--mini"
                            disabled={ocupado}
                            onClick={() => void cambiarCantidad(d.id, d.cantidad + 1)}
                          >
                            +
                          </button>
                        </div>
                      ) : (
                        d.cantidad
                      )}
                    </td>
                    <td className="derecha">{moneda.format(d.subtotal)}</td>
                    {editable && (
                      <td>
                        <div className="acciones-fila">
                          <button
                            type="button"
                            className="boton boton--mini boton--danger"
                            disabled={ocupado || unaSolaLinea}
                            title={unaSolaLinea ? 'Usa Anular para dejar sin efecto la venta' : undefined}
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

        {editable && f.saldo > 0 ? (
          <>
            <div className="fila-campos">
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
              <label>
                Forma de pago
                <select
                  value={formaPago}
                  onChange={(e) => setFormaPago(e.target.value as FormaPago)}
                >
                  {FORMAS_PAGO.map((fp) => (
                    <option key={fp} value={fp}>
                      {fp}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="acciones">
              {esAdmin && (
                <button
                  type="button"
                  className="boton boton--danger"
                  onClick={() => void anular()}
                  disabled={anulando || ocupado}
                >
                  {anulando ? 'Anulando…' : 'Anular'}
                </button>
              )}
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
            <p className="ayuda">
              {f.estado === 'Anulada' ? 'Factura anulada.' : 'Esta factura ya está paga.'}
            </p>
            <div className="acciones">
              {esAdmin && f.estado !== 'Anulada' && (
                <button
                  type="button"
                  className="boton boton--danger"
                  onClick={() => void anular()}
                  disabled={anulando || ocupado}
                >
                  {anulando ? 'Anulando…' : 'Anular'}
                </button>
              )}
              <span className="espaciador" />
              <button type="button" className="boton boton--secundario" onClick={onCerrar}>
                Cerrar
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  )
}
