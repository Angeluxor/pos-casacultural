import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { CampoPassword } from './CampoPassword'

describe('CampoPassword', () => {
  it('oculta la contraseña por defecto', () => {
    render(<CampoPassword aria-label="Contraseña" defaultValue="secreta" />)
    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('type', 'password')
  })

  it('el ojito muestra y vuelve a ocultar lo digitado', async () => {
    render(<CampoPassword aria-label="Contraseña" defaultValue="secreta" />)
    const campo = screen.getByLabelText('Contraseña')

    await userEvent.click(screen.getByRole('button', { name: 'Mostrar contraseña' }))
    expect(campo).toHaveAttribute('type', 'text')
    expect(campo).toHaveValue('secreta')

    await userEvent.click(screen.getByRole('button', { name: 'Ocultar contraseña' }))
    expect(campo).toHaveAttribute('type', 'password')
  })

  it('no envía el formulario al tocar el ojito', async () => {
    let enviado = 0
    render(
      <form
        onSubmit={(e) => {
          e.preventDefault()
          enviado += 1
        }}
      >
        <CampoPassword aria-label="Contraseña" defaultValue="secreta" />
      </form>,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Mostrar contraseña' }))
    expect(enviado).toBe(0)
  })
})
