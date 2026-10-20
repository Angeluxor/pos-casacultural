import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  crearCostoManual,
  eliminarCostoManual,
  eliminarReceta,
  guardarReceta,
  historialProducto,
  listarCostosManuales,
  listarInsumos,
  listarRecetas,
  listarResumenCostos,
  type CostoManual,
  type HistorialCosto,
  type InsumoOpcion,
  type Receta,
  type ResumenCosto,
} from '../api/costos'
import { useAuth } from '../auth/useAuth'
import { Paginacion } from '../components/Paginacion'
import { ThOrdenable } from '../components/ThOrdenable'
import { Vacio } from '../components/Vacio'
import { confirmarCierre } from '../lib/modal'
import { formatoFecha, moneda } from '../lib/formato'
import { useOrdenLocal, type Accesores } from '../lib/orden'

type Pestana = 'historico' | 'preparaciones' | 'manuales'

const ACCESORES_RESUMEN: Accesores<ResumenCosto> = {
  nombre: (f) => f.nombre.toLowerCase(),
  codigo: (f) => f.codigo.toLowerCase(),
  mejor: (f) => f.mejor_precio_6s ?? Number.POSITIVE_INFINITY,
  costo: (f) => f.costo_vigente ?? Number.POSITIVE_INFINITY,
  variacion: (f) => f.variacion_6s ?? Number.NEGATIVE_INFINITY,
  precio: (f) => f.precio,
  cmv: (f) => f.cmv_pct ?? Number.POSITIVE_INFINITY,
}

const AYUDA_PESTANA: Record<
  Pestana,
  { titulo: string; detalle: string; pista: string }
> = {
  historico: {
    titulo: 'Qué muestra el histórico',
    detalle:
      'Compara el costo de cada producto con su precio de venta. «Mejor precio 6 sem» es la compra más barata de los últimos 42 días; «Costo vigente» es el que usa el sistema (receta, costo manual o promedio de compras). La variación compara el primer y el último costo del período.',
    pista: 'Costo de compra, mejor precio y variación de los últimos 42 días',
  },
  preparaciones: {
    titulo: 'Qué son las preparaciones',
    detalle:
      'Calcula el costo de un producto transformado a partir de sus insumos y su rendimiento. La receta solo calcula el costo: no descuenta insumos ni suma stock. Si falta el costo de un insumo, la receta queda incompleta.',
    pista: 'Recetas estándar, rendimiento y costo de productos transformados',
  },
  manuales: {
    titulo: 'Qué son los costos manuales',
    detalle:
      'Registra a mano el costo de un insumo que no tiene compras o corrige el costo vigente. El registro más reciente reemplaza al promedio de compras. No se puede usar en productos con receta.',
    pista: 'Costos registrados a mano para insumos sin compras',
  },
}

function pct(valor: number | null): string {
  return valor == null ? '—' : `${valor.toFixed(1)}%`
}

function claseVariacion(valor: number | null): string {
  if (valor == null) return 'costo-neutro'
  if (valor < 0) return 'costo-baja'
  if (valor > 0) return 'costo-sube'
  return 'costo-neutro'
}

function haceSemanas(semanas: number): string {
  const d = new Date(Date.now() - semanas * 7 * 24 * 60 * 60 * 1000)
  return d.toISOString().slice(0, 10)
}

function hoyISO(): string {
  return new Date().toISOString().slice(0, 10)
}

export function Costos() {
  const { tienePermiso } = useAuth()
  const puedeEditar = tienePermiso('costos.editar')

  const [pestana, setPestana] = useState<Pestana>('historico')
  const [resumen, setResumen] = useState<ResumenCosto[]>([])
  const [recetas, setRecetas] = useState<Receta[]>([])
  const [manuales, setManuales] = useState<CostoManual[]>([])
  const [insumos, setInsumos] = useState<InsumoOpcion[]>([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [errorAccion, setErrorAccion] = useState('')

  const [buscar, setBuscar] = useState('')
  const [soloCmv, setSoloCmv] = useState(false)
  const [skip, setSkip] = useState(0)
  const tamano = 25

  const [historial, setHistorial] = useState<ResumenCosto | null>(null)
  const [formReceta, setFormReceta] = useState<{
    abierto: boolean
    receta: Receta | null
    productoIdInicial?: number
  }>({ abierto: false, receta: null })
  const [formManual, setFormManual] = useState<{
    abierto: boolean
    productoId?: number
  }>({ abierto: false })

  async function cargar() {
    setCargando(true)
    setError('')
    try {
      const [r, rec, man, ins] = await Promise.all([
        listarResumenCostos(),
        listarRecetas(),
        listarCostosManuales(),
        listarInsumos(),
      ])
      setResumen(r)
      setRecetas(rec)
      setManuales(man)
      setInsumos(ins)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron cargar los costos')
    } finally {
      setCargando(false)
    }
  }

  useEffect(() => {
    void cargar()
  }, [])

  useEffect(() => {
    setSkip(0)
  }, [buscar, soloCmv, pestana])

  const filtrados = useMemo(() => {
    const texto = buscar.trim().toLowerCase()
    return resumen.filter((f) => {
      if (soloCmv && !f.mostrar_cmv) return false
      if (!texto) return true
      return (
        f.nombre.toLowerCase().includes(texto) ||
        f.codigo.toLowerCase().includes(texto)
      )
    })
  }, [resumen, buscar, soloCmv])

  const { items: ordenados, orden, direccion, alternar } = useOrdenLocal(
    filtrados,
    ACCESORES_RESUMEN,
    { campo: 'nombre' },
  )
  const pagina = ordenados.slice(skip, skip + tamano)

  const conCosto = resumen.filter((f) => f.costo_vigente != null).length
  const sinCosto = resumen.length - conCosto
  const preparaciones = resumen.filter((f) => f.tiene_receta).length
  const incompletas = resumen.filter(
    (f) => f.tiene_receta && !f.costo_completo,
  ).length
  const margenes = resumen
    .filter((f) => f.mostrar_cmv && f.margen_pct != null)
    .map((f) => f.margen_pct as number)
  const margenPromedio = margenes.length
    ? margenes.reduce((a, b) => a + b, 0) / margenes.length
    : null

  const productosSinReceta = insumos.filter((i) => !i.tiene_receta)

  async function borrarReceta(receta: Receta) {
    if (!window.confirm(`¿Eliminar la receta de "${receta.nombre}"?`)) return
    setErrorAccion('')
    try {
      await eliminarReceta(receta.producto_id)
      await cargar()
    } catch (err) {
      setErrorAccion(err instanceof Error ? err.message : 'Error al eliminar la receta')
    }
  }

  async function borrarManual(costo: CostoManual) {
    if (!window.confirm(`¿Eliminar el costo manual de "${costo.producto_nombre}"?`))
      return
    setErrorAccion('')
    try {
      await eliminarCostoManual(costo.id)
      await cargar()
    } catch (err) {
      setErrorAccion(err instanceof Error ? err.message : 'Error al eliminar el costo')
    }
  }

  const mensajeError = error || errorAccion

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Costos</h1>
          <p className="ayuda">
            Histórico de costos, relación CMV/precio y recetas de preparaciones
          </p>
        </div>
        {puedeEditar && (
          <div className="acciones-fila">
            <button
              className="boton boton--secundario"
              onClick={() => setFormManual({ abierto: true })}
            >
              + Costo manual
            </button>
            <button
              className="boton"
              onClick={() =>
                setFormReceta({ abierto: true, receta: null, productoIdInicial: undefined })
              }
            >
              + Nueva receta
            </button>
          </div>
        )}
      </header>

      <div className="tarjetas-resumen">
        <TarjetaResumen titulo="Con costo" valor={String(conCosto)} />
        <TarjetaResumen
          titulo="Sin costo"
          valor={String(sinCosto)}
          alerta={sinCosto > 0}
        />
        <TarjetaResumen titulo="Preparaciones" valor={String(preparaciones)} />
        <TarjetaResumen
          titulo="Recetas incompletas"
          valor={String(incompletas)}
          alerta={incompletas > 0}
        />
        <TarjetaResumen
          titulo="Margen promedio"
          valor={margenPromedio == null ? '—' : `${margenPromedio.toFixed(1)}%`}
        />
      </div>

      <div className="fichas" aria-describedby="ayuda-pestana">
        <button
          className={pestana === 'historico' ? 'ficha ficha--activa' : 'ficha'}
          onClick={() => setPestana('historico')}
          title={AYUDA_PESTANA.historico.pista}
        >
          Histórico
        </button>
        <button
          className={pestana === 'preparaciones' ? 'ficha ficha--activa' : 'ficha'}
          onClick={() => setPestana('preparaciones')}
          title={AYUDA_PESTANA.preparaciones.pista}
        >
          Preparaciones
        </button>
        <button
          className={pestana === 'manuales' ? 'ficha ficha--activa' : 'ficha'}
          onClick={() => setPestana('manuales')}
          title={AYUDA_PESTANA.manuales.pista}
        >
          Costos manuales
        </button>
      </div>

      <div
        className="ayuda-pestana"
        id="ayuda-pestana"
        role="note"
        aria-live="polite"
      >
        <span className="ayuda-pestana__icono" aria-hidden="true">
          i
        </span>
        <div>
          <strong>{AYUDA_PESTANA[pestana].titulo}</strong>
          <p>{AYUDA_PESTANA[pestana].detalle}</p>
        </div>
      </div>

      {mensajeError && <p className="error">{mensajeError}</p>}

      {cargando ? (
        <p className="ayuda">Cargando…</p>
      ) : pestana === 'historico' ? (
        <>
          <div className="barra">
            <input
              className="campo-busqueda"
              placeholder="Buscar por código o nombre…"
              value={buscar}
              onChange={(e) => setBuscar(e.target.value)}
            />
            <label className="check">
              <input
                type="checkbox"
                checked={soloCmv}
                onChange={(e) => setSoloCmv(e.target.checked)}
              />
              Solo con relación CMV/precio (1:1 o receta)
            </label>
          </div>

          {pagina.length === 0 ? (
            <Vacio
              titulo={buscar.trim() ? 'Sin resultados' : 'Aún no hay productos'}
              detalle={
                buscar.trim()
                  ? `Nada coincide con «${buscar.trim()}».`
                  : 'Crea productos y registra compras para ver su histórico de costos.'
              }
            />
          ) : (
            <>
              <div className="tabla-wrap tabla-wrap--cards">
                <table className="tabla tabla--cards">
                  <thead>
                    <tr>
                      <ThOrdenable campo="nombre" orden={orden} direccion={direccion} onOrdenar={alternar}>
                        Producto
                      </ThOrdenable>
                      <ThOrdenable campo="mejor" orden={orden} direccion={direccion} onOrdenar={alternar}>
                        Mejor precio 6 sem
                      </ThOrdenable>
                      <ThOrdenable campo="costo" orden={orden} direccion={direccion} onOrdenar={alternar}>
                        Costo vigente
                      </ThOrdenable>
                      <ThOrdenable campo="variacion" orden={orden} direccion={direccion} onOrdenar={alternar}>
                        Variación 6 sem
                      </ThOrdenable>
                      <ThOrdenable campo="precio" orden={orden} direccion={direccion} onOrdenar={alternar}>
                        Precio venta
                      </ThOrdenable>
                      <ThOrdenable campo="cmv" orden={orden} direccion={direccion} onOrdenar={alternar}>
                        CMV / venta
                      </ThOrdenable>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagina.map((f) => (
                      <tr key={f.producto_id}>
                        <td data-label="Producto">
                          <strong>{f.nombre}</strong>
                          <small className="ayuda"> · {f.codigo}</small>
                          {f.tiene_receta && (
                            <>
                              {' '}
                              <span className="badge badge--info">Receta</span>
                            </>
                          )}
                        </td>
                        <td data-label="Mejor precio 6 sem" className="costo-celda">
                          {f.mejor_precio_6s == null ? (
                            '—'
                          ) : (
                            <>
                              {moneda.format(f.mejor_precio_6s)}
                              <small>
                                {f.mejor_origen === 'Manual'
                                  ? 'Manual'
                                  : f.mejor_proveedor || 'Sin proveedor'}
                                {f.mejor_fecha
                                  ? ` · ${formatoFecha(f.mejor_fecha).split(',')[0]}`
                                  : ''}
                              </small>
                            </>
                          )}
                        </td>
                        <td data-label="Costo vigente" className="costo-celda">
                          {f.costo_vigente == null ? (
                            <>
                              <span className="badge badge--off">Sin costo</span>
                              {f.faltantes.length > 0 && (
                                <small>Falta: {f.faltantes.join(', ')}</small>
                              )}
                            </>
                          ) : (
                            <>
                              {moneda.format(f.costo_vigente)}
                              <small>{f.origen_costo}</small>
                            </>
                          )}
                        </td>
                        <td data-label="Variación 6 sem">
                          <span className={claseVariacion(f.variacion_6s)}>
                            {f.variacion_6s == null
                              ? '—'
                              : `${f.variacion_6s > 0 ? '+' : ''}${f.variacion_6s.toFixed(1)}%`}
                          </span>
                        </td>
                        <td data-label="Precio venta" className="derecha">
                          {moneda.format(f.precio)}
                        </td>
                        <td data-label="CMV / venta" className="costo-celda">
                          {f.mostrar_cmv && f.cmv_pct != null ? (
                            <>
                              <strong>{pct(f.cmv_pct)} del precio</strong>
                              <small>
                                Margen {moneda.format(f.margen ?? 0)} ({pct(f.margen_pct)})
                              </small>
                            </>
                          ) : (
                            <span className="ayuda">—</span>
                          )}
                        </td>
                        <td className="celda-accion">
                          <div className="acciones-fila">
                            {f.tiene_receta ? (
                              puedeEditar && (
                                <button
                                  className="boton boton--mini"
                                  onClick={() => {
                                    const receta =
                                      recetas.find((r) => r.producto_id === f.producto_id) ??
                                      null
                                    setFormReceta({
                                      abierto: true,
                                      receta,
                                      productoIdInicial: f.producto_id,
                                    })
                                  }}
                                >
                                  Receta
                                </button>
                              )
                            ) : (
                              <button
                                className="boton boton--mini"
                                onClick={() => setHistorial(f)}
                              >
                                Historial
                              </button>
                            )}
                            {puedeEditar && !f.tiene_receta && (
                              <button
                                className="boton boton--mini boton--secundario"
                                onClick={() =>
                                  setFormManual({
                                    abierto: true,
                                    productoId: f.producto_id,
                                  })
                                }
                              >
                                Costo manual
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
                total={ordenados.length}
                skip={skip}
                limit={tamano}
                onCambiar={setSkip}
              />
            </>
          )}
        </>
      ) : pestana === 'preparaciones' ? (
        <>
          {recetas.length === 0 ? (
            <Vacio
              titulo="Aún no hay recetas"
              detalle="Crea una receta para calcular el costo de un producto transformado a partir de sus insumos."
            />
          ) : (
            <div className="tabla-wrap tabla-wrap--cards">
              <table className="tabla tabla--cards">
                <thead>
                  <tr>
                    <th>Preparación</th>
                    <th className="derecha">Rendimiento</th>
                    <th className="derecha">Costo unitario</th>
                    <th className="derecha">Precio venta</th>
                    <th>CMV / venta</th>
                    <th>Estado</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {recetas.map((r) => (
                    <tr key={r.producto_id}>
                      <td data-label="Preparación">
                        <strong>{r.nombre}</strong>
                        <small className="ayuda"> · {r.codigo}</small>
                      </td>
                      <td data-label="Rendimiento" className="derecha">
                        {r.rendimiento}
                      </td>
                      <td data-label="Costo unitario" className="derecha">
                        {r.costo_unitario == null
                          ? '—'
                          : moneda.format(r.costo_unitario)}
                      </td>
                      <td data-label="Precio venta" className="derecha">
                        {moneda.format(r.precio)}
                      </td>
                      <td data-label="CMV / venta" className="costo-celda">
                        {r.cmv_pct == null ? (
                          '—'
                        ) : (
                          <>
                            <strong>{pct(r.cmv_pct)} del precio</strong>
                            <small>
                              Margen {moneda.format(r.margen ?? 0)} ({pct(r.margen_pct)})
                            </small>
                          </>
                        )}
                      </td>
                      <td data-label="Estado">
                        {r.completo ? (
                          <span className="badge badge--on">Completa</span>
                        ) : (
                          <>
                            <span className="badge badge--warn">Incompleta</span>
                            {r.faltantes.length > 0 && (
                              <small className="ayuda">
                                {' '}
                                Falta: {r.faltantes.join(', ')}
                              </small>
                            )}
                          </>
                        )}
                      </td>
                      <td className="celda-accion">
                        <div className="acciones-fila">
                          {puedeEditar && (
                            <>
                              <button
                                className="boton boton--mini"
                                onClick={() =>
                                  setFormReceta({
                                    abierto: true,
                                    receta: r,
                                    productoIdInicial: r.producto_id,
                                  })
                                }
                              >
                                Editar
                              </button>
                              <button
                                className="boton boton--mini boton--danger"
                                onClick={() => void borrarReceta(r)}
                              >
                                Eliminar
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : (
        <>
          {manuales.length === 0 ? (
            <Vacio
              titulo="Aún no hay costos manuales"
              detalle="Registra un costo a mano para insumos que no tienen compras registradas."
            />
          ) : (
            <div className="tabla-wrap tabla--cards">
              <table className="tabla tabla--cards">
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th>Fecha</th>
                    <th className="derecha">Costo unitario</th>
                    <th>Nota</th>
                    <th>Registró</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {manuales.map((m) => (
                    <tr key={m.id}>
                      <td data-label="Producto">
                        <strong>{m.producto_nombre}</strong>
                        <small className="ayuda"> · {m.producto_codigo}</small>
                      </td>
                      <td data-label="Fecha">{formatoFecha(m.fecha)}</td>
                      <td data-label="Costo unitario" className="derecha">
                        {moneda.format(m.costo_unitario)}
                      </td>
                      <td data-label="Nota">{m.nota || '—'}</td>
                      <td data-label="Registró">{m.usuario_nombre || '—'}</td>
                      <td className="celda-accion">
                        {puedeEditar && (
                          <button
                            className="boton boton--mini boton--danger"
                            onClick={() => void borrarManual(m)}
                          >
                            Eliminar
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {historial && (
        <HistorialModal fila={historial} onCerrar={() => setHistorial(null)} />
      )}

      {formManual.abierto && (
        <FormCostoManual
          insumos={productosSinReceta}
          productoIdInicial={formManual.productoId}
          onCerrar={() => setFormManual({ abierto: false })}
          onGuardado={() => {
            setFormManual({ abierto: false })
            setPestana('manuales')
            void cargar()
          }}
        />
      )}

      {formReceta.abierto && (
        <FormReceta
          receta={formReceta.receta}
          productoIdInicial={formReceta.productoIdInicial}
          insumos={insumos}
          productosSinReceta={productosSinReceta}
          onCerrar={() => setFormReceta({ abierto: false, receta: null })}
          onGuardado={() => {
            setFormReceta({ abierto: false, receta: null })
            setPestana('preparaciones')
            void cargar()
          }}
        />
      )}
    </div>
  )
}

function TarjetaResumen({
  titulo,
  valor,
  alerta,
}: {
  titulo: string
  valor: string
  alerta?: boolean
}) {
  return (
    <div className={alerta ? 'tarjeta-resumen tarjeta-resumen--alerta' : 'tarjeta-resumen'}>
      <small>{titulo}</small>
      <strong>{valor}</strong>
    </div>
  )
}

function HistorialModal({
  fila,
  onCerrar,
}: {
  fila: ResumenCosto
  onCerrar: () => void
}) {
  const [puntos, setPuntos] = useState<HistorialCosto[]>([])
  const [todo, setTodo] = useState(false)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let activo = true
    setCargando(true)
    setError('')
    historialProducto(fila.producto_id, todo ? {} : { desde: haceSemanas(6) })
      .then((datos) => {
        if (activo) setPuntos(datos)
      })
      .catch((err) => {
        if (activo) setError(err instanceof Error ? err.message : 'Error al cargar')
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    return () => {
      activo = false
    }
  }, [fila.producto_id, todo])

  const maxCosto = puntos.reduce((max, p) => Math.max(max, p.costo_unitario), 0)

  return (
    <div className="modal-overlay" onClick={onCerrar}>
      <div className="modal modal--ancho" onClick={(e) => e.stopPropagation()}>
        <h2>Historial de costos · {fila.nombre}</h2>
        <div className="historial-resumen">
          <div>
            <small>Mejor precio 6 sem</small>
            <strong>
              {fila.mejor_precio_6s == null
                ? '—'
                : moneda.format(fila.mejor_precio_6s)}
            </strong>
          </div>
          <div>
            <small>Costo vigente</small>
            <strong>
              {fila.costo_vigente == null
                ? '—'
                : moneda.format(fila.costo_vigente)}
            </strong>
          </div>
          <div>
            <small>Variación 6 sem</small>
            <strong className={claseVariacion(fila.variacion_6s)}>
              {fila.variacion_6s == null
                ? '—'
                : `${fila.variacion_6s > 0 ? '+' : ''}${fila.variacion_6s.toFixed(1)}%`}
            </strong>
          </div>
          <div>
            <small>Precio venta</small>
            <strong>{moneda.format(fila.precio)}</strong>
          </div>
        </div>

        <label className="check">
          <input
            type="checkbox"
            checked={todo}
            onChange={(e) => setTodo(e.target.checked)}
          />
          Ver todo el histórico
        </label>

        {error && <p className="error">{error}</p>}
        {cargando ? (
          <p className="ayuda">Cargando…</p>
        ) : puntos.length === 0 ? (
          <p className="ayuda">No hay costos registrados en este período.</p>
        ) : (
          <div className="tabla-wrap">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th className="derecha">Costo unitario</th>
                  <th>Origen</th>
                  <th>Proveedor / nota</th>
                  <th className="derecha">Cantidad</th>
                </tr>
              </thead>
              <tbody>
                {puntos.map((p, i) => (
                  <tr key={`${p.fecha}-${i}`}>
                    <td>{formatoFecha(p.fecha)}</td>
                    <td className="derecha">
                      <div className="costo-barra">
                        <span
                          style={{
                            width: `${maxCosto > 0 ? (p.costo_unitario / maxCosto) * 100 : 0}%`,
                          }}
                        />
                      </div>
                      {moneda.format(p.costo_unitario)}
                    </td>
                    <td>{p.origen}</td>
                    <td>{p.proveedor || p.nota || p.referencia || '—'}</td>
                    <td className="derecha">{p.cantidad ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="acciones">
          <button className="boton boton--secundario" onClick={onCerrar}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  )
}

function FormCostoManual({
  insumos,
  productoIdInicial,
  onCerrar,
  onGuardado,
}: {
  insumos: InsumoOpcion[]
  productoIdInicial?: number
  onCerrar: () => void
  onGuardado: () => void
}) {
  const [productoId, setProductoId] = useState(
    productoIdInicial ? String(productoIdInicial) : '',
  )
  const [fecha, setFecha] = useState(hoyISO())
  const [costo, setCosto] = useState('')
  const [nota, setNota] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setGuardando(true)
    try {
      await crearCostoManual({
        producto_id: Number(productoId),
        fecha,
        costo_unitario: Number(costo),
        nota: nota.trim() || null,
      })
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar el costo')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>Registrar costo manual</h2>
        <p className="ayuda">
          Se usa como costo vigente del insumo y reemplaza al promedio de compras.
        </p>
        {error && <p className="error">{error}</p>}
        <label>
          Producto
          <select
            value={productoId}
            onChange={(e) => setProductoId(e.target.value)}
            required
          >
            <option value="">Selecciona un producto…</option>
            {insumos.map((i) => (
              <option key={i.producto_id} value={i.producto_id}>
                {i.nombre} ({i.codigo})
              </option>
            ))}
          </select>
        </label>
        <div className="campos-dobles">
          <label>
            Fecha
            <input
              type="date"
              value={fecha}
              onChange={(e) => setFecha(e.target.value)}
              required
            />
          </label>
          <label>
            Costo unitario
            <input
              type="number"
              min="0"
              step="0.01"
              value={costo}
              onChange={(e) => setCosto(e.target.value)}
              required
            />
          </label>
        </div>
        <label>
          Nota
          <input
            value={nota}
            onChange={(e) => setNota(e.target.value)}
            placeholder="Opcional"
          />
        </label>
        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button type="submit" className="boton" disabled={guardando}>
            {guardando ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </form>
    </div>
  )
}

type FilaReceta = { productoId: string; cantidad: string }

function FormReceta({
  receta,
  productoIdInicial,
  insumos,
  productosSinReceta,
  onCerrar,
  onGuardado,
}: {
  receta: Receta | null
  productoIdInicial?: number
  insumos: InsumoOpcion[]
  productosSinReceta: InsumoOpcion[]
  onCerrar: () => void
  onGuardado: () => void
}) {
  const esEdicion = receta !== null
  const [productoId, setProductoId] = useState(
    receta ? String(receta.producto_id) : productoIdInicial ? String(productoIdInicial) : '',
  )
  const [rendimiento, setRendimiento] = useState(
    receta ? String(receta.rendimiento) : '1',
  )
  const [notas, setNotas] = useState(receta?.notas ?? '')
  const [filas, setFilas] = useState<FilaReceta[]>(() =>
    receta && receta.items.length > 0
      ? receta.items.map((i) => ({
          productoId: String(i.producto_id),
          cantidad: String(i.cantidad),
        }))
      : [{ productoId: '', cantidad: '1' }],
  )
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  const producto = insumos.find((i) => i.producto_id === Number(productoId))

  let total = 0
  let incompleto = false
  for (const fila of filas) {
    if (!fila.productoId) continue
    const insumo = insumos.find((i) => i.producto_id === Number(fila.productoId))
    const cantidad = Number(fila.cantidad)
    if (!insumo || insumo.costo == null) {
      incompleto = true
      continue
    }
    if (cantidad > 0) {
      total += insumo.costo * cantidad
    }
  }
  const rendimientoNum = Number(rendimiento)
  const costoUnitario = rendimientoNum > 0 ? total / rendimientoNum : 0
  const margen = producto ? producto.precio - costoUnitario : null
  const margenPct =
    producto && producto.precio > 0 && margen != null
      ? (margen / producto.precio) * 100
      : null

  function actualizarFila(indice: number, cambios: Partial<FilaReceta>) {
    setFilas((prev) =>
      prev.map((fila, i) => (i === indice ? { ...fila, ...cambios } : fila)),
    )
  }

  function agregarFila() {
    setFilas((prev) => [...prev, { productoId: '', cantidad: '1' }])
  }

  function quitarFila(indice: number) {
    setFilas((prev) => prev.filter((_, i) => i !== indice))
  }

  function opcionesInsumo(indice: number): InsumoOpcion[] {
    const usados = new Set(
      filas
        .filter((_, i) => i !== indice)
        .map((f) => Number(f.productoId))
        .filter((id) => !Number.isNaN(id) && id > 0),
    )
    return insumos.filter(
      (i) => i.producto_id !== Number(productoId) && !usados.has(i.producto_id),
    )
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const filaInvalida = filas.some(
      (f) => f.productoId && (!Number(f.cantidad) || Number(f.cantidad) <= 0),
    )
    if (filaInvalida) {
      setError('Cada insumo seleccionado debe tener una cantidad mayor a cero.')
      return
    }
    const items = filas
      .filter((f) => f.productoId && Number(f.cantidad) > 0)
      .map((f) => ({
        producto_id: Number(f.productoId),
        cantidad: Number(f.cantidad),
      }))
    if (!productoId) {
      setError('Selecciona el producto que se prepara.')
      return
    }
    if (items.length === 0) {
      setError('Agrega al menos un insumo con cantidad mayor a cero.')
      return
    }
    setGuardando(true)
    try {
      await guardarReceta(Number(productoId), {
        rendimiento: Number(rendimiento),
        notas: notas.trim() || null,
        items,
      })
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar la receta')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form
        className="modal modal--ancho"
        onClick={(e) => e.stopPropagation()}
        onSubmit={onSubmit}
      >
        <h2>{esEdicion ? 'Editar receta' : 'Nueva receta'}</h2>
        {error && <p className="error">{error}</p>}

        <label>
          Producto que se prepara
          <select
            value={productoId}
            onChange={(e) => setProductoId(e.target.value)}
            disabled={esEdicion}
            required
          >
            <option value="">Selecciona un producto…</option>
            {(esEdicion ? insumos : productosSinReceta).map((i) => (
              <option key={i.producto_id} value={i.producto_id}>
                {i.nombre} ({i.codigo})
                {i.tiene_receta ? ' · ya tiene receta' : ''}
              </option>
            ))}
          </select>
        </label>

        <div className="campos-dobles">
          <label>
            Rendimiento (unidades que produce)
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={rendimiento}
              onChange={(e) => setRendimiento(e.target.value)}
              required
            />
          </label>
          <label>
            Notas
            <input
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              placeholder="Opcional"
            />
          </label>
        </div>

        <h3>Insumos</h3>
        <div className="receta-items">
          {filas.map((fila, indice) => {
            const insumo = insumos.find(
              (i) => i.producto_id === Number(fila.productoId),
            )
            const cantidad = Number(fila.cantidad)
            const subtotal =
              insumo && insumo.costo != null && cantidad > 0
                ? insumo.costo * cantidad
                : null
            return (
              <div className="receta-item" key={indice}>
                <label>
                  Insumo
                  <select
                    value={fila.productoId}
                    onChange={(e) =>
                      actualizarFila(indice, { productoId: e.target.value })
                    }
                  >
                    <option value="">Selecciona…</option>
                    {opcionesInsumo(indice).map((i) => (
                      <option key={i.producto_id} value={i.producto_id}>
                        {i.nombre} ({i.codigo})
                        {i.costo == null ? ' · sin costo' : ` · ${moneda.format(i.costo)}`}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Cantidad
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={fila.cantidad}
                    onChange={(e) =>
                      actualizarFila(indice, { cantidad: e.target.value })
                    }
                  />
                </label>
                <div className="receta-item__subtotal">
                  <small>Subtotal</small>
                  <strong>{subtotal == null ? '—' : moneda.format(subtotal)}</strong>
                  {filas.length > 1 && (
                    <button
                      type="button"
                      className="boton boton--mini boton--danger"
                      onClick={() => quitarFila(indice)}
                    >
                      Quitar
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
        <button type="button" className="boton boton--secundario" onClick={agregarFila}>
          + Agregar insumo
        </button>

        <div className="receta-preview">
          <div>
            <small>Costo total</small>
            <strong>{moneda.format(total)}</strong>
          </div>
          <div>
            <small>Costo por unidad</small>
            <strong>{moneda.format(costoUnitario)}</strong>
          </div>
          {producto && (
            <>
              <div>
                <small>Precio de venta</small>
                <strong>{moneda.format(producto.precio)}</strong>
              </div>
              <div>
                <small>Margen</small>
                <strong className={margen != null && margen < 0 ? 'costo-sube' : 'costo-baja'}>
                  {margen == null ? '—' : moneda.format(margen)}
                  {margenPct != null ? ` (${margenPct.toFixed(1)}%)` : ''}
                </strong>
              </div>
            </>
          )}
        </div>
        {incompleto && (
          <p className="ayuda">
            Hay insumos sin costo: la receta se guardará como incompleta.
          </p>
        )}

        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button type="submit" className="boton" disabled={guardando}>
            {guardando ? 'Guardando…' : 'Guardar receta'}
          </button>
        </div>
      </form>
    </div>
  )
}
