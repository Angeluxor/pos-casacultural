import { useState, type FormEvent } from 'react'
import {
  actualizarProveedor,
  crearProveedor,
  eliminarProveedor,
  paginaProveedores,
  type Proveedor,
} from '../api/proveedores'
import { useAuth } from '../auth/useAuth'
import { Paginacion } from '../components/Paginacion'
import { ThOrdenable } from '../components/ThOrdenable'
import { useOrdenServidor } from '../lib/orden'
import { Vacio } from '../components/Vacio'
import { confirmarCierre } from '../lib/modal'
import { usePaginacion } from '../lib/usePaginacion'

export function Proveedores() {
  const { tienePermiso } = useAuth()
  const puedeCrear = tienePermiso('proveedores.crear')
  const puedeEditar = tienePermiso('proveedores.editar')
  const puedeEliminar = tienePermiso('proveedores.eliminar')

  const { orden, direccion, alternar } = useOrdenServidor()
  const { datos, skip, setSkip, buscar, setBuscar, cargando, error, recargar, tamano } =
    usePaginacion(paginaProveedores, 25, orden, direccion)
  const proveedores = datos?.items ?? []
  const total = datos?.total ?? 0
  const [errorAccion, setErrorAccion] = useState('')
  const [eliminandoId, setEliminandoId] = useState<number | null>(null)
  const [formProveedor, setFormProveedor] = useState<{
    abierto: boolean
    proveedor: Proveedor | null
  }>({ abierto: false, proveedor: null })

  async function borrar(proveedor: Proveedor) {
    if (
      !window.confirm(
        `¿Eliminar el proveedor "${proveedor.nombre}"?\n\n` +
          'Solo se puede eliminar si no tiene ingresos asociados.',
      )
    )
      return
    setErrorAccion('')
    setEliminandoId(proveedor.id)
    try {
      await eliminarProveedor(proveedor.id)
      recargar()
    } catch (err) {
      setErrorAccion(err instanceof Error ? err.message : 'Error al eliminar el proveedor')
    } finally {
      setEliminandoId(null)
    }
  }

  const mensajeError = error || errorAccion

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Proveedores</h1>
          <p className="ayuda">{total} proveedores registrados</p>
        </div>
        {puedeCrear && (
          <button
            className="boton"
            onClick={() => setFormProveedor({ abierto: true, proveedor: null })}
          >
            + Nuevo proveedor
          </button>
        )}
      </header>

      <div className="barra">
        <input
          className="campo-busqueda"
          placeholder="Buscar por nombre, documento, celular o correo…"
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
        />
      </div>

      {mensajeError && <p className="error">{mensajeError}</p>}

      {cargando ? (
        <p className="ayuda">Cargando…</p>
      ) : proveedores.length === 0 ? (
        <Vacio
          titulo={buscar.trim() ? 'Sin resultados' : 'Aún no hay proveedores'}
          detalle={
            buscar.trim()
              ? `Nada coincide con «${buscar.trim()}».`
              : 'Agrega tu primer proveedor para usarlo en los ingresos de inventario.'
          }
        />
      ) : (
        <>
          <div className="tabla-wrap tabla-wrap--cards">
            <table className="tabla tabla--cards">
              <thead>
                <tr>
                  <ThOrdenable campo="nombre" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Nombre
                  </ThOrdenable>
                  <ThOrdenable campo="documento" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Documento
                  </ThOrdenable>
                  <ThOrdenable campo="celular" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Celular
                  </ThOrdenable>
                  <ThOrdenable campo="correo" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Correo
                  </ThOrdenable>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {proveedores.map((p) => (
                  <tr key={p.id}>
                    <td data-label="Nombre">{p.nombre}</td>
                    <td data-label="Documento">{p.documento || '—'}</td>
                    <td data-label="Celular">{p.celular || '—'}</td>
                    <td data-label="Correo">{p.correo || '—'}</td>
                    <td className="celda-accion">
                      <div className="acciones-fila">
                        {puedeEditar && (
                          <button
                            className="boton boton--mini"
                            onClick={() =>
                              setFormProveedor({ abierto: true, proveedor: p })
                            }
                          >
                            Editar
                          </button>
                        )}
                        {puedeEliminar && (
                          <button
                            className="boton boton--mini boton--danger"
                            onClick={() => void borrar(p)}
                            disabled={eliminandoId === p.id}
                          >
                            {eliminandoId === p.id ? 'Eliminando…' : 'Eliminar'}
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

      {formProveedor.abierto && (
        <FormProveedor
          proveedor={formProveedor.proveedor}
          onCerrar={() => setFormProveedor({ abierto: false, proveedor: null })}
          onGuardado={() => {
            setFormProveedor({ abierto: false, proveedor: null })
            recargar()
          }}
        />
      )}
    </div>
  )
}

function FormProveedor({
  proveedor,
  onCerrar,
  onGuardado,
}: {
  proveedor: Proveedor | null
  onCerrar: () => void
  onGuardado: (creado?: Proveedor) => void
}) {
  const esEdicion = proveedor !== null
  const [nombre, setNombre] = useState(proveedor?.nombre ?? '')
  const [documento, setDocumento] = useState(proveedor?.documento ?? '')
  const [celular, setCelular] = useState(proveedor?.celular ?? '')
  const [correo, setCorreo] = useState(proveedor?.correo ?? '')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (!nombre.trim()) {
      setError('El nombre del proveedor es obligatorio.')
      return
    }
    const correoLimpio = correo.trim()
    if (correoLimpio && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(correoLimpio)) {
      setError('El correo no tiene un formato válido.')
      return
    }
    setGuardando(true)
    try {
      const datos = {
        nombre: nombre.trim(),
        documento: documento.trim() || null,
        celular: celular.trim() || null,
        correo: correoLimpio || null,
      }
      const creado = proveedor
        ? await actualizarProveedor(proveedor.id, datos)
        : await crearProveedor(datos)
      onGuardado(creado)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar el proveedor')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>{esEdicion ? 'Editar proveedor' : 'Nuevo proveedor'}</h2>
        {error && <p className="error">{error}</p>}
        <label>
          Nombre
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} required />
        </label>
        <label>
          Documento / NIT
          <input
            value={documento}
            onChange={(e) => setDocumento(e.target.value)}
            placeholder="Opcional"
          />
        </label>
        <label>
          Celular
          <input
            value={celular}
            onChange={(e) => setCelular(e.target.value.replace(/\D/g, ''))}
            inputMode="numeric"
            pattern="\d*"
            maxLength={15}
            placeholder="Opcional"
          />
        </label>
        <label>
          Correo
          <input
            type="email"
            value={correo}
            onChange={(e) => setCorreo(e.target.value)}
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
