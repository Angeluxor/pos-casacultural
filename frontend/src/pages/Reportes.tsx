import { useEffect, useState } from 'react'
import { formatoFecha, moneda } from '../lib/formato'
import { useAuth } from '../auth/useAuth'
import { ThOrdenable } from '../components/ThOrdenable'
import { useOrdenLocal, type Accesores } from '../lib/orden'
import { AyudaContextual } from '../components/AyudaContextual'
import { Vacio } from '../components/Vacio'
import {
  consultarCaja,
  consultarCartera,
  consultarInventario,
  consultarNomina,
  consultarTopProductos,
  consultarVentas,
  descargarReporte,
  type FilaCartera,
  type FilaCierreCaja,
  type FilaDescuentoNomina,
  type FilaInventario,
  type FilaTopProducto,
  type ReporteCaja,
  type ReporteCartera,
  type ReporteInventario,
  type ReporteNomina,
  type ReporteTopProductos,
  type ReporteVentas,
  type TipoReporte,
  type VentaPorDia,
} from '../api/reportes'

const ACC_VENTAS_DIA: Accesores<VentaPorDia> = {
  fecha: (d) => d.fecha,
  facturas: (d) => d.facturas,
  anuladas: (d) => d.anuladas,
  total: (d) => d.total,
  total_anulado: (d) => d.total_anulado,
}

const ACC_TOP_PRODUCTOS: Accesores<FilaTopProducto> = {
  codigo: (i) => i.codigo,
  nombre: (i) => i.nombre,
  cantidad: (i) => i.cantidad,
  precio_promedio: (i) => i.precio_promedio,
  total: (i) => i.total,
}

const ACC_CARTERA: Accesores<FilaCartera> = {
  nombre: (i) => i.nombre,
  documento: (i) => i.documento ?? '',
  facturas: (i) => i.facturas,
  total: (i) => i.total,
  pagado: (i) => i.pagado,
  saldo: (i) => i.saldo,
}

const ACC_CAJA: Accesores<FilaCierreCaja> = {
  id: (i) => i.id,
  apertura: (i) => i.fecha_apertura,
  cierre: (i) => i.fecha_cierre ?? '',
  // Las columnas de dinero muestran dos cifras (efectivo y banco): se ordena
  // por su suma.
  inicial: (i) => i.saldo_inicial_efectivo + i.saldo_inicial_banco,
  entradas: (i) => i.entradas_efectivo + i.entradas_banco,
  salidas: (i) => i.salidas_efectivo + i.salidas_banco,
  esperado: (i) => i.esperado_efectivo + i.esperado_banco,
  real: (i) => (i.saldo_final_efectivo ?? 0) + (i.saldo_final_banco ?? 0),
  diferencia: (i) => (i.diferencia_efectivo ?? 0) + (i.diferencia_banco ?? 0),
}

const ACC_INVENTARIO: Accesores<FilaInventario> = {
  codigo: (i) => i.codigo,
  nombre: (i) => i.nombre,
  precio: (i) => i.precio,
  stock: (i) => i.stock,
  valor: (i) => i.valor,
}

const ACC_NOMINA: Accesores<FilaDescuentoNomina> = {
  fecha: (i) => i.fecha,
  usuario_nombre: (i) => i.usuario_nombre,
  cliente_nombre: (i) => i.cliente_nombre,
  monto: (i) => i.monto,
  saldo_pendiente: (i) => i.saldo_pendiente,
  facturas_afectadas: (i) => i.facturas_afectadas,
  registrado_por: (i) => i.registrado_por,
  nota: (i) => i.nota ?? '',
}

const TABS: { id: TipoReporte; label: string; conFechas: boolean }[] = [
  { id: 'ventas', label: 'Ventas', conFechas: true },
  { id: 'top-productos', label: 'Más vendidos', conFechas: true },
  { id: 'cartera', label: 'Cartera', conFechas: false },
  { id: 'caja', label: 'Cierres de caja', conFechas: true },
  { id: 'inventario', label: 'Inventario', conFechas: false },
  { id: 'nomina', label: 'Nómina', conFechas: true },
]

const AYUDA_REPORTE: Record<
  TipoReporte,
  { titulo: string; detalle: string; pista: string }
> = {
  ventas: {
    titulo: 'Ventas por día',
    detalle:
      'Muestra facturado, anulado y neto por día calendario en hora de Colombia. Los totales cubren todo el filtro, no solo la página visible.',
    pista: 'Facturado, anulado y neto por día calendario',
  },
  'top-productos': {
    titulo: 'Productos más vendidos',
    detalle:
      'Ordena los productos por cantidad y valor vendido en el período. Sirve para decidir qué reabastecer y qué rotar.',
    pista: 'Productos con más salida por cantidad y valor',
  },
  cartera: {
    titulo: 'Cartera por cobrar',
    detalle:
      'Muestra el saldo pendiente por cliente. No usa fechas: es la deuda actual, incluidos abonos parciales y facturas a crédito.',
    pista: 'Saldo pendiente actual por cliente',
  },
  caja: {
    titulo: 'Cierres de caja',
    detalle:
      'Filtra por la fecha de apertura del turno y muestra el turno completo, aunque haya cerrado después de medianoche. Solo aparecen turnos cerrados.',
    pista: 'Cuadre de los turnos cerrados por fecha de apertura',
  },
  inventario: {
    titulo: 'Inventario valorizado',
    detalle:
      'Es una foto del stock actual valorizado al costo vigente. No usa fechas; cambia cuando cambian las compras, los costos o el stock.',
    pista: 'Stock actual y su valor al costo vigente',
  },
  nomina: {
    titulo: 'Descuentos de nómina',
    detalle:
      'Lista los abonos aplicados a facturas a crédito de empleados, con monto, saldo pendiente, facturas afectadas y quién los registró.',
    pista: 'Abonos a facturas de empleados descontados de nómina',
  },
}

function aIso(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

function par(efectivo: number, banco: number): string {
  return `Ef ${moneda.format(efectivo)} · Ban ${moneda.format(banco)}`
}

export function Reportes() {
  const { tienePermiso } = useAuth()
  // El reporte de nómina expone deuda y descuentos de empleados: exige el
  // permiso específico además del acceso a Reportes.
  const tabs = TABS.filter(
    (t) => t.id !== 'nomina' || tienePermiso('nomina.descontar'),
  )
  const [tipo, setTipo] = useState<TipoReporte>('ventas')
  const tab = tabs.find((t) => t.id === tipo) ?? tabs[0]
  // Si el permiso cambia y la pestaña activa deja de estar disponible, se
  // renderiza la primera pestaña visible.
  const tipoActivo = tab.id
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

      <div
        className="fichas"
        role="tablist"
        aria-label="Tipos de reporte"
        aria-describedby="ayuda-reporte"
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={t.id === tipoActivo}
            className={t.id === tipoActivo ? 'ficha ficha--activa' : 'ficha'}
            title={AYUDA_REPORTE[t.id].pista}
            onClick={() => setTipo(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <AyudaContextual
        id="ayuda-reporte"
        ariaLive
        titulo={AYUDA_REPORTE[tab.id].titulo}
        detalle={AYUDA_REPORTE[tab.id].detalle}
      />

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
        key={`${tipoActivo}|${desde}|${hasta}|${tick}`}
        tipo={tipoActivo}
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
    case 'nomina':
      return <NominaReporte conFechas={conFechas} desde={desde} hasta={hasta} />
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
  const { items: dias, orden, direccion, alternar } = useOrdenLocal(
    datos?.por_dia ?? [],
    ACC_VENTAS_DIA,
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
                    <ThOrdenable campo="fecha" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Fecha
                    </ThOrdenable>
                    <ThOrdenable campo="facturas" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Facturas
                    </ThOrdenable>
                    <ThOrdenable campo="anuladas" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Anuladas
                    </ThOrdenable>
                    <ThOrdenable campo="total" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Total
                    </ThOrdenable>
                    <ThOrdenable campo="total_anulado" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Total anulado
                    </ThOrdenable>
                  </tr>
                </thead>
                <tbody>
                  {dias.map((d) => (
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
  const { items: productos, orden, direccion, alternar } = useOrdenLocal(
    datos?.items ?? [],
    ACC_TOP_PRODUCTOS,
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
                    <ThOrdenable campo="codigo" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Código
                    </ThOrdenable>
                    <ThOrdenable campo="nombre" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Producto
                    </ThOrdenable>
                    <ThOrdenable campo="cantidad" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Cantidad
                    </ThOrdenable>
                    <ThOrdenable campo="precio_promedio" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Precio promedio
                    </ThOrdenable>
                    <ThOrdenable campo="total" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Total vendido
                    </ThOrdenable>
                  </tr>
                </thead>
                <tbody>
                  {productos.map((i, pos) => (
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
  const { items: clientes, orden, direccion, alternar } = useOrdenLocal(
    datos?.items ?? [],
    ACC_CARTERA,
  )
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
                    <ThOrdenable campo="nombre" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Cliente
                    </ThOrdenable>
                    <ThOrdenable campo="documento" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Documento
                    </ThOrdenable>
                    <ThOrdenable campo="facturas" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Facturas
                    </ThOrdenable>
                    <ThOrdenable campo="total" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Total
                    </ThOrdenable>
                    <ThOrdenable campo="pagado" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Pagado
                    </ThOrdenable>
                    <ThOrdenable campo="saldo" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Saldo
                    </ThOrdenable>
                  </tr>
                </thead>
                <tbody>
                  {clientes.map((i) => (
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
  const { items: turnos, orden, direccion, alternar } = useOrdenLocal(
    datos?.items ?? [],
    ACC_CAJA,
  )
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
                    <ThOrdenable campo="id" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Turno
                    </ThOrdenable>
                    <ThOrdenable campo="apertura" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Apertura
                    </ThOrdenable>
                    <ThOrdenable campo="inicial" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Inicial (Ef · Ban)
                    </ThOrdenable>
                    <ThOrdenable campo="entradas" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Entradas
                    </ThOrdenable>
                    <ThOrdenable campo="salidas" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Salidas
                    </ThOrdenable>
                    <ThOrdenable campo="esperado" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Esperado
                    </ThOrdenable>
                    <ThOrdenable campo="real" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Real
                    </ThOrdenable>
                    <ThOrdenable campo="diferencia" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Diferencia
                    </ThOrdenable>
                  </tr>
                </thead>
                <tbody>
                  {turnos.map((i) => {
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
  const { items: productos, orden, direccion, alternar } = useOrdenLocal(
    datos?.items ?? [],
    ACC_INVENTARIO,
  )
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
                    <ThOrdenable campo="codigo" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Código
                    </ThOrdenable>
                    <ThOrdenable campo="nombre" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Producto
                    </ThOrdenable>
                    <ThOrdenable campo="precio" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Precio
                    </ThOrdenable>
                    <ThOrdenable campo="stock" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Stock
                    </ThOrdenable>
                    <ThOrdenable campo="valor" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Valor
                    </ThOrdenable>
                  </tr>
                </thead>
                <tbody>
                  {productos.map((i) => (
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

function NominaReporte({ conFechas, desde, hasta }: VistaProps) {
  const { datos, cargando, error } = useReporte<ReporteNomina>(() =>
    consultarNomina(conFechas ? desde : undefined, conFechas ? hasta : undefined),
  )
  const { items, orden, direccion, alternar } = useOrdenLocal(
    datos?.items ?? [],
    ACC_NOMINA,
  )
  return (
    <>
      <BotonesExportar tipo="nomina" conFechas={conFechas} desde={desde} hasta={hasta} disabled={cargando} />
      <Cuerpo cargando={cargando} error={error} vacio={!datos || datos.items.length === 0}>
        {datos && (
          <>
            <Tarjetas
              items={[
                { label: 'Descuentos', valor: String(datos.descuentos) },
                { label: 'Monto descontado', valor: moneda.format(datos.monto_total) },
                {
                  label: 'Facturas afectadas',
                  valor: String(datos.facturas_afectadas_total),
                },
              ]}
            />
            <div className="tabla-wrap">
              <table className="tabla">
                <thead>
                  <tr>
                    <ThOrdenable campo="fecha" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Fecha
                    </ThOrdenable>
                    <ThOrdenable campo="usuario_nombre" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Empleado
                    </ThOrdenable>
                    <ThOrdenable campo="cliente_nombre" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Cliente
                    </ThOrdenable>
                    <ThOrdenable campo="monto" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Monto
                    </ThOrdenable>
                    <ThOrdenable campo="saldo_pendiente" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Saldo después
                    </ThOrdenable>
                    <ThOrdenable campo="facturas_afectadas" orden={orden} direccion={direccion} onOrdenar={alternar} className="derecha">
                      Facturas
                    </ThOrdenable>
                    <ThOrdenable campo="registrado_por" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Aplicado por
                    </ThOrdenable>
                    <ThOrdenable campo="nota" orden={orden} direccion={direccion} onOrdenar={alternar}>
                      Nota
                    </ThOrdenable>
                  </tr>
                </thead>
                <tbody>
                  {items.map((i) => (
                    <tr key={i.id}>
                      <td>{formatoFecha(i.fecha)}</td>
                      <td>{i.usuario_nombre}</td>
                      <td>{i.cliente_nombre}</td>
                      <td className="derecha">{moneda.format(i.monto)}</td>
                      <td className="derecha">{moneda.format(i.saldo_pendiente)}</td>
                      <td className="derecha">{i.facturas_afectadas}</td>
                      <td>{i.registrado_por}</td>
                      <td>{i.nota ?? '—'}</td>
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