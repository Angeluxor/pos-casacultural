import { useCallback, useEffect, useState } from 'react'
import type { Pagina } from '../api/types'

export type CargarPagina<T> = (params: {
  skip: number
  limit: number
  buscar: string
}) => Promise<Pagina<T>>

export function usePaginacion<T>(cargar: CargarPagina<T>, tamano = 25) {
  const [datos, setDatos] = useState<Pagina<T> | null>(null)
  const [skip, setSkip] = useState(0)
  const [buscar, setBuscar] = useState('')
  const [buscarAplicado, setBuscarAplicado] = useState('')
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const t = setTimeout(() => {
      setBuscarAplicado(buscar)
      setSkip(0)
    }, 300)
    return () => clearTimeout(t)
  }, [buscar])

  useEffect(() => {
    let cancelado = false
    setCargando(true)
    cargar({ skip, limit: tamano, buscar: buscarAplicado })
      .then((p) => {
        if (cancelado) return
        setDatos(p)
        setError('')
      })
      .catch((err) => {
        if (cancelado) return
        setError(err instanceof Error ? err.message : 'Error al cargar datos')
      })
      .finally(() => {
        if (!cancelado) setCargando(false)
      })
    return () => {
      cancelado = true
    }
  }, [cargar, skip, buscarAplicado, tamano, version])

  const recargar = useCallback(() => setVersion((v) => v + 1), [])

  return { datos, skip, setSkip, buscar, setBuscar, cargando, error, recargar, tamano }
}
