import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './useAuth'

export function ProtectedRoute() {
  const { usuario, cargando } = useAuth()
  if (cargando) return <div className="centrado">Cargando…</div>
  if (!usuario) return <Navigate to="/login" replace />
  return <Outlet />
}
