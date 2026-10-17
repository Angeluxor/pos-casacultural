import { describe, expect, it } from 'vitest'
import { compararValores, ordenarLista, type Accesores } from './orden'

type Fila = { nombre: string; total: number | null }

const ACCESORES: Accesores<Fila> = {
  nombre: (f) => f.nombre,
  total: (f) => f.total,
}

describe('compararValores', () => {
  it('compara números de forma numérica', () => {
    expect(compararValores(2, 10)).toBeLessThan(0)
  })

  it('compara texto sin distinguir mayúsculas y con números naturales', () => {
    expect(compararValores('árbol', 'Banana')).toBeLessThan(0)
    expect(compararValores('item2', 'item10')).toBeLessThan(0)
  })
})

describe('ordenarLista', () => {
  const filas: Fila[] = [
    { nombre: 'Carlos', total: 300 },
    { nombre: 'Ana', total: 100 },
    { nombre: 'Beto', total: 200 },
  ]

  it('ordena por texto ascendente', () => {
    const r = ordenarLista(filas, 'nombre', 'asc', ACCESORES)
    expect(r.map((f) => f.nombre)).toEqual(['Ana', 'Beto', 'Carlos'])
  })

  it('ordena por número descendente', () => {
    const r = ordenarLista(filas, 'total', 'desc', ACCESORES)
    expect(r.map((f) => f.total)).toEqual([300, 200, 100])
  })

  it('deja los valores vacíos al final en ambas direcciones', () => {
    const conVacio: Fila[] = [
      { nombre: 'Ana', total: null },
      { nombre: 'Beto', total: 500 },
    ]
    expect(ordenarLista(conVacio, 'total', 'asc', ACCESORES).map((f) => f.total)).toEqual([500, null])
    expect(ordenarLista(conVacio, 'total', 'desc', ACCESORES).map((f) => f.total)).toEqual([500, null])
  })

  it('no muta el arreglo original', () => {
    const copia = [...filas]
    ordenarLista(filas, 'nombre', 'asc', ACCESORES)
    expect(filas).toEqual(copia)
  })

  it('devuelve la lista tal cual si la columna no existe', () => {
    expect(ordenarLista(filas, 'inexistente', 'asc', ACCESORES)).toBe(filas)
  })
})
