import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  resumenMock,
  recetasMock,
  manualesMock,
  insumosMock,
  historialMock,
} = vi.hoisted(() => ({
  resumenMock: vi.fn(),
  recetasMock: vi.fn(),
  manualesMock: vi.fn(),
  insumosMock: vi.fn(),
  historialMock: vi.fn(),
}))

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ tienePermiso: () => true }),
}))

vi.mock('../api/costos', () => ({
  listarResumenCostos: resumenMock,
  listarRecetas: recetasMock,
  listarCostosManuales: manualesMock,
  listarInsumos: insumosMock,
  historialProducto: historialMock,
  crearCostoManual: vi.fn(),
  guardarReceta: vi.fn(),
  eliminarReceta: vi.fn(),
  eliminarCostoManual: vi.fn(),
}))

import { Costos } from './Costos'

const RESUMEN = [
  {
    producto_id: 1,
    codigo: 'CAF',
    nombre: 'Café',
    precio: 10000,
    stock: 5,
    misma_unidad_compra_venta: true,
    tiene_receta: false,
    mostrar_cmv: true,
    costo_vigente: 5000,
    origen_costo: 'Costo promedio',
    costo_completo: true,
    faltantes: [],
    mejor_precio_6s: 4000,
    mejor_proveedor: 'Barato',
    mejor_fecha: '2026-10-10T10:00:00-05:00',
    mejor_origen: 'Compra',
    variacion_6s: 25,
    puntos_6s: 2,
    cmv_pct: 50,
    margen: 5000,
    margen_pct: 50,
  },
]

const RECETAS = [
  {
    producto_id: 2,
    codigo: 'ARE',
    nombre: 'Arepa',
    precio: 6000,
    rendimiento: 2,
    notas: null,
    costo_total: 4000,
    costo_unitario: 2000,
    completo: true,
    faltantes: [],
    cmv_pct: 33.33,
    margen: 4000,
    margen_pct: 66.67,
    items: [
      {
        producto_id: 1,
        codigo: 'CAF',
        nombre: 'Café',
        cantidad: 2,
        costo_unitario: 2000,
        subtotal: 4000,
        origen: 'Costo promedio',
      },
    ],
  },
]

const MANUALES = [
  {
    id: 1,
    producto_id: 1,
    producto_codigo: 'CAF',
    producto_nombre: 'Café',
    fecha: '2026-10-18T00:00:00-05:00',
    costo_unitario: 3000,
    nota: 'Estimado',
    usuario_id: 1,
    usuario_nombre: 'Admin',
  },
]

const INSUMOS = [
  {
    producto_id: 1,
    codigo: 'CAF',
    nombre: 'Café',
    precio: 10000,
    costo: 5000,
    origen: 'Costo promedio',
    tiene_receta: false,
    completo: true,
    faltantes: [],
  },
  {
    producto_id: 2,
    codigo: 'ARE',
    nombre: 'Arepa',
    precio: 6000,
    costo: 2000,
    origen: 'Receta',
    tiene_receta: true,
    completo: true,
    faltantes: [],
  },
]

describe('Costos', () => {
  beforeEach(() => {
    resumenMock.mockReset().mockResolvedValue(RESUMEN)
    recetasMock.mockReset().mockResolvedValue(RECETAS)
    manualesMock.mockReset().mockResolvedValue(MANUALES)
    insumosMock.mockReset().mockResolvedValue(INSUMOS)
    historialMock.mockReset().mockResolvedValue([])
  })

  it('muestra el resumen y el histórico de costos', async () => {
    render(<Costos />)

    expect(await screen.findByText('Café')).toBeInTheDocument()
    expect(screen.getByText('$ 4.000')).toBeInTheDocument() // mejor precio
    expect(screen.getByText('+25.0%')).toBeInTheDocument()
    expect(screen.getByText('50.0% del precio')).toBeInTheDocument()
    expect(screen.getByText('Con costo')).toBeInTheDocument()
    expect(screen.getByText('Qué muestra el histórico')).toBeInTheDocument()
  })

  it('lista las preparaciones con su costo', async () => {
    const user = userEvent.setup()
    render(<Costos />)
    await screen.findByText('Café')

    await user.click(screen.getByRole('button', { name: 'Preparaciones' }))

    expect(await screen.findByText('Arepa')).toBeInTheDocument()
    expect(screen.getByText('Completa')).toBeInTheDocument()
    expect(screen.getByText('$ 2.000')).toBeInTheDocument()
    expect(screen.getByText('Qué son las preparaciones')).toBeInTheDocument()
  })

  it('lista los costos manuales', async () => {
    const user = userEvent.setup()
    render(<Costos />)
    await screen.findByText('Café')

    await user.click(screen.getByRole('button', { name: 'Costos manuales' }))

    expect(await screen.findByText('Estimado')).toBeInTheDocument()
    expect(screen.getByText('Admin')).toBeInTheDocument()
    expect(screen.getByText('Qué son los costos manuales')).toBeInTheDocument()
  })
})
