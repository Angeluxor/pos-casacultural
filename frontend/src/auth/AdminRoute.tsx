import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './useAuth'

export function AdminRoute() {
  const { usuario } = useAuth()
  if (usuario?.rol !== 'Admin') return <Navigate to="/" replace />
  return <Outlet />
}
