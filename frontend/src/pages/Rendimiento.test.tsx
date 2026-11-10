import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ResumenMetricas } from '../api/metricas'

const { obtenerResumenMock } = vi.hoisted(() => ({ obtenerResumenMock: vi.fn() }))

vi.mock('../api/metricas', () => ({ obtenerResumenMetricas: obtenerResumenMock }))

import { Rendimiento } from './Rendimiento'

const RESUMEN: ResumenMetricas = {
  horas: 24,
  generado: '2026-11-09T10:00:00-05:00',
  proceso: {
    proceso_desde: '2026-11-09T08:00:00-05:00',
    arranque_ms: 4200,
    en_bufer: 0,
    descartadas: 0,
  },
  servidor: {
    n: 40,
    p50: 120,
    p95: 3400,
    max: 9000,
    pct_lentas: 7.5,
    pct_db: 62,
    arranques_en_frio: 1,
    tras_inactividad: 2,
    conexiones_nuevas: 3,
    errores_5xx: 0,
  },
  cliente: { n: 30, p50: 400, p95: 7800, max: 30000, fallidas: 2 },
  diagnostico: ['3 de 40 peticiones del servidor (7.5 %) tardaron 2 s o más.'],
  rutas: [
    {
      ruta: 'GET /api/facturas/',
      n: 12,
      p50: 200,
      p95: 3400,
      max: 9000,
      db_prom: 150,
      pct_db: 70,
      consultas_prom: 8,
      errores_5xx: 0,
      cliente_p95: 8000,
    },
  ],
  por_hora: [{ hora: '2026-11-09 09:00', n: 40, p50: 120, p95: 3400 }],
  lentas: [],
}

beforeEach(() => {
  obtenerResumenMock.mockResolvedValue(RESUMEN)
})

describe('Rendimiento', () => {
  it('muestra el diagnóstico, las rutas y los tiempos del navegador', async () => {
    render(<Rendimiento />)

    expect(await screen.findByText(/tardaron 2 s o más/)).toBeInTheDocument()
    expect(screen.getByText('GET /api/facturas/')).toBeInTheDocument()
    expect(screen.getAllByText('3.4 s').length).toBeGreaterThan(0)
    expect(screen.getByText('8.0 s')).toBeInTheDocument()
    expect(screen.getByText(/No hubo peticiones de 2 s o más/)).toBeInTheDocument()
    expect(obtenerResumenMock).toHaveBeenCalledWith(24)
  })

  it('muestra el error si el servidor rechaza la consulta', async () => {
    obtenerResumenMock.mockRejectedValue(new Error('Sin permiso'))
    render(<Rendimiento />)
    expect(await screen.findByText('Sin permiso')).toBeInTheDocument()
  })
})
