import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { PermisoRoute } from './auth/PermisoRoute'
import { useAuth } from './auth/useAuth'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { Productos } from './pages/Productos'
import { Clientes } from './pages/Clientes'
import { Usuarios } from './pages/Usuarios'
import { Permisos } from './pages/Permisos'
import { Reportes } from './pages/Reportes'
import { Ventas } from './pages/Ventas'
import { Caja } from './pages/Caja'
import { Ingresos } from './pages/Ingresos'
import { Perfil } from './pages/Perfil'

/**
 * Página inicial: muestra el Dashboard si el usuario puede verlo; si no, lo
 * manda a su primer módulo disponible (p. ej. un Mesero cae en Ventas).
 */
function Inicio() {
  const { tienePermiso } = useAuth()
  if (tienePermiso('dashboard.ver')) return <Dashboard />
  if (tienePermiso('ventas.ver')) return <Navigate to="/ventas" replace />
  if (tienePermiso('caja.ver')) return <Navigate to="/caja" replace />
  if (tienePermiso('productos.ver')) return <Navigate to="/productos" replace />
  if (tienePermiso('clientes.ver')) return <Navigate to="/clientes" replace />
  if (tienePermiso('ingresos.ver')) return <Navigate to="/ingresos" replace />
  if (tienePermiso('reportes.ver')) return <Navigate to="/reportes" replace />
  if (tienePermiso('usuarios.gestionar')) return <Navigate to="/usuarios" replace />
  if (tienePermiso('permisos.gestionar')) return <Navigate to="/permisos" replace />
  return <Navigate to="/perfil" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Inicio />} />
          <Route
            path="productos"
            element={
              <PermisoRoute permiso="productos.ver">
                <Productos />
              </PermisoRoute>
            }
          />
          <Route
            path="ventas"
            element={
              <PermisoRoute permiso="ventas.ver">
                <Ventas />
              </PermisoRoute>
            }
          />
          <Route
            path="caja"
            element={
              <PermisoRoute permiso="caja.ver">
                <Caja />
              </PermisoRoute>
            }
          />
          <Route
            path="ingresos"
            element={
              <PermisoRoute permiso="ingresos.ver">
                <Ingresos />
              </PermisoRoute>
            }
          />
          <Route
            path="clientes"
            element={
              <PermisoRoute permiso="clientes.ver">
                <Clientes />
              </PermisoRoute>
            }
          />
          <Route
            path="reportes"
            element={
              <PermisoRoute permiso="reportes.ver">
                <Reportes />
              </PermisoRoute>
            }
          />
          <Route
            path="usuarios"
            element={
              <PermisoRoute permiso="usuarios.gestionar">
                <Usuarios />
              </PermisoRoute>
            }
          />
          <Route
            path="permisos"
            element={
              <PermisoRoute permiso="permisos.gestionar">
                <Permisos />
              </PermisoRoute>
            }
          />
          <Route path="perfil" element={<Perfil />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  )
}
