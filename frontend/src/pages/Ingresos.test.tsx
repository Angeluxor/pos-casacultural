import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  crearIngresoMock,
  paginaIngresosMock,
  listarProductosMock,
  listarProveedoresMock,
  editarIngresoMock,
  anularIngresoMock,
} = vi.hoisted(() => ({
  crearIngresoMock: vi.fn(),
  paginaIngresosMock: vi.fn(),
  listarProductosMock: vi.fn(),
  listarProveedoresMock: vi.fn(),
  editarIngresoMock: vi.fn(),
  anularIngresoMock: vi.fn(),
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
    editarIngreso: editarIngresoMock,
    anularIngreso: anularIngresoMock,
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
    editarIngresoMock.mockReset()
    anularIngresoMock.mockReset()
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

  it('permite corregir la forma de pago y anular un ingreso', async () => {
    const ingreso = {
      id: 5,
      fecha: '2026-10-20T15:00:00-05:00',
      usuario_id: 1,
      turno_caja_id: 2,
      fuente_pago: 'Caja activa',
      proveedor_id: 3,
      proveedor: 'La Fría',
      forma_pago: 'Efectivo',
      total: 50000,
      estado: 'Completo',
      justificacion: null,
      observacion: null,
      suma_items: 50000,
      pagado: true,
      estado_pago: 'Pagado',
      fecha_pago: null,
      pagado_por_id: null,
      pagado_por_nombre: null,
      forma_pago_pago: 'Efectivo',
      anulada: false,
      motivo_anulacion: null,
      fecha_anulacion: null,
      anulada_por_id: null,
      anulada_por_nombre: null,
      items: [
        {
          id: 11,
          ingreso_id: 5,
          tipo: 'Producto',
          producto_id: 7,
          concepto: null,
          producto_nombre: 'Harina',
          cantidad: 10,
          cantidad_formatos: null,
          unidades_por_formato: null,
          costo_formato: null,
          costo_unitario: 5000,
          valor: 50000,
        },
      ],
    }
    paginaIngresosMock.mockResolvedValue({
      items: [ingreso],
      total: 1,
      skip: 0,
      limit: 20,
    })
    editarIngresoMock.mockResolvedValue({ ...ingreso, forma_pago: 'Transferencia' })
    anularIngresoMock.mockResolvedValue({
      ...ingreso,
      anulada: true,
      estado_pago: 'No aplica',
      motivo_anulacion: 'Error de digitación',
    })

    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <Ingresos />
      </MemoryRouter>,
    )

    await user.click(await screen.findByRole('button', { name: 'Ver' }))
    // El detalle usa el nombre del producto, no un «Producto #id».
    expect(await screen.findByText('Harina')).toBeInTheDocument()
    expect(screen.queryByText('Producto #7')).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Forma de pago'), 'Transferencia')
    await user.click(screen.getByRole('button', { name: 'Guardar cambios' }))

    await waitFor(() =>
      expect(editarIngresoMock).toHaveBeenCalledWith(
        5,
        expect.objectContaining({ forma_pago: 'Transferencia' }),
      ),
    )

    await user.click(screen.getByRole('button', { name: 'Anular ingreso' }))
    await user.type(
      screen.getByLabelText('Motivo de la anulación'),
      'Error de digitación',
    )
    await user.click(screen.getByRole('button', { name: 'Confirmar anulación' }))

    await waitFor(() =>
      expect(anularIngresoMock).toHaveBeenCalledWith(5, 'Error de digitación'),
    )
    expect(await screen.findByText('Anulada')).toBeInTheDocument()
  })

  it('calcula el costo unitario al comprar por caja o paquete', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <Ingresos />
      </MemoryRouter>,
    )

    await user.click(await screen.findByRole('button', { name: '+ Nuevo ingreso' }))
    await user.selectOptions(screen.getByLabelText('Fuente de pago'), 'Balance general')
    await user.type(screen.getByLabelText('Total del ingreso'), '48')
    await user.selectOptions(await screen.findByLabelText('Producto'), '7')

    await user.clear(screen.getByLabelText('Unidades por caja/paquete'))
    await user.type(screen.getByLabelText('Unidades por caja/paquete'), '12')
    await user.clear(screen.getByLabelText('Cantidad de cajas/paquetes'))
    await user.type(screen.getByLabelText('Cantidad de cajas/paquetes'), '2')
    await user.type(screen.getByLabelText('Costo por caja/paquete'), '24')

    expect(await screen.findByText(/24 unidades/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Registrar ingreso' }))

    await waitFor(() => expect(crearIngresoMock).toHaveBeenCalledTimes(1))
    expect(crearIngresoMock).toHaveBeenCalledWith(
      expect.objectContaining({
        items: [
          expect.objectContaining({
            cantidad: 24,
            cantidad_formatos: 2,
            unidades_por_formato: 12,
            costo_formato: 24,
            costo_unitario: 2,
          }),
        ],
      }),
    )
  })
})
