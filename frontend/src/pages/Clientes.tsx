import { useState, type FormEvent } from 'react'
import {
  actualizarCliente,
  crearCliente,
  eliminarCliente,
  fusionarClientes,
  paginaClientes,
  type Cliente,
  type ClienteFusionResultado,
} from '../api/clientes'
import { useAuth } from '../auth/useAuth'
import { AyudaContextual } from '../components/AyudaContextual'
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
  const puedeFusionar = tienePermiso('clientes.fusionar')

  const { orden, direccion, alternar } = useOrdenServidor()
  const { datos, skip, setSkip, buscar, setBuscar, cargando, error, recargar, tamano } =
    usePaginacion(paginaClientes, 25, orden, direccion)
  const clientes = datos?.items ?? []
  const total = datos?.total ?? 0
  const [errorAccion, setErrorAccion] = useState('')
  const [mensajeAccion, setMensajeAccion] = useState('')
  const [eliminandoId, setEliminandoId] = useState<number | null>(null)
  const [seleccionados, setSeleccionados] = useState<Map<number, Cliente>>(new Map())
  const [fusionAbierta, setFusionAbierta] = useState(false)

  const [formCliente, setFormCliente] = useState<{ abierto: boolean; cliente: Cliente | null }>({
    abierto: false,
    cliente: null,
  })

  const todosPaginaSeleccionados =
    clientes.length > 0 && clientes.every((c) => seleccionados.has(c.id))

  function alternarSeleccion(cliente: Cliente) {
    setSeleccionados((prev) => {
      const nuevo = new Map(prev)
      if (nuevo.has(cliente.id)) nuevo.delete(cliente.id)
      else nuevo.set(cliente.id, cliente)
      return nuevo
    })
  }

  function alternarPagina() {
    setSeleccionados((prev) => {
      const nuevo = new Map(prev)
      if (todosPaginaSeleccionados) {
        clientes.forEach((c) => nuevo.delete(c.id))
      } else {
        clientes.forEach((c) => nuevo.set(c.id, c))
      }
      return nuevo
    })
  }

  async function borrar(cliente: Cliente) {
    if (
      !window.confirm(
        `¿Eliminar el cliente "${cliente.nombre}"?\n\n` +
          'Solo se puede eliminar si no tiene ventas asociadas.',
      )
    )
      return
    setErrorAccion('')
    setMensajeAccion('')
    setEliminandoId(cliente.id)
    try {
      await eliminarCliente(cliente.id)
      setSeleccionados((prev) => {
        const nuevo = new Map(prev)
        nuevo.delete(cliente.id)
        return nuevo
      })
      recargar()
    } catch (err) {
      setErrorAccion(err instanceof Error ? err.message : 'Error al eliminar el cliente')
    } finally {
      setEliminandoId(null)
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

      <AyudaContextual
        titulo="Para qué sirve esta pantalla"
        detalle="Registra y busca clientes, edita sus datos y fusiona duplicados. El documento es único y asocia las ventas a crédito y la cartera. Una fusión reasigna las facturas al cliente principal sin borrar historial."
      />

      <div className="barra">
        <input
          className="campo-busqueda"
          placeholder="Buscar por nombre, celular o correo…"
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
        />
      </div>

      {puedeFusionar && seleccionados.size > 0 && (
        <div className="barra barra--seleccion">
          <span className="ayuda">
            {seleccionados.size} cliente(s) seleccionado(s) para fusionar
          </span>
          <div className="acciones-fila">
            <button
              className="boton boton--mini"
              disabled={seleccionados.size < 2}
              onClick={() => {
                setErrorAccion('')
                setMensajeAccion('')
                setFusionAbierta(true)
              }}
            >
              Fusionar seleccionados
            </button>
            <button
              className="boton boton--mini"
              onClick={() => setSeleccionados(new Map())}
            >
              Limpiar
            </button>
          </div>
        </div>
      )}

      {mensajeError && <p className="error">{mensajeError}</p>}
      {mensajeAccion && <p className="ok">{mensajeAccion}</p>}

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
                  {puedeFusionar && (
                    <th className="celda-seleccion">
                      <input
                        type="checkbox"
                        className="tabla__check"
                        checked={todosPaginaSeleccionados}
                        onChange={alternarPagina}
                        aria-label="Seleccionar todos los clientes de esta página"
                      />
                    </th>
                  )}
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
                  <tr key={c.id} className={seleccionados.has(c.id) ? 'fila--seleccionada' : undefined}>
                    {puedeFusionar && (
                      <td className="celda-seleccion" data-label="">
                        <input
                          type="checkbox"
                          className="tabla__check"
                          checked={seleccionados.has(c.id)}
                          onChange={() => alternarSeleccion(c)}
                          aria-label={`Seleccionar a ${c.nombre}`}
                        />
                      </td>
                    )}
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
                            disabled={eliminandoId === c.id}
                          >
                            {eliminandoId === c.id ? 'Eliminando…' : 'Eliminar'}
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

      {fusionAbierta && (
        <FusionarClientes
          clientes={[...seleccionados.values()]}
          onCerrar={() => setFusionAbierta(false)}
          onFusionado={(resultado) => {
            setFusionAbierta(false)
            setSeleccionados(new Map())
            setMensajeAccion(
              `Fusión completada: ${resultado.clientes_eliminados} cliente(s) eliminado(s) ` +
                `y ${resultado.facturas_reasignadas} factura(s) reasignada(s) a ` +
                `«${resultado.cliente.nombre}».`,
            )
            recargar()
          }}
        />
      )}
    </div>
  )
}

function FusionarClientes({
  clientes,
  onCerrar,
  onFusionado,
}: {
  clientes: Cliente[]
  onCerrar: () => void
  onFusionado: (resultado: ClienteFusionResultado) => void
}) {
  const [destinoId, setDestinoId] = useState<number | null>(clientes[0]?.id ?? null)
  const [completarDatos, setCompletarDatos] = useState(true)
  const [error, setError] = useState('')
  const [fusionando, setFusionando] = useState(false)

  const destino = clientes.find((c) => c.id === destinoId) ?? null
  const origenes = clientes.filter((c) => c.id !== destinoId)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!destino || origenes.length === 0) return
    setError('')
    setFusionando(true)
    try {
      const resultado = await fusionarClientes({
        destino_id: destino.id,
        origen_ids: origenes.map((c) => c.id),
        completar_datos: completarDatos,
      })
      onFusionado(resultado)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron fusionar los clientes')
    } finally {
      setFusionando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>Fusionar clientes</h2>
        <p className="ayuda">
          Elige el cliente que se conservará. Las facturas de los demás se moverán
          a su historial y los registros duplicados se eliminarán.
        </p>
        {error && <p className="error">{error}</p>}

        <div className="fusion-lista" role="radiogroup" aria-label="Cliente que se conserva">
          {clientes.map((c) => (
            <label
              key={c.id}
              className={`fusion-opcion${destinoId === c.id ? ' fusion-opcion--activa' : ''}`}
            >
              <input
                type="radio"
                name="cliente-principal"
                checked={destinoId === c.id}
                onChange={() => setDestinoId(c.id)}
              />
              <span className="fusion-opcion__datos">
                <strong>{c.nombre}</strong>
                <small>
                  {c.documento ? `Doc. ${c.documento} · ` : ''}
                  {c.celular || 'Sin celular'} · {c.correo || 'Sin correo'}
                </small>
              </span>
            </label>
          ))}
        </div>

        <label className="check">
          <input
            type="checkbox"
            checked={completarDatos}
            onChange={(e) => setCompletarDatos(e.target.checked)}
          />
          Completar datos vacíos del cliente principal con los duplicados
        </label>

        <p className="ayuda">
          Se conservará «{destino?.nombre ?? '…'}» y se eliminarán{' '}
          {origenes.length} registro(s). Esta acción no se puede deshacer.
        </p>

        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button
            type="submit"
            className="boton boton--danger"
            disabled={fusionando || !destino || origenes.length === 0}
          >
            {fusionando ? 'Fusionando…' : 'Fusionar clientes'}
          </button>
        </div>
      </form>
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
