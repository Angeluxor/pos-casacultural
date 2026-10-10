import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
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
  const location = useLocation()
  const [menuAbierto, setMenuAbierto] = useState(false)

  useEffect(() => {
    setMenuAbierto(false)
  }, [location.pathname])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setMenuAbierto(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  function salir() {
    logout()
    navigate('/login', { replace: true })
  }

  const claseEnlace = ({ isActive }: { isActive: boolean }) =>
    isActive ? 'nav__link nav__link--active' : 'nav__link'

  return (
    <div className="app">
      <header className="topbar">
        <button
          className="topbar__menu"
          aria-label="Abrir menú"
          aria-expanded={menuAbierto}
          onClick={() => setMenuAbierto(true)}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M4 6h16M4 12h16M4 18h16"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>
        <div className="topbar__marca">
          <span className="brand-dot" />
          <strong>Casi Obsceno</strong>
        </div>
        <span className="avatar avatar--mini">
          {usuario?.nombre?.charAt(0).toUpperCase()}
        </span>
      </header>

      <div
        className={menuAbierto ? 'drawer-scrim drawer-scrim--activo' : 'drawer-scrim'}
        onClick={() => setMenuAbierto(false)}
      />

      <aside className={menuAbierto ? 'sidebar sidebar--abierto' : 'sidebar'}>
        <div className="sidebar__brand">
          <span className="brand-dot" />
          <div className="brand-text">
            <strong>Casi Obsceno</strong>
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
