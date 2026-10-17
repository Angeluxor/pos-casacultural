import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Pagina } from '../api/types'
import { usePaginacion } from './usePaginacion'

function pagina<T>(items: T[], total: number): Pagina<T> {
  return { items, total, skip: 0, limit: 25 }
}

describe('usePaginacion', () => {
  it('carga la primera página al montar', async () => {
    const cargar = vi.fn().mockResolvedValue(pagina([1, 2, 3], 3))
    const { result } = renderHook(() => usePaginacion<number>(cargar))

    await waitFor(() => expect(result.current.cargando).toBe(false))
    expect(cargar).toHaveBeenCalledTimes(1)
    expect(cargar).toHaveBeenCalledWith({
      skip: 0,
      limit: 25,
      buscar: '',
      desde: undefined,
      hasta: undefined,
    })
    expect(result.current.datos?.items).toEqual([1, 2, 3])
    expect(result.current.error).toBe('')
  })

  it('expone el error cuando la carga falla', async () => {
    const cargar = vi.fn().mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => usePaginacion<number>(cargar))

    await waitFor(() => expect(result.current.cargando).toBe(false))
    expect(result.current.error).toBe('boom')
    expect(result.current.datos).toBeNull()
  })

  it('aplica el filtro de búsqueda tras el debounce', async () => {
    const cargar = vi.fn().mockResolvedValue(pagina([], 0))
    const { result } = renderHook(() => usePaginacion<number>(cargar))
    await waitFor(() => expect(result.current.cargando).toBe(false))

    act(() => result.current.setBuscar('leche'))

    await waitFor(() =>
      expect(cargar).toHaveBeenLastCalledWith(
        expect.objectContaining({ buscar: 'leche', skip: 0 }),
      ),
    )
  })

  it('recargar fuerza una nueva consulta', async () => {
    const cargar = vi.fn().mockResolvedValue(pagina([], 0))
    const { result } = renderHook(() => usePaginacion<number>(cargar))
    await waitFor(() => expect(result.current.cargando).toBe(false))

    act(() => result.current.recargar())

    await waitFor(() => expect(cargar).toHaveBeenCalledTimes(2))
  })
})
