import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { paginaMock, crearMock } = vi.hoisted(() => ({
  paginaMock: vi.fn(),
  crearMock: vi.fn(),
}))

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ tienePermiso: () => true }),
}))

vi.mock('../api/proveedores', () => ({
  paginaProveedores: paginaMock,
  crearProveedor: crearMock,
  actualizarProveedor: vi.fn(),
  eliminarProveedor: vi.fn(),
}))

import { Proveedores } from './Proveedores'

describe('Proveedores', () => {
  beforeEach(() => {
    paginaMock.mockReset().mockResolvedValue({
      items: [
        {
          id: 1,
          nombre: 'Distribuidora La Fría',
          documento: '900123456-7',
          celular: '3001234567',
          correo: 'compras@lafria.co',
        },
      ],
      total: 1,
      skip: 0,
      limit: 25,
    })
    crearMock.mockReset().mockResolvedValue({
      id: 2,
      nombre: 'Fletes del Norte',
      documento: null,
      celular: null,
      correo: null,
    })
  })

  it('lista los proveedores registrados', async () => {
    render(<Proveedores />)

    expect(await screen.findByText('Distribuidora La Fría')).toBeInTheDocument()
    expect(screen.getByText('900123456-7')).toBeInTheDocument()
    expect(screen.getByText('1 proveedores registrados')).toBeInTheDocument()
  })

  it('crea un proveedor desde el formulario', async () => {
    const user = userEvent.setup()
    render(<Proveedores />)

    await user.click(await screen.findByRole('button', { name: '+ Nuevo proveedor' }))
    await user.type(screen.getByLabelText('Nombre'), 'Fletes del Norte')
    await user.type(screen.getByLabelText('Documento / NIT'), '  ')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    await waitFor(() => expect(crearMock).toHaveBeenCalledTimes(1))
    expect(crearMock).toHaveBeenCalledWith({
      nombre: 'Fletes del Norte',
      documento: null,
      celular: null,
      correo: null,
    })
  })
})
