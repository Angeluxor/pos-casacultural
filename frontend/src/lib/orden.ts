import { useCallback, useMemo, useState } from 'react'

export type Direccion = 'asc' | 'desc'

/**
 * Mapa de accesores: por cada clave de columna, una función que extrae el valor
 * a comparar de un elemento. Debe ser estable (constante de módulo o `useMemo`).
 */
export type Accesores<T> = Record<string, (item: T) => unknown>

function esVacio(valor: unknown): boolean {
  return valor === null || valor === undefined || valor === ''
}

/** Compara dos valores ya no vacíos: números como números, el resto como texto. */
export function compararValores(a: unknown, b: unknown): number {
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b), 'es', { numeric: true, sensitivity: 'base' })
}

/**
 * Devuelve una copia ordenada de la lista. Los valores vacíos van siempre al
 * final, sin importar la dirección.
 */
export function ordenarLista<T>(
  items: T[],
  campo: string | undefined,
  direccion: Direccion,
  accesores: Accesores<T>,
): T[] {
  if (!campo) return items
  const acc = accesores[campo]
  if (!acc) return items
  const signo = direccion === 'desc' ? -1 : 1
  return [...items].sort((x, y) => {
    const a = acc(x)
    const b = acc(y)
    const aVacio = esVacio(a)
    const bVacio = esVacio(b)
    if (aVacio || bVacio) return aVacio && bVacio ? 0 : aVacio ? 1 : -1
    return signo * compararValores(a, b)
  })
}

/**
 * Orden para listas paginadas en el servidor: solo guarda la columna y la
 * dirección; la consulta se resuelve en el backend para abarcar todo el
 * conjunto, no únicamente la página visible.
 */
export function useOrdenServidor(inicial?: string) {
  const [orden, setOrden] = useState<string | undefined>(inicial)
  const [direccion, setDireccion] = useState<Direccion>('asc')

  const alternar = useCallback(
    (campo: string) => {
      if (campo === orden) {
        setDireccion((d) => (d === 'asc' ? 'desc' : 'asc'))
      } else {
        setOrden(campo)
        setDireccion('asc')
      }
    },
    [orden],
  )

  return { orden, direccion, alternar }
}

/**
 * Orden para listas locales (modales y reportes): ordena el arreglo en memoria.
 */
export function useOrdenLocal<T>(
  items: T[],
  accesores: Accesores<T>,
  inicial?: { campo: string; direccion?: Direccion },
) {
  const [orden, setOrden] = useState<string | undefined>(inicial?.campo)
  const [direccion, setDireccion] = useState<Direccion>(inicial?.direccion ?? 'asc')

  const alternar = useCallback(
    (campo: string) => {
      if (campo === orden) {
        setDireccion((d) => (d === 'asc' ? 'desc' : 'asc'))
      } else {
        setOrden(campo)
        setDireccion('asc')
      }
    },
    [orden],
  )

  const ordenados = useMemo(
    () => ordenarLista(items, orden, direccion, accesores),
    [items, orden, direccion, accesores],
  )

  return { items: ordenados, orden, direccion, alternar }
}
