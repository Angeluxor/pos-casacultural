import { useState, type FormEvent } from 'react'
import { actualizarPerfil, cambiarPassword } from '../api/auth'
import { useAuth } from '../auth/useAuth'
import { AyudaContextual } from '../components/AyudaContextual'
import { CampoPassword } from '../components/CampoPassword'

export function Perfil() {
  const { usuario, refrescar } = useAuth()

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Mi perfil</h1>
          <p className="ayuda">Gestiona tus datos y tu contraseña.</p>
        </div>
      </header>

      <AyudaContextual
        titulo="Tus datos de acceso"
        detalle="El nombre se puede editar; el usuario y el rol no. Usa una contraseña que nadie más conozca y cámbiala si la compartiste. Si olvidaste la clave, un administrador puede restablecerla."
      />

      <div className="perfil-grid">
        <section className="panel">
          <h3>Cuenta</h3>
          <ul className="lista-simple">
            <li>
              <span className="ayuda">Usuario</span>
              <strong>{usuario?.username}</strong>
            </li>
            <li>
              <span className="ayuda">Nombre</span>
              <strong>{usuario?.nombre}</strong>
            </li>
            <li>
              <span className="ayuda">Rol</span>
              <span className="badge badge--info">{usuario?.rol}</span>
            </li>
            <li>
              <span className="ayuda">Estado</span>
              <span className={usuario?.activo ? 'badge badge--on' : 'badge badge--off'}>
                {usuario?.activo ? 'Activo' : 'Inactivo'}
              </span>
            </li>
          </ul>
        </section>

        <div className="dash-col">
          <FormDatos nombreActual={usuario?.nombre ?? ''} onGuardado={refrescar} />
          <FormPassword />
        </div>
      </div>
    </div>
  )
}

function FormDatos({
  nombreActual,
  onGuardado,
}: {
  nombreActual: string
  onGuardado: () => Promise<void>
}) {
  const [nombre, setNombre] = useState(nombreActual)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setOk('')
    setGuardando(true)
    try {
      await actualizarPerfil({ nombre })
      await onGuardado()
      setOk('Datos actualizados.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="panel">
      <h3>Datos</h3>
      <form className="form-pila" onSubmit={onSubmit}>
        {error && <p className="error">{error}</p>}
        {ok && <p className="ok">{ok}</p>}
        <label>
          Nombre
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            required
          />
        </label>
        <div className="acciones">
          <button type="submit" className="boton" disabled={guardando || nombre.trim() === ''}>
            {guardando ? 'Guardando…' : 'Guardar cambios'}
          </button>
        </div>
      </form>
    </section>
  )
}

function FormPassword() {
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [repetir, setRepetir] = useState('')
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [guardando, setGuardando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setOk('')
    if (nueva !== repetir) {
      setError('La nueva contraseña y su confirmación no coinciden')
      return
    }
    setGuardando(true)
    try {
      await cambiarPassword({ password_actual: actual, password_nueva: nueva })
      setActual('')
      setNueva('')
      setRepetir('')
      setOk('Contraseña actualizada.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cambiar la contraseña')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="panel">
      <h3>Cambiar contraseña</h3>
      <form className="form-pila" onSubmit={onSubmit}>
        {error && <p className="error">{error}</p>}
        {ok && <p className="ok">{ok}</p>}
        <label>
          Contraseña actual
          <CampoPassword
            value={actual}
            onChange={(e) => setActual(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <label>
          Nueva contraseña
          <CampoPassword
            value={nueva}
            onChange={(e) => setNueva(e.target.value)}
            autoComplete="new-password"
            minLength={6}
            required
          />
        </label>
        <label>
          Repetir nueva contraseña
          <CampoPassword
            value={repetir}
            onChange={(e) => setRepetir(e.target.value)}
            autoComplete="new-password"
            minLength={6}
            required
          />
        </label>
        <div className="acciones">
          <button type="submit" className="boton" disabled={guardando}>
            {guardando ? 'Cambiando…' : 'Cambiar contraseña'}
          </button>
        </div>
      </form>
    </section>
  )
}
