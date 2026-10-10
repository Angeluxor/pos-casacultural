import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

type Enlace = { to: string; label: string; end?: boolean }

const enlaces: Enlace[] = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/productos', label: 'Productos' },
  { to: '/ventas', label: 'Ventas' },
  { to: '/caja', label: 'Caja' },
  { to: '/clientes', label: 'Clientes' },
]

export function Layout() {
  const { usuario, logout } = useAuth()
  const navigate = useNavigate()

  function salir() {
    logout()
    navigate('/login', { replace: true })
  }

  const claseEnlace = ({ isActive }: { isActive: boolean }) =>
    isActive ? 'nav__link nav__link--active' : 'nav__link'

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar__brand">
          <span className="brand-dot" />
          <div className="brand-text">
            <strong>Casa Cultural</strong>
            <small>POS</small>
          </div>
        </div>

        <nav className="nav">
          {enlaces.map((e) => (
            <NavLink key={e.to} to={e.to} end={e.end} className={claseEnlace}>
              {e.label}
            </NavLink>
          ))}
          {usuario?.rol === 'Admin' && (
            <NavLink to="/usuarios" className={claseEnlace}>
              Usuarios
            </NavLink>
          )}
          <NavLink to="/perfil" className={claseEnlace}>
            Mi perfil
          </NavLink>
        </nav>

        <div className="sidebar__foot">
          <NavLink to="/perfil" className="usuario-chip">
            <span className="avatar">{usuario?.nombre?.charAt(0).toUpperCase()}</span>
            <div className="usuario-chip__info">
              <strong>{usuario?.nombre}</strong>
              <small>{usuario?.rol}</small>
            </div>
          </NavLink>
          <button className="boton boton--secundario boton--block" onClick={salir}>
            Cerrar sesión
          </button>
        </div>
      </aside>

      <main className="contenido">
        <Outlet />
      </main>
    </div>
  )
}
