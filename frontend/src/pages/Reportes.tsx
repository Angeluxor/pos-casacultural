import { useEffect, useState } from 'react'
import { formatoFecha, moneda } from '../lib/formato'
import { Vacio } from '../components/Vacio'
import {
  consultarCaja,
  consultarCartera,
  consultarInventario,
  consultarTopProductos,
  consultarVentas,
  descargarReporte,
  type ReporteCaja,
  type ReporteCartera,
  type ReporteInventario,
  type ReporteTopProductos,
  type ReporteVentas,
  type TipoReporte,
} from '../api/reportes'

const TABS: { id: TipoReporte; label: string; conFechas: boolean }[] = [
  { id: 'ventas', label: 'Ventas', conFechas: true },
  { id: 'top-productos', label: 'Más vendidos', conFechas: true },
  { id: 'cartera', label: 'Cartera', conFechas: false },
  { id: 'caja', label: 'Cierres de caja', conFechas: true },
  { id: 'inventario', label: 'Inventario', conFechas: false },
]

function aIso(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

function par(efectivo: number, banco: number): string {
  return `Ef ${moneda.format(efectivo)} · Ban ${moneda.format(banco)}`
}

export function Reportes() {
  const [tipo, setTipo] = useState<TipoReporte>('ventas')
  const tab = TABS.find((t) => t.id === tipo) ?? TABS[0]
  const [desde, setDesde] = useState(() =>
    aIso(new Date(new Date().getFullYear(), new Date().getMonth(), 1)),
  )
  const [hasta, setHasta] = useState(() => aIso(new Date()))
  const [tick, setTick] = useState(0)

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Reportes</h1>
          <p className="ayuda">Consulta y exporta la información del negocio.</p>
        </div>
      </header>

      <div className="fichas" role="tablist" aria-label="Tipos de reporte">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={t.id === tipo}
            className={t.id === tipo ? 'ficha ficha--activa' : 'ficha'}
            onClick={() => setTipo(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="barra">
        {tab.conFechas && (
          <>
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
          </>
        )}
        <button className="boton" onClick={() => setTick((t) => t + 1)}>
          Consultar
        </button>
      </div>

      <ReporteVista
        key={`${tipo}|${desde}|${hasta}|${tick}`}
        tipo={tipo}
        conFechas={tab.conFechas}
        desde={desde}
        hasta={hasta}
      />
    </div>
  )
}

type VistaProps = { conFechas: boolean; desde: string; hasta: string }

function ReporteVista({ tipo, conFechas, desde, hasta }: VistaProps & { tipo: TipoReporte }) {
  switch (tipo) {
    case 'ventas':
      return <VentasReporte conFechas={conFechas} desde={desde} hasta={hasta} />
    case 'top-productos':
      return <TopReporte conFechas={conFechas} desde={desde} hasta={hasta} />
    case 'cartera':
      return <CarteraReporte />
    case 'caja':
      return <CajaReporte conFechas={conFechas} desde={desde} hasta={hasta} />
    case 'inventario':
      return <InventarioReporte />
  }
}

function useReporte<T>(consultar: () => Promise<T>) {
  const [datos, setDatos] = useState<T | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let activo = true
    setCargando(true)
    setError('')
    consultar()
      .then((d) => {
        if (activo) setDatos(d)
      })
      .catch((err) => {
        if (activo) setError(err instanceof Error ? err.message : 'Error al cargar el reporte')
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    return () => {
      activo = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { datos, cargando, error }
}

function BotonesExportar({
  tipo,
  conFechas,
  desde,
  hasta,
  disabled,
}: {
  tipo: TipoReporte
  conFechas: boolean
  desde?: string
  hasta?: string
  disabled: boolean
}) {
  const [exportando, setExportando] = useState<'excel' | 'pdf' | null>(null)
  const [falla, setFalla] = useState('')

  async function exportar(formato: 'excel' | 'pdf') {
    setExportando(formato)
    setFalla('')
    try {
      await descargarReporte(
        tipo,
        formato,
        conFechas ? desde : undefined,
        conFechas ? hasta : undefined,
      )
    } catch (err) {
      setFalla(err instanceof Error ? err.message : 'Error al exportar')
    } finally {
      setExportando(null)
    }
  }

  return (
    <div className="acciones-exportar" style={{ marginTop: 4 }}>
      <button
        type="button"
        className="boton boton--secundario"
        disabled={disabled || exportando !== null}
        onClick={() => void exportar('excel')}
      >
        {exportando === 'excel' ? 'Generando…' : 'Exportar Excel'}
      </button>
      <button
        type="button"
        className="boton boton--secundario"
        disabled={disabled || exportando !== null}
        onClick={() => void exportar('pdf')}
      >
        {exportando === 'pdf' ? 'Generando…' : 'Exportar PDF'}
      </button>
      {falla && <p className="error">{falla}</p>}
    </div>
  )
}

function Tarjetas({ items }: { items: { label: string; valor: string; nota?: string }[] }) {
  return (
    <div className="tarjetas">
      {items.map((i) => (
        <div className="mini-tarjeta" key={i.label}>
          <span className="mini-tarjeta__label">{i.label}</span>
          <strong>{i.valor}</strong>
          {i.nota && <small>{i.nota}</small>}
        </div>
      ))}
    </div>
  )
}

function Cuerpo({
  cargando,
  error,
  vacio,
  children,
}: {
  cargando: boolean
  error: string
  vacio: boolean
  children: React.ReactNode
}) {
  if (cargando) return <p className="ayuda">Cargando…</p>
  if (error) return <p className="error">{error}</p>
  if (vacio)
    return (
      <Vacio titulo="Sin datos" detalle="No hay registros para los filtros seleccionados." />
    )
  return <>{children}</>
}

function VentasReporte({ conFechas, desde, hasta }: VistaProps) {
  const { datos, cargando, error } = useReporte<ReporteVentas>(() =>
    consultarVentas(conFechas ? desde : undefined, conFechas ? hasta : undefined),
  )
  return (
    <>
      <BotonesExportar tipo="ventas" conFechas={conFechas} desde={desde} hasta={hasta} disabled={cargando} />
      <Cuerpo cargando={cargando} error={error} vacio={!datos || datos.detalle.length === 0}>
        {datos && (
          <>
            <Tarjetas
              items={[
                { label: 'Ventas (facturas)', valor: String(datos.facturas - datos.facturas_anuladas) },
                { label: 'Anuladas', valor: String(datos.facturas_anuladas) },
                { label: 'Total vendido', valor: moneda.format(datos.total_vendido) },
                { label: 'Neto', valor: moneda.format(datos.neto) },
              ]}
            />
            <div className="tabla-wrap">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th className="derecha">Facturas</th>
                    <th className="derecha">Anuladas</th>
                    <th className="derecha">Total</th>
                    <th className="derecha">Total anulado</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.por_dia.map((d) => (
                    <tr key={d.fecha}>
                      <td>{formatoFecha(d.fecha)}</td>
                      <td className="derecha">{d.facturas}</td>
                      <td className="derecha">{d.anuladas}</td>
                      <td className="derecha">{moneda.format(d.total)}</td>
                      <td className="derecha">{moneda.format(d.total_anulado)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Cuerpo>
    </>
  )
}

function TopReporte({ conFechas, desde, hasta }: VistaProps) {
  const { datos, cargando, error } = useReporte<ReporteTopProductos>(() =>
    consultarTopProductos(conFechas ? desde : undefined, conFechas ? hasta : undefined),
  )
  return (
    <>
      <BotonesExportar tipo="top-productos" conFechas={conFechas} desde={desde} hasta={hasta} disabled={cargando} />
      <Cuerpo cargando={cargando} error={error} vacio={!datos || datos.items.length === 0}>
        {datos && (
          <>
            <Tarjetas
              items={[
                { label: 'Productos', valor: String(datos.renglones) },
                { label: 'Unidades vendidas', valor: String(datos.cantidad_total) },
                { label: 'Total vendido', valor: moneda.format(datos.total_vendido) },
              ]}
            />
            <div className="tabla-wrap">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Código</th>
                    <th>Producto</th>
                    <th className="derecha">Cantidad</th>
                    <th className="derecha">Precio promedio</th>
                    <th className="derecha">Total vendido</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.items.map((i, pos) => (
                    <tr key={`${i.codigo}-${pos}`}>
                      <td>{i.codigo}</td>
                      <td>{i.nombre}</td>
                      <td className="derecha">{i.cantidad}</td>
                      <td className="derecha">{moneda.format(i.precio_promedio)}</td>
                      <td className="derecha">{moneda.format(i.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Cuerpo>
    </>
  )
}

function CarteraReporte() {
  const { datos, cargando, error } = useReporte<ReporteCartera>(consultarCartera)
  return (
    <>
      <BotonesExportar tipo="cartera" conFechas={false} disabled={cargando} />
      <Cuerpo cargando={cargando} error={error} vacio={!datos || datos.items.length === 0}>
        {datos && (
          <>
            <Tarjetas
              items={[
                { label: 'Clientes con saldo', valor: String(datos.clientes_con_saldo) },
                { label: 'Cartera total', valor: moneda.format(datos.total_cartera) },
              ]}
            />
            <div className="tabla-wrap">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Cliente</th>
                    <th>Documento</th>
                    <th className="derecha">Facturas</th>
                    <th className="derecha">Total</th>
                    <th className="derecha">Pagado</th>
                    <th className="derecha">Saldo</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.items.map((i) => (
                    <tr key={i.cliente_id}>
                      <td>{i.nombre}</td>
                      <td>{i.documento ?? '—'}</td>
                      <td className="derecha">{i.facturas}</td>
                      <td className="derecha">{moneda.format(i.total)}</td>
                      <td className="derecha">{moneda.format(i.pagado)}</td>
                      <td className="derecha">{moneda.format(i.saldo)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Cuerpo>
    </>
  )
}

function CajaReporte({ conFechas, desde, hasta }: VistaProps) {
  const { datos, cargando, error } = useReporte<ReporteCaja>(() =>
    consultarCaja(conFechas ? desde : undefined, conFechas ? hasta : undefined),
  )
  const difEfectivo = datos ? datos.diferencia_efectivo_total : 0
  const difBanco = datos ? datos.diferencia_banco_total : 0
  const cuadrada = difEfectivo === 0 && difBanco === 0
  return (
    <>
      <BotonesExportar tipo="caja" conFechas={conFechas} desde={desde} hasta={hasta} disabled={cargando} />
      <Cuerpo cargando={cargando} error={error} vacio={!datos || datos.items.length === 0}>
        {datos && (
          <>
            <Tarjetas
              items={[
                { label: 'Turnos cerrados', valor: String(datos.turnos) },
                {
                  label: 'Entradas (Ef · Ban)',
                  valor: par(datos.entradas_efectivo_total, datos.entradas_banco_total),
                },
                {
                  label: 'Salidas (Ef · Ban)',
                  valor: par(datos.salidas_efectivo_total, datos.salidas_banco_total),
                },
                {
                  label: 'Diferencia acumulada',
                  valor: par(difEfectivo, difBanco),
                  nota: cuadrada ? 'cuadrada' : 'revisar',
                },
              ]}
            />
            <FormaPagoLista items={datos.por_forma_pago} />
            <div className="tabla-wrap">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Turno</th>
                    <th>Apertura</th>
                    <th>Inicial (Ef · Ban)</th>
                    <th className="derecha">Entradas</th>
                    <th className="derecha">Salidas</th>
                    <th className="derecha">Esperado</th>
                    <th className="derecha">Real</th>
                    <th className="derecha">Diferencia</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.items.map((i) => {
                    const cuadradaFila =
                      (i.diferencia_efectivo ?? 0) === 0 && (i.diferencia_banco ?? 0) === 0
                    const hayReal = i.saldo_final_efectivo !== null || i.saldo_final_banco !== null
                    const hayDiferencia =
                      i.diferencia_efectivo !== null || i.diferencia_banco !== null
                    return (
                      <tr key={i.id}>
                        <td>#{i.id}</td>
                        <td>{formatoFecha(i.fecha_apertura)}</td>
                        <td>{par(i.saldo_inicial_efectivo, i.saldo_inicial_banco)}</td>
                        <td className="derecha">{par(i.entradas_efectivo, i.entradas_banco)}</td>
                        <td className="derecha">{par(i.salidas_efectivo, i.salidas_banco)}</td>
                        <td className="derecha">{par(i.esperado_efectivo, i.esperado_banco)}</td>
                        <td className="derecha">
                          {hayReal
                            ? par(i.saldo_final_efectivo ?? 0, i.saldo_final_banco ?? 0)
                            : '—'}
                        </td>
                        <td className="derecha">
                          {hayDiferencia ? (
                            <span
                              className={
                                cuadradaFila
                                  ? 'diferencia diferencia--ok'
                                  : 'diferencia diferencia--bad'
                              }
                            >
                              {par(i.diferencia_efectivo ?? 0, i.diferencia_banco ?? 0)}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Cuerpo>
    </>
  )
}

function InventarioReporte() {
  const { datos, cargando, error } = useReporte<ReporteInventario>(consultarInventario)
  return (
    <>
      <BotonesExportar tipo="inventario" conFechas={false} disabled={cargando} />
      <Cuerpo cargando={cargando} error={error} vacio={!datos || datos.items.length === 0}>
        {datos && (
          <>
            <Tarjetas
              items={[
                { label: 'Productos', valor: String(datos.productos) },
                { label: 'Unidades en inventario', valor: String(datos.unidades_totales) },
                { label: 'Valor del inventario', valor: moneda.format(datos.valor_inventario) },
              ]}
            />
            <div className="tabla-wrap">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Código</th>
                    <th>Producto</th>
                    <th className="derecha">Precio</th>
                    <th className="derecha">Stock</th>
                    <th className="derecha">Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.items.map((i) => (
                    <tr key={i.id}>
                      <td>{i.codigo}</td>
                      <td>{i.nombre}</td>
                      <td className="derecha">{moneda.format(i.precio)}</td>
                      <td className="derecha">{i.stock}</td>
                      <td className="derecha">{moneda.format(i.valor)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Cuerpo>
    </>
  )
}

function FormaPagoLista({ items }: { items: { forma_pago: string; monto: number }[] }) {
  if (items.length === 0) return null
  return (
    <section className="panel">
      <h3>Forma de pago</h3>
      <ul className="lista-simple">
        {items.map((f) => (
          <li key={f.forma_pago}>
            <span className="ayuda">{f.forma_pago}</span>
            <strong>{moneda.format(f.monto)}</strong>
          </li>
        ))}
      </ul>
    </section>
  )
}