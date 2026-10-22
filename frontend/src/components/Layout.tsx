import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { APP_VERSION } from '../lib/version'
import { useOffline } from '../offline/useOffline'
import { FeedbackWidget } from './FeedbackWidget'

type Enlace = { to: string; label: string; end?: boolean; permiso: string }

const enlaces: Enlace[] = [
  { to: '/', label: 'Dashboard', end: true, permiso: 'dashboard.ver' },
  { to: '/productos', label: 'Productos', permiso: 'productos.ver' },
  { to: '/costos', label: 'Costos', permiso: 'costos.ver' },
  { to: '/ventas', label: 'Ventas', permiso: 'ventas.ver' },
  { to: '/caja', label: 'Caja', permiso: 'caja.ver' },
  { to: '/ingresos', label: 'Ingresos', permiso: 'ingresos.ver' },
  { to: '/proveedores', label: 'Proveedores', permiso: 'proveedores.ver' },
  { to: '/clientes', label: 'Clientes', permiso: 'clientes.ver' },
  { to: '/reportes', label: 'Reportes', permiso: 'reportes.ver' },
  { to: '/balance', label: 'Balance', permiso: 'balance.ver' },
  { to: '/feedback', label: 'Feedback', permiso: 'feedback.gestionar' },
  { to: '/usuarios', label: 'Usuarios', permiso: 'usuarios.gestionar' },
  { to: '/permisos', label: 'Permisos', permiso: 'permisos.gestionar' },
]

export function Layout() {
  const { usuario, logout, tienePermiso } = useAuth()
  const {
    enLinea,
    pendientes,
    sincronizando,
    ultimoError,
    sincronizarAhora,
  } = useOffline()
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
    if (pendientes > 0) {
      const seguir = window.confirm(
        `Hay ${pendientes} operación(es) sin sincronizar. Si cierras sesión, ` +
          'deberás volver a entrar con el mismo usuario y con conexión para ' +
          'enviarlas. ¿Cerrar sesión de todos modos?',
      )
      if (!seguir) return
    }
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
          <img src="/LogoCO-Photoroom.png" alt="Logo Casi Obsceno" className="logo" />
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
          <img src="/LogoCO-Photoroom.png" alt="Logo Casi Obsceno" className="logo logo--sidebar" />
          <div className="brand-text">
            <strong>Casi Obsceno</strong>
            <small>POS</small>
          </div>
        </div>

        <nav className="nav">
          {enlaces
            .filter((e) => tienePermiso(e.permiso))
            .map((e) => (
              <NavLink key={e.to} to={e.to} end={e.end} className={claseEnlace}>
                {e.label}
              </NavLink>
            ))}
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
          <span className="app-version" title={`Versión ${APP_VERSION}`}>
            v{APP_VERSION}
          </span>
        </div>
      </aside>

      <main className="contenido">
        {(!enLinea || pendientes > 0) && (
          <div
            className={
              enLinea
                ? 'aviso-offline aviso-offline--pendiente'
                : 'aviso-offline aviso-offline--sin-red'
            }
            role="status"
          >
            <div>
              <strong>
                {enLinea
                  ? `${pendientes} operación(es) pendiente(s) de sincronizar`
                  : 'Sin conexión'}
              </strong>
              <span>
                {enLinea
                  ? ' Se enviarán automáticamente al recuperar la conexión.'
                  : ' Puedes seguir vendiendo: las operaciones se guardan en este dispositivo.'}
              </span>
              {ultimoError && <small className="aviso-offline__error">{ultimoError}</small>}
            </div>
            {pendientes > 0 && (
              <button
                type="button"
                className="boton boton--mini"
                disabled={sincronizando || !enLinea}
                onClick={() => void sincronizarAhora()}
              >
                {sincronizando ? 'Sincronizando…' : 'Sincronizar ahora'}
              </button>
            )}
          </div>
        )}
        <Outlet />
      </main>

      <FeedbackWidget />
    </div>
  )
}
