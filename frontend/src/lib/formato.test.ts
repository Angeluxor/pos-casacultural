import { describe, expect, it } from 'vitest'
import { formatoFecha, moneda } from './formato'

describe('moneda', () => {
  it('formatea el valor en pesos colombianos', () => {
    expect(moneda.format(1500)).toContain('1.500')
  })

  it('no muestra centavos', () => {
    expect(moneda.format(1999.9)).not.toContain(',')
  })
})

describe('formatoFecha', () => {
  it('devuelve una cadena no vacía a partir de un ISO', () => {
    const texto = formatoFecha('2026-01-15T10:30:00.000Z')
    expect(texto.length).toBeGreaterThan(0)
  })
})
