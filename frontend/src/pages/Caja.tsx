import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  abrirCaja,
  cerrarCaja,
  listarTurnos,
  obtenerCajaActiva,
  obtenerMovimientos,
  registrarMovimiento,
  type RegistroCaja,
  type TurnoCaja,
  type TurnoCajaHistorial,
} from '../api/caja'
import type { FormaPago } from '../api/types'
import { formatoFecha, moneda } from '../lib/formato'
import { confirmarCierre } from '../lib/modal'
import { Paginacion } from '../components/Paginacion'
import { usePaginacion } from '../lib/usePaginacion'
import { Vacio } from '../components/Vacio'

const FORMAS_PAGO: FormaPago[] = ['Efectivo', 'Transferencia', 'Tarjeta', 'Otro']

export function Caja() {
  const [turno, setTurno] = useState<TurnoCaja | null>(null)
  const [movimientos, setMovimientos] = useState<RegistroCaja[]>([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [abrirModal, setAbrirModal] = useState(false)
  const [movModal, setMovModal] = useState(false)
  const [cerrarModal, setCerrarModal] = useState(false)
  const [histModal, setHistModal] = useState(false)

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

  const { entradas, salidas, esperado } = useMemo(() => {
    const ent = movimientos
      .filter((m) => m.tipo === 'Entrada')
      .reduce((acc, m) => acc + m.monto, 0)
    const sal = movimientos
      .filter((m) => m.tipo === 'Salida')
      .reduce((acc, m) => acc + m.monto, 0)
    const inicial = turno?.saldo_inicial ?? 0
    return { entradas: ent, salidas: sal, esperado: inicial + ent - sal }
  }, [movimientos, turno])

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
              <button className="boton boton--secundario" onClick={() => setMovModal(true)}>
                Registrar movimiento
              </button>
              <button className="boton boton--danger" onClick={() => setCerrarModal(true)}>
                Cerrar caja
              </button>
            </>
          ) : (
            <button className="boton" onClick={() => setAbrirModal(true)}>
              Abrir caja
            </button>
          )}
        </div>
      </header>

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
              <span className="ayuda">Saldo inicial</span>
              <strong>{moneda.format(turno.saldo_inicial)}</strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Entradas</span>
              <strong>{moneda.format(entradas)}</strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Salidas</span>
              <strong>{moneda.format(salidas)}</strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Esperado en caja</span>
              <strong>{moneda.format(esperado)}</strong>
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
            <div className="tabla-wrap tabla-wrap--cards">
              <table className="tabla tabla--cards">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Tipo</th>
                    <th>Referencia</th>
                    <th>Forma de pago</th>
                    <th className="derecha">Monto</th>
                  </tr>
                </thead>
                <tbody>
                  {movimientos.map((m) => (
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
          esperado={esperado}
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
  const [saldo, setSaldo] = useState('0')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const valor = Number(saldo)
    if (Number.isNaN(valor) || valor < 0) {
      setError('El saldo inicial no puede ser negativo')
      return
    }
    setGuardando(true)
    try {
      await abrirCaja(valor)
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
        <label>
          Saldo inicial
          <input
            type="number"
            min="0"
            step="0.01"
            value={saldo}
            onChange={(e) => setSaldo(e.target.value)}
          />
        </label>
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
  const [referencia, setReferencia] = useState('')
  const [monto, setMonto] = useState('')
  const [formaPago, setFormaPago] = useState<FormaPago | ''>('')
  const [observacion, setObservacion] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const valor = Number(monto)
    if (!referencia.trim()) {
      setError('La referencia es obligatoria')
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
        forma_pago: formaPago || undefined,
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
        <label>
          Tipo
          <select value={tipo} onChange={(e) => setTipo(e.target.value as 'Entrada' | 'Salida')}>
            <option value="Entrada">Entrada</option>
            <option value="Salida">Salida</option>
          </select>
        </label>
        <label>
          Referencia
          <input value={referencia} onChange={(e) => setReferencia(e.target.value)} />
        </label>
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
            Forma de pago (opcional)
            <select value={formaPago} onChange={(e) => setFormaPago(e.target.value as FormaPago | '')}>
              <option value="">—</option>
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
  esperado,
  onCerrar,
  onGuardado,
}: {
  turno: TurnoCaja
  esperado: number
  onCerrar: () => void
  onGuardado: () => void
}) {
  const [saldoReal, setSaldoReal] = useState(String(esperado))
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  const real = Number(saldoReal)
  const diferencia = Number.isNaN(real) ? 0 : real - esperado

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (Number.isNaN(real) || real < 0) {
      setError('El saldo real no puede ser negativo')
      return
    }
    setGuardando(true)
    try {
      await cerrarCaja(turno.id, real)
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
            <span className="ayuda">Saldo inicial</span>
            <strong>{moneda.format(turno.saldo_inicial)}</strong>
          </div>
          <div className="resumen__item">
            <span className="ayuda">Esperado</span>
            <strong>{moneda.format(esperado)}</strong>
          </div>
          <div className="resumen__item">
            <span className="ayuda">Diferencia</span>
            <strong>{moneda.format(diferencia)}</strong>
          </div>
        </div>
        <label>
          Saldo real contado
          <input
            type="number"
            min="0"
            step="0.01"
            value={saldoReal}
            onChange={(e) => setSaldoReal(e.target.value)}
          />
        </label>
        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button type="submit" className="boton boton--danger" disabled={guardando}>
            {guardando ? 'Cerrando…' : 'Cerrar caja'}
          </button>
        </div>
      </form>
    </div>
  )
}

function HistorialTurnos({ onCerrar }: { onCerrar: () => void }) {
  const cargar = useCallback(
    (params: { skip: number; limit: number; desde?: string; hasta?: string }) =>
      listarTurnos({
        skip: params.skip,
        limit: params.limit,
        desde: params.desde,
        hasta: params.hasta,
      }),
    [],
  )

  const { datos, skip, setSkip, desde, setDesde, hasta, setHasta, cargando, error, tamano } =
    usePaginacion(cargar)

  const [seleccion, setSeleccion] = useState<TurnoCajaHistorial | null>(null)
  const [movs, setMovs] = useState<RegistroCaja[]>([])
  const [cargandoMovs, setCargandoMovs] = useState(false)

  useEffect(() => {
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
                  <th>Turno</th>
                  <th>Apertura</th>
                  <th>Cierre</th>
                  <th>Abrió</th>
                  <th>Cerró</th>
                  <th className="derecha">Esperado</th>
                  <th className="derecha">Real</th>
                  <th className="derecha">Diferencia</th>
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
                        {moneda.format(t.esperado)}
                      </td>
                      <td data-label="Real" className="derecha">
                        {t.saldo_final_real != null ? moneda.format(t.saldo_final_real) : '—'}
                      </td>
                      <td data-label="Diferencia" className="derecha">
                        {t.diferencia != null ? (
                          <span
                            className={
                              t.diferencia === 0
                                ? 'diferencia diferencia--ok'
                                : 'diferencia diferencia--bad'
                            }
                          >
                            {moneda.format(t.diferencia)}
                          </span>
                        ) : (
                          '—'
                        )}
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
              <div className="tabla-wrap tabla-wrap--cards">
                <table className="tabla tabla--cards">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Tipo</th>
                      <th>Referencia</th>
                      <th>Forma de pago</th>
                      <th className="derecha">Monto</th>
                    </tr>
                  </thead>
                  <tbody>
                    {movs.map((m) => (
                      <tr key={m.id}>
                        <td data-label="Fecha">{formatoFecha(m.fecha)}</td>
                        <td data-label="Tipo">{m.tipo}</td>
                        <td data-label="Referencia">{m.referencia}</td>
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
