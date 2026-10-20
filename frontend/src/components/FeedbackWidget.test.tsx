import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { crearMock } = vi.hoisted(() => ({
  crearMock: vi.fn(),
}))

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({
    usuario: { id: 7, nombre: 'Ana', rol: 'Cajero' },
    tienePermiso: (permiso: string) => permiso === 'feedback.crear',
  }),
}))

vi.mock('../api/feedback', () => ({
  crearFeedback: crearMock,
}))

vi.mock('html-to-image', () => ({
  toJpeg: vi.fn(),
}))

import { FeedbackWidget } from './FeedbackWidget'

describe('FeedbackWidget', () => {
  beforeEach(() => {
    crearMock.mockReset().mockResolvedValue({ id: 42 })
    window.history.pushState({}, '', '/caja?turno=1')
  })

  it('envía el comentario con contexto técnico automático', async () => {
    const user = userEvent.setup()
    render(<FeedbackWidget />)

    await user.click(screen.getByRole('button', { name: 'Abrir feedback' }))
    await user.type(
      screen.getByLabelText('Comentario'),
      'La caja no muestra el total del turno.',
    )
    await user.click(screen.getByRole('button', { name: 'Enviar feedback' }))

    await waitFor(() => expect(crearMock).toHaveBeenCalledTimes(1))
    const enviado = crearMock.mock.calls[0][0]
    expect(enviado.tipo).toBe('Idea')
    expect(enviado.comentario).toBe('La caja no muestra el total del turno.')
    expect(enviado.contexto.ruta).toBe('/caja')
    expect(enviado.contexto.rol).toBe('Cajero')
    expect(enviado.contexto.version).toBeTruthy()
    expect(enviado.captura_base64).toBeUndefined()

    expect(await screen.findByRole('status')).toHaveTextContent('Referencia #42')
  })
})
