import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  abrirCaja,
  cerrarCaja,
  esFormaBanco,
  listarTurnos,
  obtenerCajaActiva,
  obtenerFacturasPendientes,
  obtenerMovimientos,
  obtenerResumenVentasTurno,
  registrarMovimiento,
  categoriasDe,
  type FacturaPendienteCierre,
  type RegistroCaja,
  type ResumenVentasTurno,
  type TurnoCaja,
  type TurnoCajaHistorial,
} from '../api/caja'
import type { FormaPago } from '../api/types'
import { formatoFecha, moneda } from '../lib/formato'
import { confirmarCierre } from '../lib/modal'
import { AyudaContextual } from '../components/AyudaContextual'
import { Paginacion } from '../components/Paginacion'
import { ThOrdenable } from '../components/ThOrdenable'
import { useOrdenLocal, useOrdenServidor, type Accesores } from '../lib/orden'
import { usePaginacion } from '../lib/usePaginacion'
import { Vacio } from '../components/Vacio'
import { useAuth } from '../auth/useAuth'

// "Otro" se conserva en la base para el histórico, pero ya no se ofrece en la UI.
const FORMAS_PAGO: FormaPago[] = ['Efectivo', 'Transferencia', 'Tarjeta']

type Bucket = 'efectivo' | 'banco'

const ACCESORES_MOVIMIENTOS: Accesores<RegistroCaja> = {
  fecha: (m) => m.fecha,
  tipo: (m) => m.tipo,
  referencia: (m) => m.referencia,
  categoria: (m) => m.categoria ?? '',
  forma_pago: (m) => m.forma_pago ?? '',
  monto: (m) => m.monto,
}

type FilaCategoria = {
  categoria: string
  cantidad: number
  entradas: number
  salidas: number
  neto: number
}

function resumirCategorias(movimientos: RegistroCaja[]): FilaCategoria[] {
  const mapa = new Map<string, FilaCategoria>()
  for (const m of movimientos) {
    if (m.tipo !== 'Entrada' && m.tipo !== 'Salida') continue
    const categoria = m.categoria ?? 'Sin categoría'
    const fila =
      mapa.get(categoria) ??
      { categoria, cantidad: 0, entradas: 0, salidas: 0, neto: 0 }
    fila.cantidad += 1
    if (m.tipo === 'Entrada') {
      fila.entradas += m.monto
      fila.neto += m.monto
    } else {
      fila.salidas += m.monto
      fila.neto -= m.monto
    }
    mapa.set(categoria, fila)
  }
  return [...mapa.values()].sort((a, b) => a.categoria.localeCompare(b.categoria))
}

function bucketDe(forma_pago: FormaPago): Bucket {
  return esFormaBanco(forma_pago) ? 'banco' : 'efectivo'
}

function Cifras({ efectivo, banco }: { efectivo: string; banco: string }) {
  return (
    <div className="cifra-par">
      <span>Ef {efectivo}</span>
      <span>Ban {banco}</span>
    </div>
  )
}

export function Caja() {
  const navigate = useNavigate()
  const { tienePermiso } = useAuth()
  const puedeOperar = tienePermiso('caja.operar')
  const puedeIngresar = tienePermiso('ingresos.crear')
  const [turno, setTurno] = useState<TurnoCaja | null>(null)
  const [movimientos, setMovimientos] = useState<RegistroCaja[]>([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [abrirModal, setAbrirModal] = useState(false)
  const [movModal, setMovModal] = useState(false)
  const [cerrarModal, setCerrarModal] = useState(false)
  const [histModal, setHistModal] = useState(false)
  const [categoriaFiltro, setCategoriaFiltro] = useState('Todas')

  const cargar = useCallback(async () => {
    try {
      const activa = await obtenerCajaActiva()
      setTurno(activa)
      setMovimientos(activa ? await obtenerMovimientos(activa.id) : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar la caja')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    void cargar()
  }, [cargar])

  const { entradas, salidas } = useMemo(() => {
    const ent: Record<Bucket, number> = { efectivo: 0, banco: 0 }
    const sal: Record<Bucket, number> = { efectivo: 0, banco: 0 }
    for (const m of movimientos) {
      const bucket = bucketDe(m.forma_pago)
      if (m.tipo === 'Entrada') ent[bucket] += m.monto
      else if (m.tipo === 'Salida') sal[bucket] += m.monto
    }
    return { entradas: ent, salidas: sal }
  }, [movimientos])

  const esperadoEfectivo =
    (turno?.saldo_inicial_efectivo ?? 0) + entradas.efectivo - salidas.efectivo
  const esperadoBanco =
    (turno?.saldo_inicial_banco ?? 0) + entradas.banco - salidas.banco

  const categoriasDisponibles = useMemo(
    () =>
      [...new Set(movimientos.map((m) => m.categoria ?? 'Sin categoría'))].sort(
        (a, b) => a.localeCompare(b),
      ),
    [movimientos],
  )

  const movimientosFiltrados = useMemo(
    () =>
      categoriaFiltro === 'Todas'
        ? movimientos
        : movimientos.filter((m) => (m.categoria ?? 'Sin categoría') === categoriaFiltro),
    [movimientos, categoriaFiltro],
  )

  const resumenCategorias = useMemo(
    () => resumirCategorias(movimientos),
    [movimientos],
  )

  const movsOrdenados = useOrdenLocal(movimientosFiltrados, ACCESORES_MOVIMIENTOS, {
    campo: 'fecha',
    direccion: 'desc',
  })

  if (cargando) return <p className="ayuda">Cargando…</p>

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Caja</h1>
          <p className="ayuda">{turno ? `Turno #${turno.id} abierto` : 'Sin turno abierto'}</p>
        </div>
        <div className="acciones-fila">
          <button className="boton boton--secundario" onClick={() => setHistModal(true)}>
            Historial de turnos
          </button>
          {turno ? (
            <>
              {puedeIngresar && (
                <button
                  className="boton boton--secundario"
                  onClick={() => navigate('/ingresos?nuevo=1')}
                >
                  Ingreso de inventario
                </button>
              )}
              {puedeOperar && (
                <>
                  <button className="boton boton--secundario" onClick={() => setMovModal(true)}>
                    Registrar movimiento
                  </button>
                  <button className="boton boton--danger" onClick={() => setCerrarModal(true)}>
                    Cerrar caja
                  </button>
                </>
              )}
            </>
          ) : puedeOperar ? (
            <button className="boton" onClick={() => setAbrirModal(true)}>
              Abrir caja
            </button>
          ) : null}
        </div>
      </header>

      <AyudaContextual
        titulo="Cómo cuadrar el turno"
        detalle="El turno agrupa ventas, pagos y movimientos manuales. Abre con saldos iniciales, registra entradas o salidas con categoría y cierra con el saldo real. El cierre compara lo esperado contra lo real; lo reservado en bolsillos se consulta en Balance."
      />

      {error && <p className="error">{error}</p>}

      {!turno ? (
        <Vacio
          titulo="No hay una caja abierta"
          detalle="Abre un turno para registrar movimientos y cobrar ventas."
        />
      ) : (
        <>
          <div className="resumen">
            <div className="resumen__item">
              <span className="ayuda">Saldo inicial efectivo</span>
              <strong>{moneda.format(turno.saldo_inicial_efectivo)}</strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Saldo inicial banco</span>
              <strong>{moneda.format(turno.saldo_inicial_banco)}</strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Entradas (Ef / Ban)</span>
              <strong>
                {moneda.format(entradas.efectivo)} / {moneda.format(entradas.banco)}
              </strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Salidas (Ef / Ban)</span>
              <strong>
                {moneda.format(salidas.efectivo)} / {moneda.format(salidas.banco)}
              </strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Esperado efectivo</span>
              <strong>{moneda.format(esperadoEfectivo)}</strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Esperado banco</span>
              <strong>{moneda.format(esperadoBanco)}</strong>
            </div>
          </div>

          <p className="ayuda">
            Abierta el {formatoFecha(turno.fecha_apertura)}
          </p>

          {movimientos.length === 0 ? (
            <Vacio
              titulo="Sin movimientos"
              detalle="Aún no hay entradas ni salidas en este turno."
            />
          ) : (
            <>
              {resumenCategorias.length > 0 && (
                <section className="panel">
                  <h3>Resumen por categoría</h3>
                  <div className="tabla-wrap">
                    <table className="tabla">
                      <thead>
                        <tr>
                          <th>Categoría</th>
                          <th className="derecha">Movimientos</th>
                          <th className="derecha">Entradas</th>
                          <th className="derecha">Salidas</th>
                          <th className="derecha">Neto</th>
                        </tr>
                      </thead>
                      <tbody>
                        {resumenCategorias.map((fila) => (
                          <tr key={fila.categoria}>
                            <td>{fila.categoria}</td>
                            <td className="derecha">{fila.cantidad}</td>
                            <td className="derecha">{moneda.format(fila.entradas)}</td>
                            <td className="derecha">{moneda.format(fila.salidas)}</td>
                            <td className="derecha">{moneda.format(fila.neto)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              <div className="barra">
                <label className="campo-fecha">
                  <span>Categoría</span>
                  <select
                    value={categoriaFiltro}
                    onChange={(e) => setCategoriaFiltro(e.target.value)}
                  >
                    <option value="Todas">Todas</option>
                    {categoriasDisponibles.map((categoria) => (
                      <option key={categoria} value={categoria}>
                        {categoria}
                      </option>
                    ))}
                  </select>
                </label>
                <span className="ayuda">
                  {movsOrdenados.items.length} de {movimientos.length} movimiento(s)
                </span>
              </div>

              {movsOrdenados.items.length === 0 ? (
                <p className="ayuda">No hay movimientos con esa categoría.</p>
              ) : (
                <div className="tabla-wrap tabla-wrap--cards">
                  <table className="tabla tabla--cards">
                    <thead>
                      <tr>
                        <ThOrdenable campo="fecha" orden={movsOrdenados.orden} direccion={movsOrdenados.direccion} onOrdenar={movsOrdenados.alternar}>
                          Fecha
                        </ThOrdenable>
                        <ThOrdenable campo="tipo" orden={movsOrdenados.orden} direccion={movsOrdenados.direccion} onOrdenar={movsOrdenados.alternar}>
                          Tipo
                        </ThOrdenable>
                        <ThOrdenable campo="referencia" orden={movsOrdenados.orden} direccion={movsOrdenados.direccion} onOrdenar={movsOrdenados.alternar}>
                          Referencia
                        </ThOrdenable>
                        <ThOrdenable campo="categoria" orden={movsOrdenados.orden} direccion={movsOrdenados.direccion} onOrdenar={movsOrdenados.alternar}>
                          Categoría
                        </ThOrdenable>
                        <ThOrdenable campo="forma_pago" orden={movsOrdenados.orden} direccion={movsOrdenados.direccion} onOrdenar={movsOrdenados.alternar}>
                          Forma de pago
                        </ThOrdenable>
                        <ThOrdenable
                          campo="monto"
                          orden={movsOrdenados.orden}
                          direccion={movsOrdenados.direccion}
                          onOrdenar={movsOrdenados.alternar}
                          className="derecha"
                        >
                          Monto
                        </ThOrdenable>
                      </tr>
                    </thead>
                    <tbody>
                      {movsOrdenados.items.map((m) => (
                        <tr key={m.id}>
                          <td data-label="Fecha">{formatoFecha(m.fecha)}</td>
                          <td data-label="Tipo">
                            <span
                              className={
                                m.tipo === 'Salida'
                                  ? 'badge badge--off'
                                  : m.tipo === 'Entrada'
                                    ? 'badge badge--on'
                                    : 'badge badge--info'
                              }
                            >
                              {m.tipo}
                            </span>
                          </td>
                          <td data-label="Referencia">{m.referencia}</td>
                          <td data-label="Categoría">{m.categoria ?? '—'}</td>
                          <td data-label="Forma de pago">{m.forma_pago ?? '—'}</td>
                          <td data-label="Monto" className="derecha">
                            {moneda.format(m.monto)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </>
      )}

      {abrirModal && (
        <FormAbrir
          onCerrar={() => setAbrirModal(false)}
          onGuardado={() => {
            setAbrirModal(false)
            void cargar()
          }}
        />
      )}

      {movModal && (
        <FormMovimiento
          onCerrar={() => setMovModal(false)}
          onGuardado={() => {
            setMovModal(false)
            void cargar()
          }}
        />
      )}

      {cerrarModal && turno && (
        <FormCerrar
          turno={turno}
          esperadoEfectivo={esperadoEfectivo}
          esperadoBanco={esperadoBanco}
          onCerrar={() => setCerrarModal(false)}
          onGuardado={() => {
            setCerrarModal(false)
            void cargar()
          }}
        />
      )}

      {histModal && <HistorialTurnos onCerrar={() => setHistModal(false)} />}
    </div>
  )
}

function FormAbrir({ onCerrar, onGuardado }: { onCerrar: () => void; onGuardado: () => void }) {
  const [efectivo, setEfectivo] = useState('0')
  const [banco, setBanco] = useState('0')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  const valorEfectivo = Number(efectivo)
  const valorBanco = Number(banco)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (
      Number.isNaN(valorEfectivo) ||
      Number.isNaN(valorBanco) ||
      valorEfectivo < 0 ||
      valorBanco < 0
    ) {
      setError('Los saldos iniciales no pueden ser negativos')
      return
    }
    setGuardando(true)
    try {
      await abrirCaja({
        saldo_inicial_efectivo: valorEfectivo,
        saldo_inicial_banco: valorBanco,
      })
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al abrir la caja')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>Abrir caja</h2>
        {error && <p className="error">{error}</p>}
        <div className="fila-campos">
          <label>
            Saldo inicial efectivo
            <input
              type="number"
              min="0"
              step="0.01"
              value={efectivo}
              onChange={(e) => setEfectivo(e.target.value)}
            />
          </label>
          <label>
            Saldo inicial banco
            <input
              type="number"
              min="0"
              step="0.01"
              value={banco}
              onChange={(e) => setBanco(e.target.value)}
            />
          </label>
        </div>
        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button type="submit" className="boton" disabled={guardando}>
            {guardando ? 'Abriendo…' : 'Abrir'}
          </button>
        </div>
      </form>
    </div>
  )
}

function FormMovimiento({ onCerrar, onGuardado }: { onCerrar: () => void; onGuardado: () => void }) {
  const [tipo, setTipo] = useState<'Entrada' | 'Salida'>('Entrada')
  const [categoria, setCategoria] = useState('')
  const [referencia, setReferencia] = useState('')
  const [monto, setMonto] = useState('')
  const [formaPago, setFormaPago] = useState<FormaPago>('Efectivo')
  const [observacion, setObservacion] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  const categorias = categoriasDe(tipo)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const valor = Number(monto)
    if (!referencia.trim()) {
      setError('La referencia es obligatoria')
      return
    }
    if (!categoria) {
      setError('Selecciona una categoría')
      return
    }
    if (!valor || valor <= 0) {
      setError('El monto debe ser mayor a 0')
      return
    }
    setGuardando(true)
    try {
      await registrarMovimiento({
        tipo,
        referencia: referencia.trim(),
        monto: valor,
        forma_pago: formaPago,
        categoria,
        observacion: observacion.trim() || undefined,
      })
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al registrar el movimiento')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>Registrar movimiento</h2>
        {error && <p className="error">{error}</p>}
        <div className="fila-campos">
          <label>
            Tipo
            <select
              value={tipo}
              onChange={(e) => {
                setTipo(e.target.value as 'Entrada' | 'Salida')
                setCategoria('')
              }}
            >
              <option value="Entrada">Entrada</option>
              <option value="Salida">Salida</option>
            </select>
          </label>
          <label>
            Categoría
            <select
              value={categoria}
              onChange={(e) => setCategoria(e.target.value)}
              required
            >
              <option value="">Selecciona una categoría…</option>
              {categorias.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label>
          Referencia / concepto
          <input
            value={referencia}
            onChange={(e) => setReferencia(e.target.value)}
            placeholder={
              categoria === 'Aporte cultural'
                ? 'Ej.: Aporte cultural – Evento de octubre'
                : 'Ej.: Arriendo de octubre'
            }
          />
        </label>
        <p className="ayuda">
          La categoría permite filtrar y resumir los movimientos del turno.
        </p>
        <div className="fila-campos">
          <label>
            Monto
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
            <select value={formaPago} onChange={(e) => setFormaPago(e.target.value as FormaPago)}>
              {FORMAS_PAGO.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label>
          Observación (opcional)
          <input value={observacion} onChange={(e) => setObservacion(e.target.value)} />
        </label>
        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button type="submit" className="boton" disabled={guardando}>
            {guardando ? 'Guardando…' : 'Registrar'}
          </button>
        </div>
      </form>
    </div>
  )
}

function FormCerrar({
  turno,
  esperadoEfectivo,
  esperadoBanco,
  onCerrar,
  onGuardado,
}: {
  turno: TurnoCaja
  esperadoEfectivo: number
  esperadoBanco: number
  onCerrar: () => void
  onGuardado: () => void
}) {
  const [realEfectivo, setRealEfectivo] = useState(String(esperadoEfectivo))
  const [realBanco, setRealBanco] = useState(String(esperadoBanco))
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [pendientes, setPendientes] = useState<FacturaPendienteCierre[]>([])
  const [cargandoPendientes, setCargandoPendientes] = useState(true)
  const [resumen, setResumen] = useState<ResumenVentasTurno | null>(null)

  useEffect(() => {
    let activo = true
    setCargandoPendientes(true)
    obtenerFacturasPendientes(turno.id)
      .then((l) => {
        if (activo) setPendientes(l)
      })
      .catch(() => {
        if (activo) setPendientes([])
      })
      .finally(() => {
        if (activo) setCargandoPendientes(false)
      })
    obtenerResumenVentasTurno(turno.id)
      .then((r) => {
        if (activo) setResumen(r)
      })
      .catch(() => {
        if (activo) setResumen(null)
      })
    return () => {
      activo = false
    }
  }, [turno.id])

  const eventualesSinPagar = pendientes.filter((p) => p.es_eventual)

  const valorEfectivo = Number(realEfectivo)
  const valorBanco = Number(realBanco)
  const diferenciaEfectivo = Number.isNaN(valorEfectivo)
    ? 0
    : valorEfectivo - esperadoEfectivo
  const diferenciaBanco = Number.isNaN(valorBanco) ? 0 : valorBanco - esperadoBanco

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (eventualesSinPagar.length > 0) {
      setError(
        'Hay facturas de cliente eventual sin pagar. Asígnales un cliente o cóbralas antes de cerrar.',
      )
      return
    }
    if (
      Number.isNaN(valorEfectivo) ||
      Number.isNaN(valorBanco) ||
      valorEfectivo < 0 ||
      valorBanco < 0
    ) {
      setError('Los saldos reales no pueden ser negativos')
      return
    }
    setGuardando(true)
    try {
      await cerrarCaja(turno.id, {
        saldo_final_real_efectivo: valorEfectivo,
        saldo_final_real_banco: valorBanco,
      })
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cerrar la caja')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>Cerrar caja</h2>
        {error && <p className="error">{error}</p>}
        <div className="resumen">
          <div className="resumen__item">
            <span className="ayuda">Ventas del turno</span>
            <strong>{moneda.format(resumen?.ventas ?? 0)}</strong>
          </div>
          <div className="resumen__item">
            <span className="ayuda">Crédito (no cobrado)</span>
            <strong>−{moneda.format(resumen?.creditos ?? 0)}</strong>
          </div>
          <div className="resumen__item">
            <span className="ayuda">Total cobrado del turno</span>
            <strong>{moneda.format(resumen?.cobrado ?? 0)}</strong>
          </div>
          <div className="resumen__item">
            <span className="ayuda">Esperado efectivo</span>
            <strong>{moneda.format(esperadoEfectivo)}</strong>
          </div>
          <div className="resumen__item">
            <span className="ayuda">Esperado banco</span>
            <strong>{moneda.format(esperadoBanco)}</strong>
          </div>
          <div className="resumen__item">
            <span className="ayuda">Diferencia (Ef / Ban)</span>
            <strong>
              {moneda.format(diferenciaEfectivo)} / {moneda.format(diferenciaBanco)}
            </strong>
          </div>
        </div>
        <div className="fila-campos">
          <label>
            Saldo real en efectivo
            <input
              type="number"
              min="0"
              step="0.01"
              value={realEfectivo}
              onChange={(e) => setRealEfectivo(e.target.value)}
            />
          </label>
          <label>
            Saldo real en banco
            <input
              type="number"
              min="0"
              step="0.01"
              value={realBanco}
              onChange={(e) => setRealBanco(e.target.value)}
            />
          </label>
        </div>
        {cargandoPendientes ? (
          <p className="ayuda">Revisando facturas pendientes…</p>
        ) : pendientes.length > 0 ? (
          <div className="pendientes-cierre">
            <p className="ayuda">
              Facturas de este turno con saldo pendiente — pasarán a Crédito (
              {pendientes.length}):
            </p>
            <ul className="lista-pendientes">
              {pendientes.map((p) => (
                <li key={p.id}>
                  <span>
                    #{p.id} · {p.cliente_nombre || '—'}
                  </span>
                  <span className={p.es_eventual ? 'badge badge--warn' : 'badge badge--info'}>
                    {p.es_eventual ? 'Eventual · ' : ''}
                    Saldo {moneda.format(p.saldo)}
                  </span>
                </li>
              ))}
            </ul>
            {eventualesSinPagar.length > 0 && (
              <p className="error">
                Hay {eventualesSinPagar.length} factura(s) de cliente eventual sin pagar. Asígnales
                un cliente o cóbralas antes de cerrar la caja.
              </p>
            )}
          </div>
        ) : null}
        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button
            type="submit"
            className="boton boton--danger"
            disabled={guardando || eventualesSinPagar.length > 0}
          >
            {guardando ? 'Cerrando…' : 'Cerrar caja'}
          </button>
        </div>
      </form>
    </div>
  )
}

function HistorialTurnos({ onCerrar }: { onCerrar: () => void }) {
  const { orden, direccion, alternar } = useOrdenServidor()
  const cargar = useCallback(
    (params: {
      skip: number
      limit: number
      desde?: string
      hasta?: string
      orden?: string
      direccion?: 'asc' | 'desc'
    }) =>
      listarTurnos({
        skip: params.skip,
        limit: params.limit,
        desde: params.desde,
        hasta: params.hasta,
        orden: params.orden,
        direccion: params.direccion,
      }),
    [],
  )

  const { datos, skip, setSkip, desde, setDesde, hasta, setHasta, cargando, error, tamano } =
    usePaginacion(cargar, 25, orden, direccion)

  const [seleccion, setSeleccion] = useState<TurnoCajaHistorial | null>(null)
  const [movs, setMovs] = useState<RegistroCaja[]>([])
  const [cargandoMovs, setCargandoMovs] = useState(false)
  const [categoriaHistorial, setCategoriaHistorial] = useState('Todas')

  useEffect(() => {
    setCategoriaHistorial('Todas')
    if (!seleccion) {
      setMovs([])
      return
    }
    let cancelado = false
    setCargandoMovs(true)
    obtenerMovimientos(seleccion.id)
      .then((m) => {
        if (!cancelado) setMovs(m)
      })
      .catch(() => {
        if (!cancelado) setMovs([])
      })
      .finally(() => {
        if (!cancelado) setCargandoMovs(false)
      })
    return () => {
      cancelado = true
    }
  }, [seleccion])

  const items = datos?.items ?? []
  const categoriasHistorial = useMemo(
    () =>
      [...new Set(movs.map((m) => m.categoria ?? 'Sin categoría'))].sort((a, b) =>
        a.localeCompare(b),
      ),
    [movs],
  )
  const movsHistorialFiltrados = useMemo(
    () =>
      categoriaHistorial === 'Todas'
        ? movs
        : movs.filter(
            (m) => (m.categoria ?? 'Sin categoría') === categoriaHistorial,
          ),
    [movs, categoriaHistorial],
  )
  const movsOrdenados = useOrdenLocal(movsHistorialFiltrados, ACCESORES_MOVIMIENTOS, {
    campo: 'fecha',
    direccion: 'desc',
  })

  return (
    <div className="modal-overlay modal-overlay--full" onClick={onCerrar}>
      <div className="modal modal--ancho" onClick={(e) => e.stopPropagation()}>
        <h2>Turnos de caja cerrados</h2>
        {error && <p className="error">{error}</p>}

        <div className="fila-campos">
          <label>
            Desde
            <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
          </label>
          <label>
            Hasta
            <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
          </label>
        </div>

        {cargando ? (
          <p className="ayuda">Cargando…</p>
        ) : items.length === 0 ? (
          <Vacio
            titulo="Sin turnos cerrados"
            detalle="Aún no hay cierres de caja registrados en este rango."
          />
        ) : (
          <div className="tabla-wrap tabla-wrap--cards">
            <table className="tabla tabla--cards">
              <thead>
                <tr>
                  <ThOrdenable campo="id" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Turno
                  </ThOrdenable>
                  <ThOrdenable campo="apertura" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Apertura
                  </ThOrdenable>
                  <ThOrdenable campo="cierre" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Cierre
                  </ThOrdenable>
                  <ThOrdenable campo="abrio" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Abrió
                  </ThOrdenable>
                  <ThOrdenable campo="cerro" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Cerró
                  </ThOrdenable>
                  <th className="derecha">Esperado (Ef / Ban)</th>
                  <th className="derecha">Real (Ef / Ban)</th>
                  <th className="derecha">Diferencia (Ef / Ban)</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((t) => {
                  const activo = seleccion?.id === t.id
                  return (
                    <tr key={t.id}>
                      <td data-label="Turno">#{t.id}</td>
                      <td data-label="Apertura">{formatoFecha(t.fecha_apertura)}</td>
                      <td data-label="Cierre">
                        {t.fecha_cierre ? formatoFecha(t.fecha_cierre) : '—'}
                      </td>
                      <td data-label="Abrió">
                        {t.usuario_apertura_nombre ?? `#${t.usuario_apertura_id}`}
                      </td>
                      <td data-label="Cerró">
                        {t.usuario_cierre_nombre ??
                          (t.usuario_cierre_id ? `#${t.usuario_cierre_id}` : '—')}
                      </td>
                      <td data-label="Esperado" className="derecha">
                        <Cifras
                          efectivo={moneda.format(t.esperado_efectivo)}
                          banco={moneda.format(t.esperado_banco)}
                        />
                      </td>
                      <td data-label="Real" className="derecha">
                        <Cifras
                          efectivo={
                            t.saldo_final_real_efectivo != null
                              ? moneda.format(t.saldo_final_real_efectivo)
                              : '—'
                          }
                          banco={
                            t.saldo_final_real_banco != null
                              ? moneda.format(t.saldo_final_real_banco)
                              : '—'
                          }
                        />
                      </td>
                      <td data-label="Diferencia" className="derecha">
                        <Cifras
                          efectivo={moneda.format(t.diferencia_efectivo ?? 0)}
                          banco={moneda.format(t.diferencia_banco ?? 0)}
                        />
                      </td>
                      <td className="celda-accion">
                        <button
                          type="button"
                          className="boton boton--mini"
                          onClick={() => setSeleccion(activo ? null : t)}
                        >
                          {activo ? 'Ocultar' : 'Ver movimientos'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <Paginacion
          total={datos?.total ?? 0}
          skip={skip}
          limit={tamano}
          onCambiar={setSkip}
          cargando={cargando}
        />

        {seleccion && (
          <div className="detalle-turno">
            <h3>Movimientos del turno #{seleccion.id}</h3>
            {cargandoMovs ? (
              <p className="ayuda">Cargando movimientos…</p>
            ) : movs.length === 0 ? (
              <p className="ayuda">Este turno no tiene movimientos registrados.</p>
            ) : (
              <>
                <div className="barra">
                  <label className="campo-fecha">
                    <span>Categoría</span>
                    <select
                      value={categoriaHistorial}
                      onChange={(e) => setCategoriaHistorial(e.target.value)}
                    >
                      <option value="Todas">Todas</option>
                      {categoriasHistorial.map((categoria) => (
                        <option key={categoria} value={categoria}>
                          {categoria}
                        </option>
                      ))}
                    </select>
                  </label>
                  <span className="ayuda">
                    {movsOrdenados.items.length} de {movs.length} movimiento(s)
                  </span>
                </div>
                {movsOrdenados.items.length === 0 ? (
                  <p className="ayuda">No hay movimientos con esa categoría.</p>
                ) : (
                  <div className="tabla-wrap tabla-wrap--cards">
                    <table className="tabla tabla--cards">
                      <thead>
                        <tr>
                          <ThOrdenable campo="fecha" orden={movsOrdenados.orden} direccion={movsOrdenados.direccion} onOrdenar={movsOrdenados.alternar}>
                            Fecha
                          </ThOrdenable>
                          <ThOrdenable campo="tipo" orden={movsOrdenados.orden} direccion={movsOrdenados.direccion} onOrdenar={movsOrdenados.alternar}>
                            Tipo
                          </ThOrdenable>
                          <ThOrdenable campo="referencia" orden={movsOrdenados.orden} direccion={movsOrdenados.direccion} onOrdenar={movsOrdenados.alternar}>
                            Referencia
                          </ThOrdenable>
                          <ThOrdenable campo="categoria" orden={movsOrdenados.orden} direccion={movsOrdenados.direccion} onOrdenar={movsOrdenados.alternar}>
                            Categoría
                          </ThOrdenable>
                          <ThOrdenable campo="forma_pago" orden={movsOrdenados.orden} direccion={movsOrdenados.direccion} onOrdenar={movsOrdenados.alternar}>
                            Forma de pago
                          </ThOrdenable>
                          <ThOrdenable
                            campo="monto"
                            orden={movsOrdenados.orden}
                            direccion={movsOrdenados.direccion}
                            onOrdenar={movsOrdenados.alternar}
                            className="derecha"
                          >
                            Monto
                          </ThOrdenable>
                        </tr>
                      </thead>
                      <tbody>
                        {movsOrdenados.items.map((m) => (
                          <tr key={m.id}>
                            <td data-label="Fecha">{formatoFecha(m.fecha)}</td>
                            <td data-label="Tipo">{m.tipo}</td>
                            <td data-label="Referencia">{m.referencia}</td>
                            <td data-label="Categoría">{m.categoria ?? '—'}</td>
                            <td data-label="Forma de pago">{m.forma_pago ?? '—'}</td>
                            <td data-label="Monto" className="derecha">
                              {moneda.format(m.monto)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  )
}
