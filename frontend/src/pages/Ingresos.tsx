import { useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  crearIngreso,
  editarIngreso,
  paginaIngresos,
  resolverIngreso,
  FORMAS_PAGO_INGRESO,
  TIPOS_ITEM_INGRESO,
  type FormaPagoIngreso,
  type Ingreso,
  type IngresoCreate,
  type TipoItemIngreso,
} from '../api/ingresos'
import { listarProductos, type Producto } from '../api/productos'
import { useAuth } from '../auth/useAuth'
import { Paginacion } from '../components/Paginacion'
import { ThOrdenable } from '../components/ThOrdenable'
import { useOrdenServidor } from '../lib/orden'
import { Vacio } from '../components/Vacio'
import { confirmarCierre } from '../lib/modal'
import { formatoFecha, moneda } from '../lib/formato'
import { usePaginacion } from '../lib/usePaginacion'

const CLASE_ESTADO: Record<string, string> = {
  Completo: 'badge badge--on',
  Parcial: 'badge badge--warn',
  Inconsistente: 'badge badge--off',
}

export function Ingresos() {
  const { tienePermiso } = useAuth()
  const puedeCrear = tienePermiso('ingresos.crear')
  const [params, setParams] = useSearchParams()

  const { orden, direccion, alternar } = useOrdenServidor()
  const { datos, skip, setSkip, cargando, error, recargar, tamano } = usePaginacion(
    paginaIngresos,
    20,
    orden,
    direccion,
  )
  const ingresos = datos?.items ?? []
  const total = datos?.total ?? 0

  const [formNuevo, setFormNuevo] = useState(false)
  const [detalle, setDetalle] = useState<Ingreso | null>(null)

  useEffect(() => {
    if (params.get('nuevo') && puedeCrear) {
      setFormNuevo(true)
      params.delete('nuevo')
      setParams(params, { replace: true })
    }
  }, [params, setParams, puedeCrear])

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Ingresos de inventario</h1>
          <p className="ayuda">{total} ingresos registrados</p>
        </div>
        {puedeCrear && (
          <button className="boton" onClick={() => setFormNuevo(true)}>
            + Nuevo ingreso
          </button>
        )}
      </header>

      {error && <p className="error">{error}</p>}

      {cargando ? (
        <p className="ayuda">Cargando…</p>
      ) : ingresos.length === 0 ? (
        <Vacio
          titulo="Aún no hay ingresos"
          detalle="Registra la entrada de mercancía: suma stock y, si la pagas en efectivo o transferencia, descuenta de la caja."
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
                  <ThOrdenable
                    campo="proveedor"
                    orden={orden}
                    direccion={direccion}
                    onOrdenar={alternar}
                  >
                    Proveedor
                  </ThOrdenable>
                  <ThOrdenable
                    campo="forma_pago"
                    orden={orden}
                    direccion={direccion}
                    onOrdenar={alternar}
                  >
                    Forma de pago
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
                  <th className="derecha">Suma ítems</th>
                  <ThOrdenable campo="estado" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Estado
                  </ThOrdenable>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {ingresos.map((ing) => (
                  <tr key={ing.id}>
                    <td data-label="#">#{ing.id}</td>
                    <td data-label="Fecha">{formatoFecha(ing.fecha)}</td>
                    <td data-label="Proveedor">{ing.proveedor ?? '—'}</td>
                    <td data-label="Forma de pago">{ing.forma_pago}</td>
                    <td data-label="Total" className="derecha">
                      {moneda.format(ing.total)}
                    </td>
                    <td data-label="Suma ítems" className="derecha">
                      {moneda.format(ing.suma_items)}
                    </td>
                    <td data-label="Estado">
                      <span className={CLASE_ESTADO[ing.estado] ?? 'badge'}>{ing.estado}</span>
                    </td>
                    <td className="celda-accion">
                      <div className="acciones-fila">
                        <button className="boton boton--mini" onClick={() => setDetalle(ing)}>
                          Ver
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginacion total={total} skip={skip} limit={tamano} onCambiar={setSkip} cargando={cargando} />
        </>
      )}

      {formNuevo && (
        <FormNuevo
          onCerrar={() => setFormNuevo(false)}
          onCreado={() => {
            setFormNuevo(false)
            recargar()
          }}
        />
      )}

      {detalle && (
        <DetalleIngreso
          ingreso={detalle}
          puedeResolver={tienePermiso('ingresos.resolver')}
          puedeEditar={tienePermiso('ingresos.editar')}
          onCerrar={() => setDetalle(null)}
          onActualizado={(ing) => {
            setDetalle(ing)
            recargar()
          }}
        />
      )}
    </div>
  )
}

type Linea = {
  key: number
  tipo: TipoItemIngreso
  productoId: string
  concepto: string
  precio: string
  cantidad: string
  costo: string
  valor: string
}

let contadorLineas = 0
function nuevaLinea(tipo: TipoItemIngreso = 'Producto'): Linea {
  contadorLineas += 1
  return {
    key: contadorLineas,
    tipo,
    productoId: '',
    concepto: '',
    precio: '',
    cantidad: '1',
    costo: '',
    valor: '',
  }
}

function FormNuevo({ onCerrar, onCreado }: { onCerrar: () => void; onCreado: () => void }) {
  const [productos, setProductos] = useState<Producto[]>([])
  const [proveedor, setProveedor] = useState('')
  const [formaPago, setFormaPago] = useState<FormaPagoIngreso>('Efectivo')
  const [total, setTotal] = useState('')
  const [observacion, setObservacion] = useState('')
  const [lineas, setLineas] = useState<Linea[]>([nuevaLinea()])
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  useEffect(() => {
    listarProductos()
      .then(setProductos)
      .catch(() => setProductos([]))
  }, [])

  function actualizar(key: number, cambios: Partial<Linea>) {
    setLineas((ls) => ls.map((l) => (l.key === key ? { ...l, ...cambios } : l)))
  }

  function agregar() {
    setLineas((l) => [...l, nuevaLinea()])
  }

  function quitar(key: number) {
    setLineas((l) => l.filter((x) => x.key !== key))
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const totalNum = Number(total)
    if (!total || totalNum < 0) {
      setError('Indica el total del ingreso.')
      return
    }
    const items = []
    for (const l of lineas) {
      if (l.tipo === 'Otros') {
        if (!l.concepto.trim() || !l.valor) {
          setError('Completa el concepto y el valor de cada ítem «Otros».')
          return
        }
        items.push({ tipo: l.tipo, concepto: l.concepto.trim(), valor: Number(l.valor) })
      } else if (l.tipo === 'Producto') {
        if (!l.productoId || !l.cantidad) {
          setError('Elige el producto y la cantidad de cada línea.')
          return
        }
        items.push({
          tipo: l.tipo,
          producto_id: Number(l.productoId),
          cantidad: Number(l.cantidad),
          costo_unitario: l.costo ? Number(l.costo) : undefined,
        })
      } else {
        if (!l.concepto.trim() || !l.precio || !l.cantidad) {
          setError('Completa nombre, precio y cantidad del producto nuevo.')
          return
        }
        items.push({
          tipo: l.tipo,
          concepto: l.concepto.trim(),
          precio: Number(l.precio),
          cantidad: Number(l.cantidad),
          costo_unitario: l.costo ? Number(l.costo) : undefined,
        })
      }
    }
    if (items.length === 0) {
      setError('Agrega al menos un ítem.')
      return
    }
    const data: IngresoCreate = {
      proveedor: proveedor.trim() || undefined,
      forma_pago: formaPago,
      total: totalNum,
      observacion: observacion.trim() || undefined,
      items,
    }
    setGuardando(true)
    try {
      await crearIngreso(data)
      onCreado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al registrar el ingreso')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay modal-overlay--full" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal modal--ancho" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>Nuevo ingreso de inventario</h2>
        {error && <p className="error">{error}</p>}

        <div className="fila-campos">
          <label>
            Proveedor
            <input
              value={proveedor}
              onChange={(e) => setProveedor(e.target.value)}
              placeholder="Opcional"
            />
          </label>
          <label>
            Forma de pago
            <select
              value={formaPago}
              onChange={(e) => setFormaPago(e.target.value as FormaPagoIngreso)}
            >
              {FORMAS_PAGO_INGRESO.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>
          <label>
            Total del ingreso
            <input
              type="number"
              min="0"
              step="0.01"
              value={total}
              onChange={(e) => setTotal(e.target.value)}
              required
            />
          </label>
          <label>
            Observación
            <input
              value={observacion}
              onChange={(e) => setObservacion(e.target.value)}
              placeholder="Opcional"
            />
          </label>
        </div>

        <h3>Ítems</h3>
        <ul className="lista-simple">
          {lineas.map((l) => (
            <li key={l.key} style={{ display: 'block' }}>
              <div className="fila-campos">
                <label>
                  Tipo
                  <select
                    value={l.tipo}
                    onChange={(e) => actualizar(l.key, { tipo: e.target.value as TipoItemIngreso })}
                  >
                    {TIPOS_ITEM_INGRESO.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </label>

                {l.tipo === 'Producto' && (
                  <label>
                    Producto
                    <select
                      value={l.productoId}
                      onChange={(e) => actualizar(l.key, { productoId: e.target.value })}
                    >
                      <option value="">Elige…</option>
                      {productos.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.codigo} · {p.nombre}
                        </option>
                      ))}
                    </select>
                  </label>
                )}

                {l.tipo === 'Producto nuevo' && (
                  <>
                    <label>
                      Nombre
                      <input
                        value={l.concepto}
                        onChange={(e) => actualizar(l.key, { concepto: e.target.value })}
                      />
                    </label>
                    <label>
                      Precio de venta
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={l.precio}
                        onChange={(e) => actualizar(l.key, { precio: e.target.value })}
                      />
                    </label>
                  </>
                )}

                {l.tipo === 'Otros' ? (
                  <>
                    <label>
                      Concepto
                      <input
                        value={l.concepto}
                        onChange={(e) => actualizar(l.key, { concepto: e.target.value })}
                      />
                    </label>
                    <label>
                      Valor
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={l.valor}
                        onChange={(e) => actualizar(l.key, { valor: e.target.value })}
                      />
                    </label>
                  </>
                ) : (
                  <>
                    <label>
                      Cantidad
                      <input
                        type="number"
                        min="1"
                        step="1"
                        value={l.cantidad}
                        onChange={(e) => actualizar(l.key, { cantidad: e.target.value })}
                      />
                    </label>
                    <label>
                      Costo unitario
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={l.costo}
                        placeholder="Opcional"
                        onChange={(e) => actualizar(l.key, { costo: e.target.value })}
                      />
                    </label>
                  </>
                )}
              </div>
              <div className="acciones">
                <button
                  type="button"
                  className="boton boton--mini boton--danger"
                  onClick={() => quitar(l.key)}
                  disabled={lineas.length === 1}
                >
                  Quitar
                </button>
              </div>
            </li>
          ))}
        </ul>

        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={agregar}>
            + Agregar ítem
          </button>
          <div className="espaciador" />
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button type="submit" className="boton" disabled={guardando}>
            {guardando ? 'Guardando…' : 'Registrar ingreso'}
          </button>
        </div>
      </form>
    </div>
  )
}

function DetalleIngreso({
  ingreso,
  puedeResolver,
  puedeEditar,
  onCerrar,
  onActualizado,
}: {
  ingreso: Ingreso
  puedeResolver: boolean
  puedeEditar: boolean
  onCerrar: () => void
  onActualizado: (ing: Ingreso) => void
}) {
  const [proveedor, setProveedor] = useState(ingreso.proveedor ?? '')
  const [costos, setCostos] = useState<Record<number, string>>(() =>
    Object.fromEntries(
      ingreso.items.map((i) => [i.id, i.costo_unitario != null ? String(i.costo_unitario) : '']),
    ),
  )
  const [justificacion, setJustificacion] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function guardar() {
    setError('')
    setGuardando(true)
    try {
      const items = ingreso.items
        .filter((i) => i.tipo !== 'Otros')
        .map((i) => ({
          id: i.id,
          costo_unitario: costos[i.id] ? Number(costos[i.id]) : undefined,
        }))
      const actualizado = await editarIngreso(ingreso.id, {
        proveedor: proveedor.trim() || undefined,
        items,
      })
      onActualizado(actualizado)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar')
    } finally {
      setGuardando(false)
    }
  }

  async function resolver() {
    if (!justificacion.trim()) {
      setError('Escribe la justificación para marcar el ingreso como completo.')
      return
    }
    setError('')
    setGuardando(true)
    try {
      const actualizado = await resolverIngreso(ingreso.id, justificacion.trim())
      onActualizado(actualizado)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al resolver')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay modal-overlay--full" onClick={() => confirmarCierre(onCerrar)}>
      <div className="modal modal--ancho" onClick={(e) => e.stopPropagation()}>
        <h2>
          Ingreso #{ingreso.id}{' '}
          <span className={CLASE_ESTADO[ingreso.estado] ?? 'badge'}>{ingreso.estado}</span>
        </h2>
        <p className="ayuda">
          {formatoFecha(ingreso.fecha)} · {ingreso.forma_pago} · Total {moneda.format(ingreso.total)}{' '}
          · Suma ítems {moneda.format(ingreso.suma_items)}
        </p>
        {ingreso.justificacion && (
          <p className="ayuda">Justificación: {ingreso.justificacion}</p>
        )}
        {error && <p className="error">{error}</p>}

        <label>
          Proveedor
          <input
            value={proveedor}
            onChange={(e) => setProveedor(e.target.value)}
            disabled={!puedeEditar}
          />
        </label>

        <div className="tabla-wrap tabla-wrap--cards">
          <table className="tabla tabla--cards">
            <thead>
              <tr>
                <th>Tipo</th>
                <th>Detalle</th>
                <th className="derecha">Cantidad</th>
                <th className="derecha">Costo unitario</th>
                <th className="derecha">Valor</th>
              </tr>
            </thead>
            <tbody>
              {ingreso.items.map((i) => (
                <tr key={i.id}>
                  <td data-label="Tipo">{i.tipo}</td>
                  <td data-label="Detalle">{i.concepto ?? `Producto #${i.producto_id ?? '—'}`}</td>
                  <td data-label="Cantidad" className="derecha">
                    {i.cantidad ?? '—'}
                  </td>
                  <td data-label="Costo unitario" className="derecha">
                    {i.tipo === 'Otros' ? (
                      '—'
                    ) : (
                      <input
                        className="input-mini"
                        type="number"
                        min="0"
                        step="0.01"
                        value={costos[i.id] ?? ''}
                        disabled={!puedeEditar}
                        onChange={(e) =>
                          setCostos((c) => ({ ...c, [i.id]: e.target.value }))
                        }
                      />
                    )}
                  </td>
                  <td data-label="Valor" className="derecha">
                    {i.valor != null ? moneda.format(i.valor) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {ingreso.estado === 'Inconsistente' && puedeResolver && (
          <div className="panel-anular">
            <p className="ayuda">
              La suma de los ítems supera el total. Un administrador puede marcar el ingreso como
              completo dejando una justificación.
            </p>
            <label>
              Justificación
              <input
                value={justificacion}
                onChange={(e) => setJustificacion(e.target.value)}
                placeholder="Describe por qué se acepta la diferencia"
              />
            </label>
            <div className="acciones">
              <button
                type="button"
                className="boton boton--danger"
                onClick={resolver}
                disabled={guardando}
              >
                Marcar como completo
              </button>
            </div>
          </div>
        )}

        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cerrar
          </button>
          {puedeEditar && (
            <button type="button" className="boton" onClick={guardar} disabled={guardando}>
              {guardando ? 'Guardando…' : 'Guardar cambios'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}