import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { BalanceGeneral } from '../api/balance'

const { obtenerBalanceMock } = vi.hoisted(() => ({
  obtenerBalanceMock: vi.fn(),
}))

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ tienePermiso: () => true }),
}))

vi.mock('../api/balance', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/balance')>()
  return {
    ...actual,
    obtenerBalance: obtenerBalanceMock,
    descargarBalance: vi.fn(),
  }
})

import { Balance } from './Balance'

const DATOS: BalanceGeneral = {
  generado: '2026-10-19T10:00:00-05:00',
  fecha_corte: '2026-10-19T10:00:00-05:00',
  caja: {
    efectivo: 50000,
    banco: 100000,
    reservado: 30000,
    disponible: 120000,
    abierta: true,
    turno_id: 1,
    origen: 'Turno abierto #1',
  },
  activos: {
    efectivo: 50000,
    banco: 100000,
    reservado: 30000,
    disponible: 120000,
    inventario: 20000,
    cartera: 10000,
    total: 180000,
  },
  pasivos: { cuentas_por_pagar: 5000, total: 5000 },
  patrimonio: { total: 75000 },
  resultados: {
    desde: '2026-10-01',
    hasta: '2026-10-19',
    ventas_netas: 40000,
    costo_ventas: 15000,
    utilidad_bruta: 25000,
    gastos: 5000,
    gastos_caja: 3000,
    gastos_otros: 2000,
    utilidad: 20000,
    margen: 50,
    facturas: 2,
    productos_vendidos_sin_costo: 0,
  },
  inventario: [
    {
      producto_id: 7,
      codigo: 'P001',
      nombre: 'Producto de prueba',
      stock: 2,
      costo_unitario: 10000,
      valor: 20000,
      origen: 'Costo promedio',
    },
  ],
  cuentas_por_pagar: [
    {
      ingreso_id: 9,
      fecha: '2026-10-10T09:00:00-05:00',
      proveedor: 'Transportes',
      total: 5000,
      estado_ingreso: 'Completo',
      forma_pago_pago: null,
      fecha_pago: null,
    },
  ],
  bolsillos: [
    {
      id: 1,
      nombre: 'Arriendo',
      descripcion: 'Reserva mensual',
      reservado: 30000,
      fecha_creacion: '2026-10-01T09:00:00-05:00',
    },
  ],
  total_reservado: 30000,
  productos_sin_costo: 0,
  valor_inventario_precio_venta: 0,
  compras_credito_pendientes: 1,
}

describe('Balance', () => {
  beforeEach(() => {
    obtenerBalanceMock.mockReset()
    obtenerBalanceMock.mockResolvedValue(DATOS)
  })

  it('muestra el corte, las cuentas por pagar y el enlace para pagar', async () => {
    render(
      <MemoryRouter>
        <Balance />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Ecuación del balance')).toBeInTheDocument()
    expect(screen.getByText('Transportes')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Pagar' })).toHaveAttribute(
      'href',
      '/ingresos?pagar=9',
    )
    expect(screen.getByText('Producto de prueba')).toBeInTheDocument()
    expect(screen.getByText('Turno abierto #1')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Bolsillos de gastos vitales' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Arriendo')).toBeInTheDocument()
    expect(screen.getByText('Reserva mensual')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Aportar' })).toBeInTheDocument()
    expect(obtenerBalanceMock).toHaveBeenCalledTimes(1)
  })
})
