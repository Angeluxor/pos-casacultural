import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  archivarBolsillo,
  crearBolsillo,
  descargarBalance,
  historialBolsillo,
  obtenerBalance,
  registrarMovimientoBolsillo,
  type BalanceGeneral,
  type BolsilloBalance,
  type BolsilloMovimiento,
  type CuentaPorPagar,
  type FilaInventarioBalance,
} from '../api/balance'
import { useAuth } from '../auth/useAuth'
import { formatoFecha, moneda } from '../lib/formato'
import { confirmarCierre } from '../lib/modal'

const CLASE_INGRESO: Record<string, string> = {
  Completo: 'badge badge--on',
  Parcial: 'badge badge--warn',
  Inconsistente: 'badge badge--off',
}

const CLASE_ORIGEN: Record<string, string> = {
  'Costo promedio': 'badge badge--on',
  'Costo manual': 'badge badge--on',
  Receta: 'badge badge--info',
  'Precio de venta': 'badge badge--warn',
}

function isoLocal(fecha: Date): string {
  const y = fecha.getFullYear()
  const m = String(fecha.getMonth() + 1).padStart(2, '0')
  const d = String(fecha.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function mesActual(): { desde: string; hasta: string } {
  const ahora = new Date()
  const hasta = isoLocal(ahora)
  return { desde: `${hasta.slice(0, 8)}01`, hasta }
}

function Tarjetas({
  items,
}: {
  items: { label: string; valor: string; nota?: string }[]
}) {
  return (
    <div className="tarjetas">
      {items.map((item) => (
        <div className="mini-tarjeta" key={item.label}>
          <span className="mini-tarjeta__label">{item.label}</span>
          <strong>{item.valor}</strong>
          {item.nota && <small>{item.nota}</small>}
        </div>
      ))}
    </div>
  )
}

function TablaCuentas({
  cuentas,
  puedePagar,
}: {
  cuentas: CuentaPorPagar[]
  puedePagar: boolean
}) {
  if (cuentas.length === 0) {
    return <p className="ayuda">No hay compras a crédito pendientes de pago.</p>
  }
  return (
    <div className="tabla-wrap tabla-wrap--cards">
      <table className="tabla tabla--cards">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Proveedor</th>
            <th className="derecha">Total</th>
            <th>Ingreso</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {cuentas.map((c) => (
            <tr key={c.ingreso_id}>
              <td data-label="Fecha">{formatoFecha(c.fecha)}</td>
              <td data-label="Proveedor">{c.proveedor ?? '—'}</td>
              <td data-label="Total" className="derecha">
                {moneda.format(c.total)}
              </td>
              <td data-label="Ingreso">
                <span className={CLASE_INGRESO[c.estado_ingreso] ?? 'badge'}>
                  #{c.ingreso_id} · {c.estado_ingreso}
                </span>
              </td>
              <td className="celda-accion">
                {puedePagar ? (
                  <Link
                    className="boton boton--mini"
                    to={`/ingresos?pagar=${c.ingreso_id}`}
                    title="Abrir el ingreso para registrar el pago"
                  >
                    Pagar
                  </Link>
                ) : (
                  <span className="ayuda">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TablaInventario({ items }: { items: FilaInventarioBalance[] }) {
  if (items.length === 0) {
    return <p className="ayuda">No hay productos con stock para valorizar.</p>
  }
  return (
    <div className="tabla-wrap tabla-wrap--cards">
      <table className="tabla tabla--cards">
        <thead>
          <tr>
            <th>Código</th>
            <th>Producto</th>
            <th className="derecha">Stock</th>
            <th className="derecha">Costo unitario</th>
            <th className="derecha">Valor</th>
            <th>Origen del costo</th>
          </tr>
        </thead>
        <tbody>
          {items.map((i) => (
            <tr key={i.producto_id}>
              <td data-label="Código">{i.codigo}</td>
              <td data-label="Producto">{i.nombre}</td>
              <td data-label="Stock" className="derecha">
                {i.stock}
              </td>
              <td data-label="Costo unitario" className="derecha">
                {moneda.format(i.costo_unitario)}
              </td>
              <td data-label="Valor" className="derecha">
                {moneda.format(i.valor)}
              </td>
              <td data-label="Origen del costo">
                <span className={CLASE_ORIGEN[i.origen] ?? 'badge'}>{i.origen}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TablaBolsillos({
  bolsillos,
  disponible,
  puedeGestionar,
  onAportar,
  onLiberar,
  onHistorial,
  onArchivar,
}: {
  bolsillos: BolsilloBalance[]
  disponible: number
  puedeGestionar: boolean
  onAportar: (bolsillo: BolsilloBalance) => void
  onLiberar: (bolsillo: BolsilloBalance) => void
  onHistorial: (bolsillo: BolsilloBalance) => void
  onArchivar: (bolsillo: BolsilloBalance) => void
}) {
  if (bolsillos.length === 0) {
    return (
      <p className="ayuda">
        Todavía no hay bolsillos.{' '}
        {puedeGestionar
          ? 'Crea uno para apartar dinero de gastos vitales como el arriendo.'
          : 'Cuando se cree uno, aparecerá aquí.'}
      </p>
    )
  }

  return (
    <div className="tabla-wrap tabla-wrap--cards">
      <table className="tabla tabla--cards">
        <thead>
          <tr>
            <th>Bolsillo</th>
            <th>Descripción</th>
            <th className="derecha">Reservado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {bolsillos.map((b) => (
            <tr key={b.id}>
              <td data-label="Bolsillo">
                <strong>{b.nombre}</strong>
              </td>
              <td data-label="Descripción">{b.descripcion ?? '—'}</td>
              <td data-label="Reservado" className="derecha">
                {moneda.format(b.reservado)}
              </td>
              <td className="celda-accion">
                <div className="acciones-fila">
                  {puedeGestionar && (
                    <>
                      <button
                        type="button"
                        className="boton boton--mini"
                        onClick={() => onAportar(b)}
                        disabled={disponible <= 0}
                        title={
                          disponible <= 0
                            ? 'No hay efectivo/banco disponible para apartar'
                            : 'Apartar dinero del disponible'
                        }
                      >
                        Aportar
                      </button>
                      <button
                        type="button"
                        className="boton boton--mini boton--secundario"
                        onClick={() => onLiberar(b)}
                        disabled={b.reservado <= 0}
                        title={
                          b.reservado <= 0
                            ? 'El bolsillo no tiene saldo reservado'
                            : 'Devolver dinero a la liquidez disponible'
                        }
                      >
                        Liberar
                      </button>
                    </>
                  )}
                  <button
                    type="button"
                    className="boton boton--mini boton--secundario"
                    onClick={() => onHistorial(b)}
                  >
                    Historial
                  </button>
                  {puedeGestionar && (
                    <button
                      type="button"
                      className="boton boton--mini boton--danger"
                      onClick={() => onArchivar(b)}
                      disabled={Math.abs(b.reservado) > 0.005}
                      title={
                        Math.abs(b.reservado) > 0.005
                          ? 'Libera el saldo antes de archivar el bolsillo'
                          : 'Archivar el bolsillo (conserva el historial)'
                      }
                    >
                      Archivar
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function FormBolsillo({
  onCerrar,
  onGuardado,
}: {
  onCerrar: () => void
  onGuardado: () => void
}) {
  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (!nombre.trim()) {
      setError('El nombre del bolsillo es obligatorio')
      return
    }
    setGuardando(true)
    try {
      await crearBolsillo({
        nombre: nombre.trim(),
        descripcion: descripcion.trim() || undefined,
      })
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo crear el bolsillo')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>Nuevo bolsillo</h2>
        <p className="ayuda">
          Un bolsillo aparta una parte del efectivo/banco para un gasto vital. El dinero
          sigue en la caja: solo deja de contar como disponible.
        </p>
        {error && <p className="error">{error}</p>}
        <label>
          Nombre
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="Ej.: Arriendo"
            maxLength={80}
            autoFocus
          />
        </label>
        <label>
          Descripción (opcional)
          <input
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
            placeholder="Ej.: Reserva para el arriendo de cada mes"
            maxLength={300}
          />
        </label>
        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button type="submit" className="boton" disabled={guardando}>
            {guardando ? 'Creando…' : 'Crear bolsillo'}
          </button>
        </div>
      </form>
    </div>
  )
}

function FormMovimientoBolsillo({
  bolsillo,
  tipo,
  disponible,
  onCerrar,
  onGuardado,
}: {
  bolsillo: BolsilloBalance
  tipo: 'Aporte' | 'Retiro'
  disponible: number
  onCerrar: () => void
  onGuardado: () => void
}) {
  const [monto, setMonto] = useState('')
  const [nota, setNota] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  const limite = tipo === 'Aporte' ? Math.max(disponible, 0) : bolsillo.reservado
  const esAporte = tipo === 'Aporte'

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const valor = Number(monto)
    if (!valor || valor <= 0) {
      setError('El monto debe ser mayor a 0')
      return
    }
    if (valor > limite) {
      setError(
        esAporte
          ? `Solo puedes apartar hasta ${moneda.format(limite)}`
          : `Solo puedes liberar hasta ${moneda.format(limite)}`,
      )
      return
    }
    setGuardando(true)
    try {
      await registrarMovimientoBolsillo(bolsillo.id, {
        tipo,
        monto: valor,
        nota: nota.trim() || undefined,
      })
      onGuardado()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'No se pudo registrar el movimiento',
      )
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>
          {esAporte ? 'Aportar a' : 'Liberar de'} «{bolsillo.nombre}»
        </h2>
        <p className="ayuda">
          {esAporte
            ? `Disponible para apartar: ${moneda.format(limite)}.`
            : `Reservado en el bolsillo: ${moneda.format(limite)}.`}
        </p>
        {error && <p className="error">{error}</p>}
        <label>
          Monto
          <input
            type="number"
            min="0.01"
            max={limite}
            step="0.01"
            value={monto}
            onChange={(e) => setMonto(e.target.value)}
            autoFocus
          />
        </label>
        <label>
          Nota (opcional)
          <input
            value={nota}
            onChange={(e) => setNota(e.target.value)}
            placeholder={
              esAporte ? 'Ej.: Aparto para el arriendo de noviembre' : 'Ej.: Pago del arriendo'
            }
            maxLength={300}
          />
        </label>
        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button type="submit" className="boton" disabled={guardando}>
            {guardando ? 'Guardando…' : esAporte ? 'Apartar' : 'Liberar'}
          </button>
        </div>
      </form>
    </div>
  )
}

function HistorialBolsillo({
  bolsillo,
  onCerrar,
}: {
  bolsillo: BolsilloBalance
  onCerrar: () => void
}) {
  const [movs, setMovs] = useState<BolsilloMovimiento[]>([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let activo = true
    setCargando(true)
    historialBolsillo(bolsillo.id)
      .then((m) => {
        if (activo) setMovs(m)
      })
      .catch((err) => {
        if (activo) {
          setError(
            err instanceof Error ? err.message : 'No se pudo cargar el historial',
          )
        }
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    return () => {
      activo = false
    }
  }, [bolsillo.id])

  return (
    <div className="modal-overlay" onClick={onCerrar}>
      <div className="modal modal--ancho" onClick={(e) => e.stopPropagation()}>
        <h2>Historial de «{bolsillo.nombre}»</h2>
        {error && <p className="error">{error}</p>}
        {cargando ? (
          <p className="ayuda">Cargando…</p>
        ) : movs.length === 0 ? (
          <p className="ayuda">Este bolsillo todavía no tiene movimientos.</p>
        ) : (
          <div className="tabla-wrap tabla-wrap--cards">
            <table className="tabla tabla--cards">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Tipo</th>
                  <th className="derecha">Monto</th>
                  <th>Nota</th>
                  <th>Usuario</th>
                </tr>
              </thead>
              <tbody>
                {movs.map((m) => (
                  <tr key={m.id}>
                    <td data-label="Fecha">{formatoFecha(m.fecha)}</td>
                    <td data-label="Tipo">
                      <span
                        className={
                          m.tipo === 'Aporte' ? 'badge badge--on' : 'badge badge--off'
                        }
                      >
                        {m.tipo}
                      </span>
                    </td>
                    <td data-label="Monto" className="derecha">
                      {moneda.format(m.monto)}
                    </td>
                    <td data-label="Nota">{m.nota ?? '—'}</td>
                    <td data-label="Usuario">{m.usuario_nombre ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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

export function Balance() {
  const { tienePermiso } = useAuth()
  const puedePagar = tienePermiso('ingresos.ver') && tienePermiso('ingresos.pagar')
  const puedeGestionar = tienePermiso('balance.editar')

  const [filtro, setFiltro] = useState(mesActual)
  const [desde, setDesde] = useState(filtro.desde)
  const [hasta, setHasta] = useState(filtro.hasta)
  const [datos, setDatos] = useState<BalanceGeneral | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [errorExport, setErrorExport] = useState('')
  const [errorAccion, setErrorAccion] = useState('')
  const [exportando, setExportando] = useState<'excel' | 'pdf' | null>(null)
  const [tick, setTick] = useState(0)
  const [nuevoBolsillo, setNuevoBolsillo] = useState(false)
  const [movimientoBolsillo, setMovimientoBolsillo] = useState<{
    bolsillo: BolsilloBalance
    tipo: 'Aporte' | 'Retiro'
  } | null>(null)
  const [historial, setHistorial] = useState<BolsilloBalance | null>(null)

  const cargar = useCallback(async (activo: () => boolean) => {
    setCargando(true)
    setError('')
    try {
      const data = await obtenerBalance(filtro.desde, filtro.hasta)
      if (activo()) setDatos(data)
    } catch (err) {
      if (activo()) setError(err instanceof Error ? err.message : 'Error al cargar el balance')
    } finally {
      if (activo()) setCargando(false)
    }
  }, [filtro])

  useEffect(() => {
    let vivo = true
    void cargar(() => vivo)
    return () => {
      vivo = false
    }
  }, [cargar, tick])

  function consultar() {
    if (filtro.desde === desde && filtro.hasta === hasta) {
      setTick((t) => t + 1)
    } else {
      setFiltro({ desde, hasta })
    }
  }

  async function exportar(formato: 'excel' | 'pdf') {
    setErrorExport('')
    setExportando(formato)
    try {
      await descargarBalance(formato, filtro.desde, filtro.hasta)
    } catch (err) {
      setErrorExport(err instanceof Error ? err.message : 'No se pudo exportar el balance')
    } finally {
      setExportando(null)
    }
  }

  async function archivar(bolsillo: BolsilloBalance) {
    if (
      !window.confirm(
        `¿Archivar el bolsillo «${bolsillo.nombre}»? El historial de movimientos se conserva.`,
      )
    ) {
      return
    }
    setErrorAccion('')
    try {
      await archivarBolsillo(bolsillo.id)
      setTick((t) => t + 1)
    } catch (err) {
      setErrorAccion(
        err instanceof Error ? err.message : 'No se pudo archivar el bolsillo',
      )
    }
  }

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Balance general</h1>
          <p className="ayuda">
            {datos
              ? `Corte al ${formatoFecha(datos.fecha_corte)} · Patrimonio calculado como activos menos pasivos.`
              : 'Corte actual del negocio y resultados del período.'}
          </p>
        </div>
        <div className="acciones-fila">
          <button
            className="boton boton--secundario"
            onClick={() => setTick((t) => t + 1)}
            disabled={cargando}
          >
            Actualizar
          </button>
          <button
            className="boton boton--secundario"
            onClick={() => void exportar('excel')}
            disabled={!datos || exportando !== null}
          >
            {exportando === 'excel' ? 'Exportando…' : 'Exportar Excel'}
          </button>
          <button
            className="boton boton--secundario"
            onClick={() => void exportar('pdf')}
            disabled={!datos || exportando !== null}
          >
            {exportando === 'pdf' ? 'Exportando…' : 'Exportar PDF'}
          </button>
        </div>
      </header>

      <div className="barra">
        <label className="campo-fecha">
          <span>Resultados desde</span>
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
        <button className="boton" onClick={consultar} disabled={cargando}>
          Consultar
        </button>
      </div>
      <p className="ayuda">
        El balance de activos, pasivos y patrimonio es un corte al momento actual. Las fechas
        filtran únicamente el estado de resultados.
      </p>

      {error && <p className="error">{error}</p>}
      {errorExport && <p className="error">{errorExport}</p>}
      {errorAccion && <p className="error">{errorAccion}</p>}

      {cargando && !datos ? (
        <p className="ayuda">Cargando balance…</p>
      ) : datos ? (
        <>
          <section className="panel">
            <h3>Ecuación del balance</h3>
            <div className="balance-ecuacion">
              <div className="balance-ecuacion__bloque">
                <span>Activos</span>
                <strong>{moneda.format(datos.activos.total)}</strong>
              </div>
              <span className="balance-ecuacion__simbolo">=</span>
              <div className="balance-ecuacion__bloque">
                <span>Pasivos</span>
                <strong>{moneda.format(datos.pasivos.total)}</strong>
              </div>
              <span className="balance-ecuacion__simbolo">+</span>
              <div className="balance-ecuacion__bloque">
                <span>Patrimonio</span>
                <strong>{moneda.format(datos.patrimonio.total)}</strong>
              </div>
            </div>
            <p className="ayuda">
              Patrimonio residual: activos menos pasivos. El sistema no lleva aportes ni retiros
              de capital.
            </p>
          </section>

          <section>
            <h2>Activos</h2>
            <Tarjetas
              items={[
                {
                  label: 'Efectivo',
                  valor: moneda.format(datos.activos.efectivo),
                },
                {
                  label: 'Banco',
                  valor: moneda.format(datos.activos.banco),
                },
                {
                  label: 'Reservado en bolsillos',
                  valor: moneda.format(datos.activos.reservado),
                  nota: `${datos.bolsillos.length} bolsillo(s) · no disponible para operar`,
                },
                {
                  label: 'Disponible para operación',
                  valor: moneda.format(datos.activos.disponible),
                  nota: 'Efectivo + banco - reservado',
                },
                {
                  label: 'Inventario',
                  valor: moneda.format(datos.activos.inventario),
                  nota: `${datos.inventario.length} producto(s) con stock`,
                },
                {
                  label: 'Cartera por cobrar',
                  valor: moneda.format(datos.activos.cartera),
                  nota: 'Saldo de facturas no anuladas',
                },
              ]}
            />
          </section>

          <section className="panel">
            <div className="panel__head">
              <h3>Bolsillos de gastos vitales</h3>
              {puedeGestionar && (
                <button className="boton" onClick={() => setNuevoBolsillo(true)}>
                  + Nuevo bolsillo
                </button>
              )}
            </div>
            <p className="ayuda">
              Aparta una parte del efectivo o del banco para gastos vitales como el
              arriendo. El dinero sigue en la caja y en el patrimonio; solo deja de
              contar como disponible para la operación diaria.
            </p>
            {datos.activos.disponible < 0 && (
              <p className="error">
                El dinero apartado supera el efectivo y banco actuales. Libera un
                bolsillo o registra el ingreso que falta.
              </p>
            )}
            <TablaBolsillos
              bolsillos={datos.bolsillos}
              disponible={datos.activos.disponible}
              puedeGestionar={puedeGestionar}
              onAportar={(bolsillo) =>
                setMovimientoBolsillo({ bolsillo, tipo: 'Aporte' })
              }
              onLiberar={(bolsillo) =>
                setMovimientoBolsillo({ bolsillo, tipo: 'Retiro' })
              }
              onHistorial={(bolsillo) => setHistorial(bolsillo)}
              onArchivar={(bolsillo) => void archivar(bolsillo)}
            />
            <p className="ayuda">
              Para pagar un gasto vital, libera primero el valor del bolsillo y luego
              registra la salida real en Caja. Si no lo liberas, el bolsillo seguiría
              mostrando ese dinero como reservado.
            </p>
          </section>

          <section>
            <h2>Pasivos y patrimonio</h2>
            <Tarjetas
              items={[
                {
                  label: 'Cuentas por pagar',
                  valor: moneda.format(datos.pasivos.cuentas_por_pagar),
                  nota: `${datos.compras_credito_pendientes} compra(s) a crédito`,
                },
                { label: 'Total pasivos', valor: moneda.format(datos.pasivos.total) },
                {
                  label: 'Patrimonio',
                  valor: moneda.format(datos.patrimonio.total),
                  nota: 'Activos - pasivos',
                },
              ]}
            />
          </section>

          <section className="panel">
            <h3>Estado de resultados</h3>
            <p className="ayuda">
              Del {filtro.desde || 'inicio'} al {filtro.hasta || 'hoy'} · {datos.resultados.facturas}{' '}
              factura(s).
            </p>
            <Tarjetas
              items={[
                { label: 'Ventas netas', valor: moneda.format(datos.resultados.ventas_netas) },
                { label: 'Costo de ventas', valor: moneda.format(datos.resultados.costo_ventas) },
                { label: 'Utilidad bruta', valor: moneda.format(datos.resultados.utilidad_bruta) },
                {
                  label: 'Gastos',
                  valor: moneda.format(datos.resultados.gastos),
                  nota: `Caja ${moneda.format(datos.resultados.gastos_caja)} · Otros ${moneda.format(
                    datos.resultados.gastos_otros,
                  )}`,
                },
                { label: 'Utilidad del período', valor: moneda.format(datos.resultados.utilidad) },
                { label: 'Margen', valor: `${datos.resultados.margen.toFixed(2)}%` },
              ]}
            />
          </section>

          <section className="panel">
            <h3>Notas del cálculo</h3>
            <ul className="lista-simple">
              <li>
                <span>Caja y banco</span>
                <strong>{datos.caja.origen}</strong>
              </li>
              <li>
                <span>Bolsillos de gastos vitales</span>
                <strong>Apartan liquidez; no cambian activos ni resultados</strong>
              </li>
              <li>
                <span>Costo de ventas e inventario</span>
                <strong>Costo promedio de compras</strong>
              </li>
              {datos.productos_sin_costo > 0 && (
                <li>
                  <span>Productos sin costo</span>
                  <strong>
                    {datos.productos_sin_costo} valorizado(s) a precio de venta por{' '}
                    {moneda.format(datos.valor_inventario_precio_venta)}
                  </strong>
                </li>
              )}
              {datos.resultados.productos_vendidos_sin_costo > 0 && (
                <li>
                  <span>Ventas con costo incompleto</span>
                  <strong>
                    {datos.resultados.productos_vendidos_sin_costo} producto(s) usaron precio de
                    venta como costo
                  </strong>
                </li>
              )}
              {datos.compras_credito_pendientes > 0 && (
                <li>
                  <span>Cuentas por pagar</span>
                  <strong>
                    {datos.compras_credito_pendientes} compra(s) a crédito pendiente(s)
                  </strong>
                </li>
              )}
              <li>
                <span>Ingresos en balance general</span>
                <strong>No mueven caja; crédito queda como cuenta por pagar</strong>
              </li>
            </ul>
            <p className="ayuda">
              Los gastos incluyen salidas de caja que no corresponden a compras de inventario,
              pagos de esas compras ni devoluciones por anulación, más los ítems «Otros» de los
              ingresos (también los de balance general). El resultado del período es independiente
              del patrimonio residual.
            </p>
            <p className="ayuda">
              Los ingresos registrados con fuente «Balance general» no exigen caja abierta ni
              generan movimientos. Si son en efectivo o transferencia se consideran pagados por
              fuera del POS; si son a crédito, quedan como cuenta por pagar hasta que se paguen.
            </p>
            <p className="ayuda">
              Los bolsillos no son una salida de caja: el dinero sigue en efectivo/banco y en el
              total de activos, pero se resta del disponible para operar. Para pagar un gasto
              vital, libera primero el bolsillo y registra la salida real en Caja.
            </p>
          </section>

          <section className="panel">
            <h3>Cuentas por pagar</h3>
            <TablaCuentas cuentas={datos.cuentas_por_pagar} puedePagar={puedePagar} />
            {datos.cuentas_por_pagar.length > 0 && (
              <p className="ayuda">
                El pago se registra en Ingresos y descuenta el total de la caja abierta.
              </p>
            )}
          </section>

          <section className="panel">
            <h3>Detalle del inventario</h3>
            <TablaInventario items={datos.inventario} />
          </section>
        </>
      ) : null}

      {nuevoBolsillo && (
        <FormBolsillo
          onCerrar={() => setNuevoBolsillo(false)}
          onGuardado={() => {
            setNuevoBolsillo(false)
            setErrorAccion('')
            setTick((t) => t + 1)
          }}
        />
      )}

      {movimientoBolsillo && datos && (
        <FormMovimientoBolsillo
          bolsillo={movimientoBolsillo.bolsillo}
          tipo={movimientoBolsillo.tipo}
          disponible={datos.activos.disponible}
          onCerrar={() => setMovimientoBolsillo(null)}
          onGuardado={() => {
            setMovimientoBolsillo(null)
            setErrorAccion('')
            setTick((t) => t + 1)
          }}
        />
      )}

      {historial && (
        <HistorialBolsillo
          bolsillo={historial}
          onCerrar={() => setHistorial(null)}
        />
      )}
    </div>
  )
}
