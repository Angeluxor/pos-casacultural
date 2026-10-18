import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { CampoPassword } from '../components/CampoPassword'

export function Login() {
  const { usuario, cargando, login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    if (!cargando && usuario) navigate('/', { replace: true })
  }, [cargando, usuario, navigate])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setEnviando(true)
    try {
      await login(username, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar sesión')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="pantalla">
      <div className="tarjeta">
        <header className="marca">
          <img src="/LogoCO-Photoroom.png" alt="Logo Casi Obsceno" className="logo logo--login" />
          <h1>Casi Obsceno</h1>
          <span className="estado">Acceso al sistema</span>
        </header>

        <form className="login" onSubmit={onSubmit}>
          <h2>Iniciar sesión</h2>
          {error && <p className="error">{error}</p>}
          <label>
            Usuario
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label>
            Contraseña
            <CampoPassword
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <button className="boton" type="submit" disabled={enviando}>
            {enviando ? 'Entrando…' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  )
}
