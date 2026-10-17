import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { AuthProvider } from './auth/AuthProvider'
import type { Usuario } from './api/types'
import type { DashboardResumen } from './api/dashboard'

const USUARIO: Usuario = {
  id: 1,
  username: 'sistema',
  nombre: 'Usuario Sistema',
  rol: 'Admin',
  activo: true,
}

const DASHBOARD: DashboardResumen = {
  kpis: {
    ventas_hoy_total: 120000,
    ventas_hoy_cantidad: 3,
    ventas_7d_total: 850000,
    cartera_total: 200000,
    facturas_pendientes: 2,
    facturas_credito: 1,
  },
  ventas_ultimos_7_dias: [
    { fecha: '2026-10-04', total: 100000, cantidad: 2 },
    { fecha: '2026-10-05', total: 0, cantidad: 0 },
    { fecha: '2026-10-06', total: 50000, cantidad: 1 },
    { fecha: '2026-10-07', total: 0, cantidad: 0 },
    { fecha: '2026-10-08', total: 0, cantidad: 0 },
    { fecha: '2026-10-09', total: 0, cantidad: 0 },
    { fecha: '2026-10-10', total: 120000, cantidad: 3 },
  ],
  productos_bajo_stock: [
    { id: 7, codigo: 'LI006', nombre: 'Ron Media', stock: 2 },
  ],
  facturas_por_estado: { Abierta: 2, 'Pagado Parcial': 1, Pagada: 530, Crédito: 1, Anulada: 0 },
  caja: {
    abierta: true,
    turno_id: 1,
    saldo_inicial_efectivo: 0,
    saldo_inicial_banco: 0,
    entradas_efectivo: 120000,
    entradas_banco: 0,
    salidas_efectivo: 0,
    salidas_banco: 0,
    esperado_efectivo: 120000,
    esperado_banco: 0,
  },
  total_clientes: 176,
  total_productos: 49,
}

function json(data: unknown, status = 200): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => data,
  } as unknown as Response
}

function montarApp(ruta = '/') {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

function mockApi() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const metodo = (init?.method ?? 'GET').toUpperCase()

    if (path === '/api/auth/login' && metodo === 'POST') {
      const form = init?.body as URLSearchParams
      if (form.get('username') === 'sistema' && form.get('password') === 'admin123') {
        return json({ access_token: 'token-de-prueba' })
      }
      return json({ detail: 'Usuario o contraseña incorrectos' }, 401)
    }
    if (path === '/api/auth/me' && metodo === 'GET') {
      return json(USUARIO)
    }
    if (path === '/api/dashboard/' && metodo === 'GET') {
      return json(DASHBOARD)
    }
    return json({ detail: 'no encontrado' }, 404)
  })

  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('E2E: inicio de sesión y navegación protegida', () => {
  beforeEach(() => {
    localStorage.clear()
    mockApi()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sin sesión redirige al login', async () => {
    montarApp('/')

    expect(await screen.findByRole('button', { name: 'Entrar' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Casi Obsceno' })).toBeInTheDocument()
    expect(screen.getByText('Acceso al sistema')).toBeInTheDocument()
  })

  it('inicia sesión y llega al dashboard con los datos del resumen', async () => {
    montarApp('/login')

    await userEvent.type(await screen.findByLabelText('Usuario'), 'sistema')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'admin123')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(
      await screen.findByRole('heading', { name: 'Hola, Usuario Sistema' }),
    ).toBeInTheDocument()
    expect(await screen.findByText('Ventas de hoy')).toBeInTheDocument()
    expect(await screen.findByText(/3 facturas/)).toBeInTheDocument()
    expect(await screen.findByText('Ron Media')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Reportes' })).toBeInTheDocument()
    expect(localStorage.getItem('pos_token')).toBe('token-de-prueba')
  })

  it('muestra el error y no navega con credenciales inválidas', async () => {
    montarApp('/login')

    await userEvent.type(await screen.findByLabelText('Usuario'), 'sistema')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'incorrecta')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(
      await screen.findByText('Usuario o contraseña incorrectos'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeInTheDocument()
    expect(localStorage.getItem('pos_token')).toBeNull()
  })

  it('cerrar sesión vuelve al login', async () => {
    montarApp('/login')

    await userEvent.type(await screen.findByLabelText('Usuario'), 'sistema')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'admin123')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    await screen.findByRole('heading', { name: 'Hola, Usuario Sistema' })

    await userEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))

    expect(await screen.findByRole('button', { name: 'Entrar' })).toBeInTheDocument()
    expect(localStorage.getItem('pos_token')).toBeNull()
  })
})
