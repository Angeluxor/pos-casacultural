import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { AdminRoute } from './auth/AdminRoute'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { Productos } from './pages/Productos'
import { Clientes } from './pages/Clientes'
import { Usuarios } from './pages/Usuarios'
import { Reportes } from './pages/Reportes'
import { Ventas } from './pages/Ventas'
import { Caja } from './pages/Caja'
import { Ingresos } from './pages/Ingresos'
import { Perfil } from './pages/Perfil'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="productos" element={<Productos />} />
          <Route path="ventas" element={<Ventas />} />
          <Route path="caja" element={<Caja />} />
          <Route path="ingresos" element={<Ingresos />} />
          <Route path="clientes" element={<Clientes />} />
          <Route path="perfil" element={<Perfil />} />
          <Route element={<AdminRoute />}>
            <Route path="usuarios" element={<Usuarios />} />
            <Route path="reportes" element={<Reportes />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  )
}
