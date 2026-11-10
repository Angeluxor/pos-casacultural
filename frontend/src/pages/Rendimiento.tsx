import { useCallback, useEffect, useState } from 'react'
import { obtenerResumenMetricas, type ResumenMetricas } from '../api/metricas'
import { AyudaContextual } from '../components/AyudaContextual'
import { formatoFecha } from '../lib/formato'

const VENTANAS = [
  { horas: 1, etiqueta: 'Última hora' },
  { horas: 24, etiqueta: 'Últimas 24 horas' },
  { horas: 168, etiqueta: 'Últimos 7 días' },
  { horas: 720, etiqueta: 'Últimos 30 días' },
]

function ms(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—'
  return valor >= 1000 ? `${(valor / 1000).toFixed(1)} s` : `${Math.round(valor)} ms`
}

function segundos(valor: number | null): string {
  if (valor === null) return '—'
  return valor >= 120 ? `${Math.round(valor / 60)} min` : `${Math.round(valor)} s`
}

export function Rendimiento() {
  const [horas, setHoras] = useState(24)
  const [datos, setDatos] = useState<ResumenMetricas | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  const cargar = useCallback(async () => {
    setCargando(true)
    setError('')
    try {
      setDatos(await obtenerResumenMetricas(horas))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron cargar las métricas')
    } finally {
      setCargando(false)
    }
  }, [horas])

  useEffect(() => {
    void cargar()
  }, [cargar])

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Rendimiento</h1>
          <p className="ayuda">
            {datos
              ? `Servidor activo desde ${formatoFecha(datos.proceso.proceso_desde)}` +
                (datos.proceso.arranque_ms !== null
                  ? ` · arranque ${ms(datos.proceso.arranque_ms)}`
                  : '')
              : 'Tiempos de respuesta de la aplicación'}
          </p>
        </div>
        <div className="acciones-fila">
          <label className="campo-fecha">
            Periodo
            <select value={horas} onChange={(e) => setHoras(Number(e.target.value))}>
              {VENTANAS.map((v) => (
                <option key={v.horas} value={v.horas}>
                  {v.etiqueta}
                </option>
              ))}
            </select>
          </label>
          <button className="boton boton--secundario" onClick={() => void cargar()}>
            Actualizar
          </button>
        </div>
      </header>

      <AyudaContextual
        titulo="Cómo leer estas métricas"
        detalle="p50 es el tiempo típico y p95 el de las peticiones más lentas (1 de cada 20). «Servidor» mide lo que tarda la API una vez despierta; «Navegador» mide lo que espera la persona, incluida su red y el arranque en frío del hosting. Si el navegador espera mucho más que el servidor, la demora está fuera del código."
      />

      {error && <p className="error">{error}</p>}
      {cargando && !datos && <p className="ayuda">Cargando…</p>}

      {datos && (
        <>
          <section>
            <h3>Diagnóstico</h3>
            <ul>
              {datos.diagnostico.map((nota) => (
                <li key={nota}>{nota}</li>
              ))}
            </ul>
          </section>

          <div className="resumen">
            <div className="resumen__item">
              <span className="ayuda">Servidor · peticiones</span>
              <strong>{datos.servidor.n}</strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Servidor · p50 / p95</span>
              <strong>
                {ms(datos.servidor.p50)} / {ms(datos.servidor.p95)}
              </strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Lentas (+2 s)</span>
              <strong>{datos.servidor.pct_lentas} %</strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Tiempo en base de datos</span>
              <strong>{datos.servidor.pct_db} %</strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Arranques / tras pausa</span>
              <strong>
                {datos.servidor.arranques_en_frio} / {datos.servidor.tras_inactividad}
              </strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Navegador · p50 / p95</span>
              <strong>
                {ms(datos.cliente.p50)} / {ms(datos.cliente.p95)}
              </strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Navegador · sin respuesta</span>
              <strong>
                {datos.cliente.fallidas} de {datos.cliente.n}
              </strong>
            </div>
            <div className="resumen__item">
              <span className="ayuda">Errores 5xx</span>
              <strong>{datos.servidor.errores_5xx}</strong>
            </div>
          </div>

          <h3>Rutas más lentas (por p95)</h3>
          {datos.rutas.length === 0 ? (
            <p className="ayuda">Sin datos en este periodo.</p>
          ) : (
            <div className="tabla-wrap">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Ruta</th>
                    <th className="derecha">Peticiones</th>
                    <th className="derecha">p50</th>
                    <th className="derecha">p95</th>
                    <th className="derecha">Máx.</th>
                    <th className="derecha">% en BD</th>
                    <th className="derecha">Consultas</th>
                    <th className="derecha">Navegador p95</th>
                    <th className="derecha">5xx</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.rutas.map((r) => (
                    <tr key={r.ruta}>
                      <td>{r.ruta}</td>
                      <td className="derecha">{r.n}</td>
                      <td className="derecha">{ms(r.p50)}</td>
                      <td className="derecha">{ms(r.p95)}</td>
                      <td className="derecha">{ms(r.max)}</td>
                      <td className="derecha">{r.pct_db} %</td>
                      <td className="derecha">{r.consultas_prom}</td>
                      <td className="derecha">{ms(r.cliente_p95)}</td>
                      <td className="derecha">{r.errores_5xx}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h3>Peticiones lentas recientes</h3>
          {datos.lentas.length === 0 ? (
            <p className="ayuda">No hubo peticiones de 2 s o más en este periodo.</p>
          ) : (
            <div className="tabla-wrap">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Cuándo</th>
                    <th>Petición</th>
                    <th className="derecha">Total</th>
                    <th className="derecha">En BD</th>
                    <th className="derecha">Consultas</th>
                    <th className="derecha">Conex. nuevas</th>
                    <th className="derecha">Inactivo antes</th>
                    <th>Primera tras arranque</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.lentas.map((l, i) => (
                    <tr key={`${l.creado_en}-${i}`}>
                      <td>{formatoFecha(l.creado_en)}</td>
                      <td>
                        {l.metodo} {l.ruta} ({l.estado})
                      </td>
                      <td className="derecha">{ms(l.ms_total)}</td>
                      <td className="derecha">{ms(l.ms_db)}</td>
                      <td className="derecha">{l.consultas}</td>
                      <td className="derecha">{l.conexiones_nuevas}</td>
                      <td className="derecha">{segundos(l.inactivo_s)}</td>
                      <td>{l.primera_tras_arranque ? 'Sí' : 'No'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h3>Por hora (servidor)</h3>
          {datos.por_hora.length === 0 ? (
            <p className="ayuda">Sin datos en este periodo.</p>
          ) : (
            <div className="tabla-wrap">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Hora</th>
                    <th className="derecha">Peticiones</th>
                    <th className="derecha">p50</th>
                    <th className="derecha">p95</th>
                  </tr>
                </thead>
                <tbody>
                  {[...datos.por_hora].reverse().map((h) => (
                    <tr key={h.hora}>
                      <td>{h.hora}</td>
                      <td className="derecha">{h.n}</td>
                      <td className="derecha">{ms(h.p50)}</td>
                      <td className="derecha">{ms(h.p95)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
