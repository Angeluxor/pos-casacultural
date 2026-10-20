import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { paginaMock, actualizarMock, capturaMock } = vi.hoisted(() => ({
  paginaMock: vi.fn(),
  actualizarMock: vi.fn(),
  capturaMock: vi.fn(),
}))

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({
    usuario: { id: 1, nombre: 'Admin', rol: 'Admin' },
    tienePermiso: () => true,
  }),
}))

vi.mock('../api/feedback', () => ({
  paginaFeedback: paginaMock,
  actualizarFeedback: actualizarMock,
  obtenerCapturaFeedback: capturaMock,
}))

import { Feedback } from './Feedback'
import type { Feedback as FeedbackItem } from '../api/feedback'

const ITEM: FeedbackItem = {
  id: 1,
  tipo: 'Idea',
  comentario: 'Sería útil ver el total del día en la caja.',
  contexto: { ruta: '/caja', version: '1.0.0' },
  estado: 'Nuevo',
  prioridad: 'Media',
  etiquetas: [],
  usuario_id: 2,
  usuario_nombre: 'Cajero',
  responsable_id: null,
  responsable_nombre: null,
  tiene_captura: false,
  captura_mime: null,
  captura_nombre: null,
  notas_internas: null,
  creado_en: '2026-10-19T10:00:00-05:00',
  actualizado_en: '2026-10-19T10:00:00-05:00',
  resuelto_en: null,
}

describe('Feedback administrativo', () => {
  beforeEach(() => {
    paginaMock.mockReset().mockResolvedValue({
      items: [ITEM],
      total: 1,
      skip: 0,
      limit: 20,
    })
    actualizarMock.mockReset().mockResolvedValue({
      ...ITEM,
      estado: 'Resuelto',
    })
    capturaMock.mockReset()
  })

  it('lista y permite gestionar estado, etiquetas y notas', async () => {
    const user = userEvent.setup()
    render(<Feedback />)

    expect(
      await screen.findByText('Sería útil ver el total del día en la caja.'),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Gestionar' }))
    const dialogo = screen.getByRole('dialog', { name: 'Detalle del feedback' })

    await user.selectOptions(within(dialogo).getByLabelText('Estado'), 'Resuelto')
    await user.type(
      within(dialogo).getByLabelText('Etiquetas (separadas por coma)'),
      'ui, mobile',
    )
    await user.type(
      within(dialogo).getByLabelText('Notas internas (solo administración)'),
      'Revisado con el equipo',
    )
    await user.click(within(dialogo).getByRole('button', { name: 'Guardar cambios' }))

    await waitFor(() => expect(actualizarMock).toHaveBeenCalledTimes(1))
    expect(actualizarMock).toHaveBeenCalledWith(1, {
      estado: 'Resuelto',
      prioridad: 'Media',
      etiquetas: ['ui', 'mobile'],
      notas_internas: 'Revisado con el equipo',
      responsable_id: null,
    })
    expect(paginaMock).toHaveBeenCalledTimes(2)
  })
})
