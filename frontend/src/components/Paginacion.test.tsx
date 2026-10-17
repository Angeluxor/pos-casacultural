import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Paginacion } from './Paginacion'

describe('Paginacion', () => {
  it('no renderiza nada si hay una sola página', () => {
    const { container } = render(
      <Paginacion total={10} skip={0} limit={25} onCambiar={() => {}} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('muestra la página actual y el total de registros', () => {
    render(<Paginacion total={100} skip={25} limit={25} onCambiar={() => {}} />)
    expect(screen.getByText('de 4 · 100 registros')).toBeInTheDocument()
    expect(screen.getByLabelText('Número de página')).toHaveValue(2)
  })

  it('deshabilita Anterior en la primera página', () => {
    render(<Paginacion total={100} skip={0} limit={25} onCambiar={() => {}} />)
    expect(screen.getByRole('button', { name: '← Anterior' })).toBeDisabled()
  })

  it('llama a onCambiar con la página siguiente', async () => {
    const onCambiar = vi.fn()
    render(<Paginacion total={100} skip={0} limit={25} onCambiar={onCambiar} />)

    await userEvent.click(screen.getByRole('button', { name: 'Siguiente →' }))

    expect(onCambiar).toHaveBeenCalledWith(25)
  })

  it('salta a una página concreta desde el formulario', () => {
    const onCambiar = vi.fn()
    render(<Paginacion total={100} skip={0} limit={25} onCambiar={onCambiar} />)

    const input = screen.getByLabelText('Número de página')
    fireEvent.change(input, { target: { value: '3' } })
    fireEvent.submit(input.closest('form') as HTMLFormElement)

    expect(onCambiar).toHaveBeenCalledWith(50)
  })
})
