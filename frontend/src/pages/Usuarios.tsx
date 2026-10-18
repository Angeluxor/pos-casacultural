import { useState, type FormEvent } from 'react'
import {
  actualizarUsuario,
  crearUsuario,
  eliminarUsuario,
  paginaUsuarios,
  type UsuarioCreate,
} from '../api/usuarios'
import type { RolUsuario, Usuario } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { CampoPassword } from '../components/CampoPassword'
import { Paginacion } from '../components/Paginacion'
import { ThOrdenable } from '../components/ThOrdenable'
import { useOrdenServidor } from '../lib/orden'
import { Vacio } from '../components/Vacio'
import { confirmarCierre } from '../lib/modal'
import { usePaginacion } from '../lib/usePaginacion'

const ROLES: RolUsuario[] = ['Admin', 'Cajero', 'Mesero']

export function Usuarios() {
  const { usuario: actual } = useAuth()

  const { orden, direccion, alternar } = useOrdenServidor()
  const { datos, skip, setSkip, buscar, setBuscar, cargando, error, recargar, tamano } =
    usePaginacion(paginaUsuarios, 25, orden, direccion)
  const usuarios = datos?.items ?? []
  const total = datos?.total ?? 0

  const [form, setForm] = useState<{ abierto: boolean; usuario: Usuario | null }>({
    abierto: false,
    usuario: null,
  })
  const [errorAccion, setErrorAccion] = useState('')
  const [eliminandoId, setEliminandoId] = useState<number | null>(null)

  async function eliminar(u: Usuario) {
    if (!window.confirm(`¿Eliminar al usuario «${u.username}»? Esta acción no se puede deshacer.`))
      return
    setErrorAccion('')
    setEliminandoId(u.id)
    try {
      await eliminarUsuario(u.id)
      recargar()
    } catch (err) {
      setErrorAccion(err instanceof Error ? err.message : 'No se pudo eliminar el usuario')
    } finally {
      setEliminandoId(null)
    }
  }

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Usuarios</h1>
          <p className="ayuda">{total} usuarios</p>
        </div>
        <button className="boton" onClick={() => setForm({ abierto: true, usuario: null })}>
          + Nuevo usuario
        </button>
      </header>

      <div className="barra">
        <input
          className="campo-busqueda"
          placeholder="Buscar por usuario o nombre…"
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
        />
      </div>

      {error && <p className="error">{error}</p>}
      {errorAccion && <p className="error">{errorAccion}</p>}

      {cargando ? (
        <p className="ayuda">Cargando…</p>
      ) : usuarios.length === 0 ? (
        <Vacio
          titulo={buscar.trim() ? 'Sin resultados' : 'Aún no hay usuarios'}
          detalle={
            buscar.trim()
              ? `Nada coincide con «${buscar.trim()}».`
              : 'Crea el primer usuario del sistema.'
          }
        />
      ) : (
        <>
          <div className="tabla-wrap tabla-wrap--cards">
            <table className="tabla tabla--cards">
              <thead>
                <tr>
                  <ThOrdenable campo="username" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Usuario
                  </ThOrdenable>
                  <ThOrdenable campo="nombre" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Nombre
                  </ThOrdenable>
                  <ThOrdenable campo="rol" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Rol
                  </ThOrdenable>
                  <ThOrdenable campo="activo" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Estado
                  </ThOrdenable>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {usuarios.map((u) => (
                  <tr key={u.id}>
                    <td data-label="Usuario">{u.username}</td>
                    <td data-label="Nombre">{u.nombre}</td>
                    <td data-label="Rol">{u.rol}</td>
                    <td data-label="Estado">
                      <span className={u.activo ? 'badge badge--on' : 'badge badge--off'}>
                        {u.activo ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    <td className="celda-accion">
                      <div className="acciones-fila">
                        <button
                          className="boton boton--mini"
                          onClick={() => setForm({ abierto: true, usuario: u })}
                        >
                          Editar
                        </button>
                        <button
                          className="boton boton--mini boton--danger"
                          disabled={u.id === actual?.id || eliminandoId === u.id}
                          title={
                            u.id === actual?.id ? 'No puedes eliminar tu propio usuario' : undefined
                          }
                          onClick={() => void eliminar(u)}
                        >
                          {eliminandoId === u.id ? 'Eliminando…' : 'Eliminar'}
                        </button>
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

      {form.abierto && (
        <FormUsuario
          usuario={form.usuario}
          esUsuarioActual={form.usuario?.id === actual?.id}
          onCerrar={() => setForm({ abierto: false, usuario: null })}
          onGuardado={() => {
            setForm({ abierto: false, usuario: null })
            recargar()
          }}
        />
      )}
    </div>
  )
}

function FormUsuario({
  usuario,
  esUsuarioActual,
  onCerrar,
  onGuardado,
}: {
  usuario: Usuario | null
  esUsuarioActual: boolean
  onCerrar: () => void
  onGuardado: () => void
}) {
  const esEdicion = usuario !== null
  const [username, setUsername] = useState(usuario?.username ?? '')
  const [nombre, setNombre] = useState(usuario?.nombre ?? '')
  const [password, setPassword] = useState('')
  const [rol, setRol] = useState<RolUsuario>(usuario?.rol ?? 'Cajero')
  const [activo, setActivo] = useState(usuario?.activo ?? true)
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setGuardando(true)
    try {
      if (usuario) {
        await actualizarUsuario(usuario.id, {
          nombre,
          rol,
          activo,
          ...(password ? { password } : {}),
        })
      } else {
        const data: UsuarioCreate = { username, nombre, password, rol, activo }
        await crearUsuario(data)
      }
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar el usuario')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>{esEdicion ? 'Editar usuario' : 'Nuevo usuario'}</h2>
        {error && <p className="error">{error}</p>}
        <label>
          Usuario
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            disabled={esEdicion}
          />
        </label>
        <label>
          Nombre
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} required />
        </label>
        <label>
          Contraseña {esEdicion ? '(dejar vacío para no cambiar)' : ''}
          <CampoPassword
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required={!esEdicion}
            autoComplete="new-password"
          />
        </label>
        <label>
          Rol
          <select value={rol} onChange={(e) => setRol(e.target.value as RolUsuario)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={activo}
            disabled={esUsuarioActual}
            onChange={(e) => setActivo(e.target.checked)}
          />
          Activo
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
