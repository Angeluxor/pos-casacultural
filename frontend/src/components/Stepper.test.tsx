import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Stepper } from './Stepper'

describe('Stepper', () => {
  it('aumenta y disminuye la cantidad', async () => {
    const onCambiar = vi.fn()
    render(<Stepper valor={2} onCambiar={onCambiar} />)

    await userEvent.click(screen.getByRole('button', { name: 'Aumentar cantidad' }))
    expect(onCambiar).toHaveBeenCalledWith(3)

    await userEvent.click(screen.getByRole('button', { name: 'Disminuir cantidad' }))
    expect(onCambiar).toHaveBeenCalledWith(1)
  })

  it('deshabilita Disminuir al llegar al mínimo', () => {
    render(<Stepper valor={1} min={1} onCambiar={() => {}} />)
    expect(screen.getByRole('button', { name: 'Disminuir cantidad' })).toBeDisabled()
  })

  it('deshabilita Aumentar al llegar al máximo', () => {
    render(<Stepper valor={5} max={5} onCambiar={() => {}} />)
    expect(screen.getByRole('button', { name: 'Aumentar cantidad' })).toBeDisabled()
  })

  it('acota al máximo los valores escritos', () => {
    const onCambiar = vi.fn()
    render(<Stepper valor={3} min={1} max={5} onCambiar={onCambiar} />)

    fireEvent.change(screen.getByLabelText('Cantidad de cantidad'), {
      target: { value: '9' },
    })

    expect(onCambiar).toHaveBeenLastCalledWith(5)
  })

  it('acota al mínimo los valores escritos', () => {
    const onCambiar = vi.fn()
    render(<Stepper valor={3} min={1} max={5} onCambiar={onCambiar} />)

    fireEvent.change(screen.getByLabelText('Cantidad de cantidad'), {
      target: { value: '0' },
    })

    expect(onCambiar).toHaveBeenLastCalledWith(1)
  })
})
