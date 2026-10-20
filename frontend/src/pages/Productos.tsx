import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  actualizarProducto,
  crearProducto,
  historialKardex,
  paginaProductos,
  registrarMovimiento,
  MOTIVOS_AJUSTE,
  type KardexMovimiento,
  type MotivoAjuste,
  type Producto,
} from '../api/productos'
import { useAuth } from '../auth/useAuth'
import { AyudaContextual } from '../components/AyudaContextual'
import { Paginacion } from '../components/Paginacion'
import { ThOrdenable } from '../components/ThOrdenable'
import { useOrdenLocal, useOrdenServidor, type Accesores } from '../lib/orden'
import { Vacio } from '../components/Vacio'
import { confirmarCierre } from '../lib/modal'
import { formatoFecha } from '../lib/formato'
import { usePaginacion } from '../lib/usePaginacion'

const moneda = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
})

export function Productos() {
  const { tienePermiso } = useAuth()
  const puedeCrear = tienePermiso('productos.crear')
  const puedeEditar = tienePermiso('productos.editar')
  const puedeAjustar = tienePermiso('productos.ajustar')
  const puedeIngresar = tienePermiso('ingresos.crear')
  const navigate = useNavigate()

  const { orden, direccion, alternar } = useOrdenServidor()
  const { datos, skip, setSkip, buscar, setBuscar, cargando, error, recargar, tamano } =
    usePaginacion(paginaProductos, 25, orden, direccion)
  const productos = datos?.items ?? []
  const total = datos?.total ?? 0

  const [formProducto, setFormProducto] = useState<{ abierto: boolean; producto: Producto | null }>({
    abierto: false,
    producto: null,
  })
  const [movProducto, setMovProducto] = useState<Producto | null>(null)
  const [kardexProducto, setKardexProducto] = useState<Producto | null>(null)

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Productos</h1>
          <p className="ayuda">{total} productos en catálogo</p>
        </div>
        <div className="acciones-fila">
          {puedeIngresar && (
            <button
              className="boton boton--secundario"
              onClick={() => navigate('/ingresos?nuevo=1')}
            >
              Ingreso de inventario
            </button>
          )}
          {puedeCrear && (
            <button
              className="boton"
              onClick={() => setFormProducto({ abierto: true, producto: null })}
            >
              + Nuevo producto
            </button>
          )}
        </div>
      </header>

      <AyudaContextual
        titulo="Cómo se organiza el catálogo"
        detalle="Aquí creas y editas productos, registras movimientos de stock y consultas el kardex. El stock cambia con ventas, compras, devoluciones y ajustes. El código no se puede cambiar después de crear el producto."
      />

      <div className="barra">
        <input
          className="campo-busqueda"
          placeholder="Buscar por código o nombre…"
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
        />
      </div>

      {error && <p className="error">{error}</p>}

      {cargando ? (
        <p className="ayuda">Cargando…</p>
      ) : productos.length === 0 ? (
        <Vacio
          titulo={buscar.trim() ? 'Sin resultados' : 'Aún no hay productos'}
          detalle={
            buscar.trim()
              ? `Nada coincide con «${buscar.trim()}».`
              : 'Agrega tu primer producto para empezar.'
          }
        />
      ) : (
        <>
          <div className="tabla-wrap tabla-wrap--cards">
            <table className="tabla tabla--cards">
              <thead>
                <tr>
                  <ThOrdenable campo="codigo" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Código
                  </ThOrdenable>
                  <ThOrdenable campo="nombre" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Nombre
                  </ThOrdenable>
                  <ThOrdenable
                    campo="precio"
                    orden={orden}
                    direccion={direccion}
                    onOrdenar={alternar}
                    className="derecha"
                  >
                    Precio
                  </ThOrdenable>
                  <ThOrdenable
                    campo="stock"
                    orden={orden}
                    direccion={direccion}
                    onOrdenar={alternar}
                    className="derecha"
                  >
                    Stock
                  </ThOrdenable>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {productos.map((p) => (
                  <tr key={p.id}>
                    <td data-label="Código">{p.codigo}</td>
                    <td data-label="Nombre">{p.nombre}</td>
                    <td data-label="Precio" className="derecha">
                      {moneda.format(p.precio)}
                    </td>
                    <td data-label="Stock" className="derecha">
                      {p.stock}
                    </td>
                    <td className="celda-accion">
                      <div className="acciones-fila">
                        {puedeAjustar && (
                          <button className="boton boton--mini" onClick={() => setMovProducto(p)}>
                            Stock
                          </button>
                        )}
                        <button className="boton boton--mini" onClick={() => setKardexProducto(p)}>
                          Historial
                        </button>
                        {puedeEditar && (
                          <button
                            className="boton boton--mini"
                            onClick={() => setFormProducto({ abierto: true, producto: p })}
                          >
                            Editar
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

      {formProducto.abierto && (
        <FormProducto
          producto={formProducto.producto}
          onCerrar={() => setFormProducto({ abierto: false, producto: null })}
          onGuardado={() => {
            setFormProducto({ abierto: false, producto: null })
            recargar()
          }}
        />
      )}

      {movProducto && (
        <FormMovimiento
          producto={movProducto}
          onCerrar={() => setMovProducto(null)}
          onGuardado={() => {
            setMovProducto(null)
            recargar()
          }}
        />
      )}

      {kardexProducto && (
        <FormKardex producto={kardexProducto} onCerrar={() => setKardexProducto(null)} />
      )}
    </div>
  )
}

function FormProducto({
  producto,
  onCerrar,
  onGuardado,
}: {
  producto: Producto | null
  onCerrar: () => void
  onGuardado: () => void
}) {
  const esEdicion = producto !== null
  const [codigo, setCodigo] = useState(producto?.codigo ?? '')
  const [nombre, setNombre] = useState(producto?.nombre ?? '')
  const [precio, setPrecio] = useState(producto ? String(producto.precio) : '')
  const [stockInicial, setStockInicial] = useState('0')
  const [mismaUnidad, setMismaUnidad] = useState(
    producto?.misma_unidad_compra_venta ?? true,
  )
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setGuardando(true)
    try {
      if (producto) {
        await actualizarProducto(producto.id, {
          nombre,
          precio: Number(precio),
          misma_unidad_compra_venta: mismaUnidad,
        })
      } else {
        await crearProducto({
          codigo,
          nombre,
          precio: Number(precio),
          stock_inicial: Number(stockInicial),
          misma_unidad_compra_venta: mismaUnidad,
        })
      }
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar el producto')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>{esEdicion ? 'Editar producto' : 'Nuevo producto'}</h2>
        {error && <p className="error">{error}</p>}
        <label>
          Código
          <input
            value={codigo}
            onChange={(e) => setCodigo(e.target.value)}
            required
            disabled={esEdicion}
          />
        </label>
        <label>
          Nombre
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} required />
        </label>
        <label>
          Precio
          <input
            type="number"
            min="0"
            step="0.01"
            value={precio}
            onChange={(e) => setPrecio(e.target.value)}
            required
          />
        </label>
        {!esEdicion && (
          <label>
            Stock inicial
            <input
              type="number"
              value={stockInicial}
              onChange={(e) => setStockInicial(e.target.value)}
            />
          </label>
        )}
        <label className="check">
          <input
            type="checkbox"
            checked={mismaUnidad}
            onChange={(e) => setMismaUnidad(e.target.checked)}
          />
          Se compra y se vende en la misma unidad (1:1)
        </label>
        <p className="ayuda">
          Desmárcalo si compras por caja o paquete y vendes por unidad: en Costos
          no se mostrará la relación CMV/precio de ese producto.
        </p>
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

function FormMovimiento({
  producto,
  onCerrar,
  onGuardado,
}: {
  producto: Producto
  onCerrar: () => void
  onGuardado: () => void
}) {
  const [cantidad, setCantidad] = useState('1')
  const [motivo, setMotivo] = useState<MotivoAjuste>('Derrama o pérdida')
  const [motivoDetalle, setMotivoDetalle] = useState('')
  const [referencia, setReferencia] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const cant = Number(cantidad)
    if (!Number.isInteger(cant)) {
      setError('La cantidad debe ser un número entero.')
      return
    }
    if (cant === 0) {
      setError('El ajuste no puede ser 0.')
      return
    }
    if (motivo === 'Otro' && !motivoDetalle.trim()) {
      setError("Especifica el detalle del motivo 'Otro'.")
      return
    }
    setGuardando(true)
    try {
      await registrarMovimiento(producto.id, {
        tipo_movimiento: 'Ajuste',
        cantidad: cant,
        referencia: referencia || undefined,
        motivo,
        motivo_detalle: motivo === 'Otro' ? motivoDetalle.trim() : undefined,
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
        <h2>Ajuste de stock</h2>
        <p className="ayuda">
          {producto.nombre} · stock actual: {producto.stock}
        </p>
        {error && <p className="error">{error}</p>}
        <label>
          Motivo
          <select value={motivo} onChange={(e) => setMotivo(e.target.value as MotivoAjuste)}>
            {MOTIVOS_AJUSTE.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        {motivo === 'Otro' && (
          <label>
            Detalle del motivo
            <input
              value={motivoDetalle}
              onChange={(e) => setMotivoDetalle(e.target.value)}
              placeholder="Describe el motivo del ajuste"
              required
            />
          </label>
        )}
        <label>
          Cantidad (usa signo: + suma, − resta)
          <input
            type="number"
            value={cantidad}
            onChange={(e) => setCantidad(e.target.value)}
            step={1}
            required
          />
        </label>
        <label>
          Referencia
          <input
            value={referencia}
            onChange={(e) => setReferencia(e.target.value)}
            placeholder="Opcional"
          />
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

function cambioConSigno(m: KardexMovimiento): number {
  if (m.tipo_movimiento === 'Ajuste') return m.cantidad
  if (m.tipo_movimiento === 'Salida por Venta') return -Math.abs(m.cantidad)
  return Math.abs(m.cantidad)
}

const ACCESORES_KARDEX: Accesores<KardexMovimiento> = {
  fecha: (m) => m.fecha,
  tipo: (m) => m.tipo_movimiento,
  cambio: (m) => cambioConSigno(m),
  stock: (m) => m.saldo_stock,
  motivo: (m) => m.motivo ?? '',
  referencia: (m) => m.referencia ?? '',
}

function FormKardex({ producto, onCerrar }: { producto: Producto; onCerrar: () => void }) {
  const [movs, setMovs] = useState<KardexMovimiento[]>([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const { items: movsOrdenados, orden, direccion, alternar } = useOrdenLocal(
    movs,
    ACCESORES_KARDEX,
    { campo: 'fecha', direccion: 'desc' },
  )

  useEffect(() => {
    let cancelado = false
    setCargando(true)
    historialKardex(producto.id)
      .then((m) => {
        if (!cancelado) setMovs(m)
      })
      .catch((err) => {
        if (!cancelado) setError(err instanceof Error ? err.message : 'Error al cargar el historial')
      })
      .finally(() => {
        if (!cancelado) setCargando(false)
      })
    return () => {
      cancelado = true
    }
  }, [producto.id])

  return (
    <div className="modal-overlay modal-overlay--full" onClick={onCerrar}>
      <div className="modal modal--ancho" onClick={(e) => e.stopPropagation()}>
        <h2>Historial de stock</h2>
        <p className="ayuda">
          {producto.nombre} · stock actual: {producto.stock}
        </p>
        {error && <p className="error">{error}</p>}
        {cargando ? (
          <p className="ayuda">Cargando…</p>
        ) : movs.length === 0 ? (
          <Vacio
            titulo="Sin movimientos"
            detalle="Este producto aún no tiene entradas ni salidas registradas."
          />
        ) : (
          <div className="tabla-wrap tabla-wrap--cards">
            <table className="tabla tabla--cards">
              <thead>
                <tr>
                  <ThOrdenable campo="fecha" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Fecha
                  </ThOrdenable>
                  <ThOrdenable campo="tipo" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Tipo
                  </ThOrdenable>
                  <ThOrdenable
                    campo="cambio"
                    orden={orden}
                    direccion={direccion}
                    onOrdenar={alternar}
                    className="derecha"
                  >
                    Cambio
                  </ThOrdenable>
                  <ThOrdenable
                    campo="stock"
                    orden={orden}
                    direccion={direccion}
                    onOrdenar={alternar}
                    className="derecha"
                  >
                    Stock
                  </ThOrdenable>
                  <ThOrdenable campo="motivo" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Motivo
                  </ThOrdenable>
                  <ThOrdenable
                    campo="referencia"
                    orden={orden}
                    direccion={direccion}
                    onOrdenar={alternar}
                  >
                    Referencia
                  </ThOrdenable>
                </tr>
              </thead>
              <tbody>
                {movsOrdenados.map((m) => {
                  const cambio = cambioConSigno(m)
                  return (
                    <tr key={m.id}>
                      <td data-label="Fecha">{formatoFecha(m.fecha)}</td>
                      <td data-label="Tipo">{m.tipo_movimiento}</td>
                      <td data-label="Cambio" className="derecha">
                        <span
                          className={
                            cambio < 0 ? 'diferencia diferencia--bad' : 'diferencia diferencia--ok'
                          }
                        >
                          {cambio > 0 ? `+${cambio}` : cambio}
                        </span>
                      </td>
                      <td data-label="Stock" className="derecha">
                        {m.saldo_stock}
                      </td>
                      <td data-label="Motivo">
                        {m.motivo ?? '—'}
                        {m.motivo_detalle ? ` (${m.motivo_detalle})` : ''}
                      </td>
                      <td data-label="Referencia">{m.referencia ?? '—'}</td>
                    </tr>
                  )
                })}
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
