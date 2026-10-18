import { useState, type FormEvent } from 'react'
import {
  actualizarCliente,
  crearCliente,
  eliminarCliente,
  paginaClientes,
  type Cliente,
} from '../api/clientes'
import { useAuth } from '../auth/useAuth'
import { Paginacion } from '../components/Paginacion'
import { ThOrdenable } from '../components/ThOrdenable'
import { useOrdenServidor } from '../lib/orden'
import { Vacio } from '../components/Vacio'
import { confirmarCierre } from '../lib/modal'
import { usePaginacion } from '../lib/usePaginacion'

export function Clientes() {
  const { tienePermiso } = useAuth()
  const puedeCrear = tienePermiso('clientes.crear')
  const puedeEditar = tienePermiso('clientes.editar')
  const puedeEliminar = tienePermiso('clientes.eliminar')

  const { orden, direccion, alternar } = useOrdenServidor()
  const { datos, skip, setSkip, buscar, setBuscar, cargando, error, recargar, tamano } =
    usePaginacion(paginaClientes, 25, orden, direccion)
  const clientes = datos?.items ?? []
  const total = datos?.total ?? 0
  const [errorAccion, setErrorAccion] = useState('')

  const [formCliente, setFormCliente] = useState<{ abierto: boolean; cliente: Cliente | null }>({
    abierto: false,
    cliente: null,
  })

  async function borrar(cliente: Cliente) {
    if (!window.confirm(`¿Eliminar el cliente "${cliente.nombre}"?`)) return
    setErrorAccion('')
    try {
      await eliminarCliente(cliente.id)
      recargar()
    } catch (err) {
      setErrorAccion(err instanceof Error ? err.message : 'Error al eliminar el cliente')
    }
  }

  const mensajeError = error || errorAccion

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Clientes</h1>
          <p className="ayuda">{total} clientes registrados</p>
        </div>
        {puedeCrear && (
          <button
            className="boton"
            onClick={() => setFormCliente({ abierto: true, cliente: null })}
          >
            + Nuevo cliente
          </button>
        )}
      </header>

      <div className="barra">
        <input
          className="campo-busqueda"
          placeholder="Buscar por nombre, celular o correo…"
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
        />
      </div>

      {mensajeError && <p className="error">{mensajeError}</p>}

      {cargando ? (
        <p className="ayuda">Cargando…</p>
      ) : clientes.length === 0 ? (
        <Vacio
          titulo={buscar.trim() ? 'Sin resultados' : 'Aún no hay clientes'}
          detalle={
            buscar.trim()
              ? `Nada coincide con «${buscar.trim()}».`
              : 'Agrega tu primer cliente para empezar.'
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
                {clientes.map((c) => (
                  <tr key={c.id}>
                    <td data-label="Nombre">{c.nombre}</td>
                    <td data-label="Celular">{c.celular || '—'}</td>
                    <td data-label="Correo">{c.correo || '—'}</td>
                    <td className="celda-accion">
                      <div className="acciones-fila">
                        {puedeEditar && (
                          <button
                            className="boton boton--mini"
                            onClick={() => setFormCliente({ abierto: true, cliente: c })}
                          >
                            Editar
                          </button>
                        )}
                        {puedeEliminar && (
                          <button
                            className="boton boton--mini boton--danger"
                            onClick={() => void borrar(c)}
                          >
                            Eliminar
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

      {formCliente.abierto && (
        <FormCliente
          cliente={formCliente.cliente}
          onCerrar={() => setFormCliente({ abierto: false, cliente: null })}
          onGuardado={() => {
            setFormCliente({ abierto: false, cliente: null })
            recargar()
          }}
        />
      )}
    </div>
  )
}

export function FormCliente({
  cliente,
  onCerrar,
  onGuardado,
}: {
  cliente: Cliente | null
  onCerrar: () => void
  onGuardado: (creado?: Cliente) => void
}) {
  const esEdicion = cliente !== null
  const [nombre, setNombre] = useState(cliente?.nombre ?? '')
  const [celular, setCelular] = useState(cliente?.celular ?? '')
  const [correo, setCorreo] = useState(cliente?.correo ?? '')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const correoLimpio = correo.trim()
    if (correoLimpio && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(correoLimpio)) {
      setError('El correo no tiene un formato válido.')
      return
    }
    setGuardando(true)
    try {
      const datos = { nombre, celular: celular || null, correo: correoLimpio || null }
      const creado = cliente
        ? await actualizarCliente(cliente.id, datos)
        : await crearCliente(datos)
      onGuardado(creado)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar el cliente')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>{esEdicion ? 'Editar cliente' : 'Nuevo cliente'}</h2>
        {error && <p className="error">{error}</p>}
        <label>
          Nombre
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} required />
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
