import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { crearIngresoMock, paginaIngresosMock, listarProductosMock, listarProveedoresMock } =
  vi.hoisted(() => ({
    crearIngresoMock: vi.fn(),
    paginaIngresosMock: vi.fn(),
    listarProductosMock: vi.fn(),
    listarProveedoresMock: vi.fn(),
  }))

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ tienePermiso: () => true }),
}))

vi.mock('../api/productos', () => ({
  listarProductos: listarProductosMock,
}))

vi.mock('../api/proveedores', () => ({
  listarProveedores: listarProveedoresMock,
  crearProveedor: vi.fn(),
}))

vi.mock('../api/ingresos', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/ingresos')>()
  return {
    ...actual,
    paginaIngresos: paginaIngresosMock,
    crearIngreso: crearIngresoMock,
  }
})

import { Ingresos } from './Ingresos'

describe('Ingresos', () => {
  beforeEach(() => {
    paginaIngresosMock.mockReset().mockResolvedValue({
      items: [],
      total: 0,
      skip: 0,
      limit: 20,
    })
    listarProductosMock.mockReset().mockResolvedValue([
      { id: 7, codigo: 'P001', nombre: 'Harina', precio: 6000, stock: 0 },
    ])
    listarProveedoresMock.mockReset().mockResolvedValue([
      { id: 3, nombre: 'La Fría', documento: null, celular: null, correo: null },
    ])
    crearIngresoMock.mockReset().mockResolvedValue({})
  })

  it('permite registrar un ingreso en balance general sin caja', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <Ingresos />
      </MemoryRouter>,
    )

    await user.click(await screen.findByRole('button', { name: '+ Nuevo ingreso' }))

    await user.selectOptions(screen.getByLabelText('Fuente de pago'), 'Balance general')
    expect(screen.getByText(/No requiere caja abierta/)).toBeInTheDocument()

    await user.type(screen.getByLabelText('Total del ingreso'), '10000')
    await user.selectOptions(await screen.findByLabelText('Proveedor'), '3')
    await user.selectOptions(await screen.findByLabelText('Producto'), '7')
    await user.click(screen.getByRole('button', { name: 'Registrar ingreso' }))

    await waitFor(() => expect(crearIngresoMock).toHaveBeenCalledTimes(1))
    expect(crearIngresoMock).toHaveBeenCalledWith(
      expect.objectContaining({
        fuente_pago: 'Balance general',
        forma_pago: 'Efectivo',
        total: 10000,
        proveedor_id: 3,
      }),
    )
  })
})
