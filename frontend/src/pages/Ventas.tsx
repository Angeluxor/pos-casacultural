import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
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
} from '../api/ventas'
import { listarProductos, type Producto } from '../api/productos'
import { listarClientes, type Cliente } from '../api/clientes'
import type { FormaPago } from '../api/types'
import { Paginacion } from '../components/Paginacion'
import { Stepper } from '../components/Stepper'
import { ThOrdenable } from '../components/ThOrdenable'
import { formatoFecha, moneda } from '../lib/formato'
import { confirmarCierre } from '../lib/modal'
import { useOrdenServidor } from '../lib/orden'
import { Vacio } from '../components/Vacio'
import { useAuth } from '../auth/useAuth'
import { usePaginacion } from '../lib/usePaginacion'
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
  const { usuario } = useAuth()
  const esAdmin = usuario?.rol === 'Admin'

  const [estado, setEstado] = useState<EstadoFactura | ''>('')
  const cargarFacturas = useCallback(
    (params: Parameters<typeof listarFacturasPaginado>[0]) =>
      listarFacturasPaginado({ ...params, estado }),
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
  const hayFiltros = buscar.trim() !== '' || desde !== '' || hasta !== '' || estado !== ''

  useEffect(() => {
    setSkip(0)
  }, [estado, setSkip])

  const [clientes, setClientes] = useState<Cliente[]>([])
  const [productos, setProductos] = useState<Producto[]>([])
  const [cargandoCatalogo, setCargandoCatalogo] = useState(true)
  const [errorCatalogo, setErrorCatalogo] = useState('')
  const [mensaje, setMensaje] = useState('')

  const [nuevaAbierta, setNuevaAbierta] = useState(false)
  const [cobrar, setCobrar] = useState<Factura | null>(null)
  const [modoFactura, setModoFactura] = useState<'ver' | 'pagar'>('ver')

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

  const agregarCliente = useCallback((c: Cliente) => {
    setClientes((prev) => (prev.some((x) => x.id === c.id) ? prev : [...prev, c]))
  }, [])

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
                        {f.saldo > 0 && f.estado !== 'Anulada' && (
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
          productos={productos}
          catalogoListo={catalogoListo}
          onClienteCreado={agregarCliente}
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
          clientes={clientes}
          esAdmin={esAdmin}
          modo={modoFactura}
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

function round2(n: number): number {
  return Math.round(n * 100) / 100
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
  onClienteCreado,
  onCerrar,
  onGuardado,
}: {
  clientes: Cliente[]
  productos: Producto[]
  catalogoListo: boolean
  onClienteCreado: (cliente: Cliente) => void
  onCerrar: () => void
  onGuardado: (aviso?: string) => void
}) {
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
    try {
      const factura = await crearFactura({
        cliente_id: cliente ? cliente.id : null,
        nombre_eventual: cliente ? null : nombreEventual.trim() || null,
        detalles: items.map((i) => ({ producto_id: i.producto.id, cantidad: i.cantidad })),
      })
      if (cobrarAhora) {
        try {
          await pagarFactura(
            factura.id,
            pagos.map((p) => ({ valor: Number(p.valor), forma_pago: p.forma_pago })),
          )
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

        <label className="check">
          <input
            type="checkbox"
            checked={cobrarAhora}
            onChange={(e) => alternarCobro(e.target.checked)}
          />
          Cobrar ahora
        </label>

        {cobrarAhora && (
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
  esAdmin,
  modo,
  onCerrar,
  onGuardado,
}: {
  factura: Factura
  productos: Producto[]
  clientes: Cliente[]
  esAdmin: boolean
  modo: 'ver' | 'pagar'
  onCerrar: () => void
  onGuardado: () => void
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
  const editable = facturaAbierta && modo === 'ver'
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
    setGuardando(true)
    try {
      await pagarFactura(
        f.id,
        pagos.map((p) => ({ valor: Number(p.valor), forma_pago: p.forma_pago })),
      )
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al registrar el pago')
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

  const pagado = f.total - f.saldo

  return (
    <div className="modal-overlay modal-overlay--full" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal modal--ancho" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>{esPago ? `Registrar pago · Factura #${f.id}` : `Factura #${f.id}`}</h2>
        <p className="ayuda">
          {formatoFecha(f.fecha)} · Total {moneda.format(f.total)} · Pagado {moneda.format(pagado)}{' '}
          · Saldo {moneda.format(f.saldo)}{' '}
          <span className={claseEstado(f.estado)}>{f.estado}</span>
        </p>
        {f.estado === 'Anulada' && (f.motivo_anulacion || f.fecha_anulacion) && (
          <p className="ayuda">
            Anulada{f.fecha_anulacion ? ` el ${formatoFecha(f.fecha_anulacion)}` : ''}
            {f.motivo_anulacion ? ` · Motivo: ${f.motivo_anulacion}` : ''}
          </p>
        )}
        {error && <p className="error">{error}</p>}

        <p className="ayuda">Cliente: {f.cliente_nombre || '—'}</p>
        {facturaAbierta &&
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
              {editable && esAdmin && (
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

        {esAdmin && f.estado !== 'Anulada' && mostrandoAnular && (
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
