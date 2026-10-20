import { useCallback, useEffect, useState } from 'react'
import { obtenerDashboard, type DashboardResumen } from '../api/dashboard'
import { moneda } from '../lib/formato'
import { Vacio } from '../components/Vacio'
import { CollageHero } from '../components/Collage'
import { useAuth } from '../auth/useAuth'

const ORDEN_ESTADOS = ['Abierta', 'Pagado Parcial', 'Pagada', 'Crédito', 'Anulada']
const CLASE_ESTADO: Record<string, string> = {
  Abierta: 'badge badge--warn',
  'Pagado Parcial': 'badge badge--info',
  Pagada: 'badge badge--on',
  Crédito: 'badge badge--credito',
  Anulada: 'badge badge--off',
}

function etiquetaDia(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('es-CO', {
    weekday: 'short',
    day: 'numeric',
  })
}

function etiquetaMesCorta(mes: string): string {
  const [anio, numero] = mes.split('-').map(Number)
  return new Date(anio, numero - 1, 1).toLocaleDateString('es-CO', {
    month: 'short',
  })
}

function etiquetaMesLarga(mes: string): string {
  const [anio, numero] = mes.split('-').map(Number)
  return new Date(anio, numero - 1, 1).toLocaleDateString('es-CO', {
    month: 'long',
    year: 'numeric',
  })
}

export function Dashboard() {
  const { usuario } = useAuth()
  const [datos, setDatos] = useState<DashboardResumen | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [verTodoBajoStock, setVerTodoBajoStock] = useState(false)
  const [vistaVentas, setVistaVentas] = useState<'semanal' | 'mensual'>('semanal')

  const cargar = useCallback(async () => {
    setCargando(true)
    try {
      setDatos(await obtenerDashboard())
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar el dashboard')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    void cargar()
  }, [cargar])

  const maxDia = datos ? Math.max(...datos.ventas_ultimos_7_dias.map((d) => d.total), 1) : 1
  const maxMes = datos
    ? Math.max(...datos.ventas_ultimos_12_meses.map((m) => m.total), 1)
    : 1
  const total12m = datos
    ? datos.ventas_ultimos_12_meses.reduce((suma, m) => suma + m.total, 0)
    : 0
  const facturas12m = datos
    ? datos.ventas_ultimos_12_meses.reduce((suma, m) => suma + m.cantidad, 0)
    : 0

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Hola, {usuario?.nombre}</h1>
          <p className="ayuda">Resumen del punto de venta de Casi Obsceno.</p>
        </div>
        <div className="pagina__acciones">
          <CollageHero />
          <button className="boton boton--secundario" onClick={() => void cargar()}>
            Actualizar
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      {cargando ? (
        <p className="ayuda">Cargando…</p>
      ) : !datos ? (
        <Vacio titulo="Sin datos" detalle="No se pudo obtener el resumen." />
      ) : (
        <>
          <div className="tarjetas">
            <div className="mini-tarjeta">
              <span className="mini-tarjeta__label">Ventas de hoy</span>
              <strong>{moneda.format(datos.kpis.ventas_hoy_total)}</strong>
              <small>
                {datos.kpis.ventas_hoy_cantidad} factura
                {datos.kpis.ventas_hoy_cantidad === 1 ? '' : 's'}
              </small>
            </div>
            <div className="mini-tarjeta">
              <span className="mini-tarjeta__label">Últimos 7 días</span>
              <strong>{moneda.format(datos.kpis.ventas_7d_total)}</strong>
              <small>ventas acumuladas</small>
            </div>
            <div className="mini-tarjeta">
              <span className="mini-tarjeta__label">Ventas del mes</span>
              <strong>{moneda.format(datos.kpis.ventas_mes_total)}</strong>
              <small>
                {datos.kpis.ventas_mes_cantidad} factura
                {datos.kpis.ventas_mes_cantidad === 1 ? '' : 's'} este mes
              </small>
            </div>
            <div className="mini-tarjeta">
              <span className="mini-tarjeta__label">Cartera por cobrar</span>
              <strong>{moneda.format(datos.kpis.cartera_total)}</strong>
              <small>
                {datos.kpis.facturas_pendientes} factura
                {datos.kpis.facturas_pendientes === 1 ? '' : 's'} pendiente
                {datos.kpis.facturas_pendientes === 1 ? '' : 's'}
              </small>
            </div>
            <div className="mini-tarjeta">
              <span className="mini-tarjeta__label">Crédito</span>
              <strong>{datos.kpis.facturas_credito}</strong>
              <small>
                factura{datos.kpis.facturas_credito === 1 ? '' : 's'} a crédito
              </small>
            </div>
            <div className="mini-tarjeta">
              <span className="mini-tarjeta__label">Caja disponible</span>
              <strong
                className={
                  datos.caja.disponible < 0 ? 'mini-tarjeta__valor--alerta' : undefined
                }
              >
                {moneda.format(datos.caja.disponible)}
              </strong>
              <small>
                {datos.caja.abierta
                  ? `Turno #${datos.caja.turno_id}`
                  : datos.caja.turno_id
                    ? `Último cierre #${datos.caja.turno_id}`
                    : 'Sin turnos'}{' '}
                · Total{' '}
                {moneda.format(
                  datos.caja.esperado_efectivo + datos.caja.esperado_banco,
                )}
                {datos.caja.reservado > 0 &&
                  ` · Reservado ${moneda.format(datos.caja.reservado)}`}
              </small>
            </div>
          </div>

          <div className="dash-grid">
            <div className="dash-col">
              <section className="panel">
                <div className="panel__head">
                  <h3>Ventas</h3>
                  <div
                    className="fichas fichas--compactas"
                    role="group"
                    aria-label="Período de ventas"
                  >
                    <button
                      type="button"
                      className={
                        vistaVentas === 'semanal' ? 'ficha ficha--activa' : 'ficha'
                      }
                      aria-pressed={vistaVentas === 'semanal'}
                      onClick={() => setVistaVentas('semanal')}
                    >
                      7 días
                    </button>
                    <button
                      type="button"
                      className={
                        vistaVentas === 'mensual' ? 'ficha ficha--activa' : 'ficha'
                      }
                      aria-pressed={vistaVentas === 'mensual'}
                      onClick={() => setVistaVentas('mensual')}
                    >
                      12 meses
                    </button>
                  </div>
                </div>
                <p className="ayuda">
                  {vistaVentas === 'semanal'
                    ? 'Ventas de los últimos 7 días.'
                    : datos.ventas_ultimos_12_meses.length > 0
                      ? `Ventas de ${etiquetaMesLarga(
                          datos.ventas_ultimos_12_meses[0].mes,
                        )} a ${etiquetaMesLarga(
                          datos.ventas_ultimos_12_meses[
                            datos.ventas_ultimos_12_meses.length - 1
                          ].mes,
                        )}.`
                      : 'Ventas de los últimos 12 meses.'}
                </p>
                {vistaVentas === 'semanal' ? (
                  <div className="barras">
                    {datos.ventas_ultimos_7_dias.map((d) => (
                      <div
                        className="barra-col"
                        key={d.fecha}
                        title={`${etiquetaDia(d.fecha)}: ${moneda.format(d.total)} (${d.cantidad})`}
                      >
                        <span className="barra-valor">
                          {d.total > 0 ? moneda.format(d.total) : ''}
                        </span>
                        <div
                          className="barra-fill"
                          style={{ height: `${Math.max((d.total / maxDia) * 100, 2)}%` }}
                        />
                        <span className="barra-label">{etiquetaDia(d.fecha)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <>
                    <div className="barras barras--mes">
                      {datos.ventas_ultimos_12_meses.map((m) => (
                        <div
                          className="barra-col"
                          key={m.mes}
                          title={`${etiquetaMesLarga(m.mes)}: ${moneda.format(m.total)} (${m.cantidad})`}
                        >
                          <div
                            className="barra-fill"
                            style={{ height: `${Math.max((m.total / maxMes) * 100, 2)}%` }}
                          />
                          <span className="barra-label">{etiquetaMesCorta(m.mes)}</span>
                        </div>
                      ))}
                    </div>
                    <p className="ayuda">
                      Total 12 meses: {moneda.format(total12m)} · {facturas12m} factura
                      {facturas12m === 1 ? '' : 's'}.
                    </p>
                  </>
                )}
              </section>

              <section className="panel">
                <h3>Facturas por estado</h3>
                <ul className="lista-simple">
                  {ORDEN_ESTADOS.map((estado) => (
                    <li key={estado}>
                      <span className={CLASE_ESTADO[estado] ?? 'badge'}>{estado}</span>
                      <strong>{datos.facturas_por_estado[estado] ?? 0}</strong>
                    </li>
                  ))}
                </ul>
              </section>
            </div>

            <div className="dash-col">
              <section className="panel">
                <h3>Productos con bajo stock</h3>
                {datos.productos_bajo_stock.length === 0 ? (
                  <p className="ayuda">Todo el catálogo con stock suficiente.</p>
                ) : (
                  <>
                    <ul
                      className={
                        verTodoBajoStock
                          ? 'lista-simple lista-simple--scroll'
                          : 'lista-simple'
                      }
                    >
                      {(verTodoBajoStock
                        ? datos.productos_bajo_stock
                        : datos.productos_bajo_stock.slice(0, 6)
                      ).map((p) => (
                        <li key={p.id}>
                          <span>
                            {p.nombre}
                            <br />
                            <small className="ayuda">{p.codigo}</small>
                          </span>
                          <span
                            className={p.stock === 0 ? 'badge badge--off' : 'badge badge--warn'}
                          >
                            {p.stock}
                          </span>
                        </li>
                      ))}
                    </ul>
                    {datos.productos_bajo_stock.length > 6 && (
                      <button
                        type="button"
                        className="boton boton--secundario boton--mini enlace-ver-mas"
                        onClick={() => setVerTodoBajoStock((v) => !v)}
                      >
                        {verTodoBajoStock
                          ? 'Ver menos'
                          : `Ver todos (${datos.productos_bajo_stock.length})`}
                      </button>
                    )}
                  </>
                )}
              </section>

              <section className="panel">
                <h3>Resumen</h3>
                <ul className="lista-simple">
                  <li>
                    <span className="ayuda">Clientes</span>
                    <strong>{datos.total_clientes}</strong>
                  </li>
                  <li>
                    <span className="ayuda">Productos</span>
                    <strong>{datos.total_productos}</strong>
                  </li>
                  <li>
                    <span className="ayuda">Cartera</span>
                    <strong>{moneda.format(datos.kpis.cartera_total)}</strong>
                  </li>
                </ul>
              </section>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
