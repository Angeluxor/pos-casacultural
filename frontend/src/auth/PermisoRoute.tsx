import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from './useAuth'

/**
 * Deja pasar solo si el usuario de la sesión tiene el permiso indicado.
 * Si no, lo devuelve al inicio (que a su vez lo lleva a su primer módulo).
 */
export function PermisoRoute({
  permiso,
  children,
}: {
  permiso: string
  children: ReactNode
}) {
  const { tienePermiso } = useAuth()
  if (!tienePermiso(permiso)) return <Navigate to="/" replace />
  return <>{children}</>
}
