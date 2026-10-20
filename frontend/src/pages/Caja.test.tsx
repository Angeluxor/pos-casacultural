import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { TurnoCaja } from '../api/caja'

const { obtenerCajaActivaMock, obtenerMovimientosMock } = vi.hoisted(() => ({
  obtenerCajaActivaMock: vi.fn(),
  obtenerMovimientosMock: vi.fn(),
}))

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ tienePermiso: () => true }),
}))

vi.mock('../api/caja', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/caja')>()
  return {
    ...actual,
    abrirCaja: vi.fn(),
    cerrarCaja: vi.fn(),
    listarTurnos: vi.fn(),
    obtenerCajaActiva: obtenerCajaActivaMock,
    obtenerFacturasPendientes: vi.fn(),
    obtenerMovimientos: obtenerMovimientosMock,
    obtenerResumenVentasTurno: vi.fn(),
    registrarMovimiento: vi.fn(),
  }
})

import { Caja } from './Caja'

const TURNO: TurnoCaja = {
  id: 1,
  usuario_apertura_id: 1,
  usuario_cierre_id: null,
  fecha_apertura: '2026-10-19T08:00:00-05:00',
  fecha_cierre: null,
  saldo_inicial_efectivo: 50000,
  saldo_inicial_banco: 0,
  saldo_final_real_efectivo: null,
  saldo_final_real_banco: null,
  abierta: true,
}

beforeEach(() => {
  obtenerCajaActivaMock.mockResolvedValue(TURNO)
  obtenerMovimientosMock.mockResolvedValue([])
})

describe('Caja', () => {
  it('permite elegir la categoría del movimiento según el tipo', async () => {
    render(
      <MemoryRouter>
        <Caja />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Turno #1 abierto')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Registrar movimiento' }))

    const categoria = screen.getByLabelText('Categoría')
    expect(categoria).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Aporte cultural' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Otro ingreso' })).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText('Tipo'), 'Salida')

    expect(screen.getByRole('option', { name: 'Arriendo' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Otro gasto' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Aporte cultural' })).not.toBeInTheDocument()
  })

  it('muestra el resumen por categoría de los movimientos del turno', async () => {
    obtenerMovimientosMock.mockResolvedValue([
      {
        id: 1,
        turno_caja_id: 1,
        usuario_id: 1,
        fecha: '2026-10-19T09:00:00-05:00',
        tipo: 'Entrada',
        referencia: 'Aporte cultural – Evento',
        forma_pago: 'Efectivo',
        monto: 20000,
        categoria: 'Aporte cultural',
        observacion: null,
      },
      {
        id: 2,
        turno_caja_id: 1,
        usuario_id: 1,
        fecha: '2026-10-19T10:00:00-05:00',
        tipo: 'Salida',
        referencia: 'Arriendo de octubre',
        forma_pago: 'Transferencia',
        monto: 15000,
        categoria: 'Arriendo',
        observacion: null,
      },
    ])

    render(
      <MemoryRouter>
        <Caja />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Resumen por categoría')).toBeInTheDocument()
    expect(screen.getAllByText('Aporte cultural').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Arriendo').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/20\.000/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/15\.000/).length).toBeGreaterThan(0)
  })
})
