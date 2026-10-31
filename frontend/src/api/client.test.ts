import { describe, expect, it } from 'vitest'
import { ApiError, esErrorRed, esErrorTiempo, resolverApiUrl } from './client'

describe('resolverApiUrl', () => {
  it('usa la URL configurada en producción', () => {
    expect(
      resolverApiUrl('https://pos-casacultural-api.onrender.com/', 'pos-casacultural.vercel.app'),
    ).toBe('https://pos-casacultural-api.onrender.com')
  })

  it('usa el proxy relativo en los previews de Vercel', () => {
    expect(
      resolverApiUrl(
        'https://pos-casacultural-api.onrender.com',
        'pos-casacultural-git-collage-identidad-angeluxor.vercel.app',
      ),
    ).toBe('')
  })

  it('mantiene la URL configurada en desarrollo local', () => {
    expect(resolverApiUrl('http://localhost:8000', 'localhost')).toBe('http://localhost:8000')
  })
})

describe('clasificación de errores de conexión', () => {
  it('un timeout se distingue de un fallo de red y sigue siendo reintentable', () => {
    const error = new ApiError(0, 'El servidor tardó demasiado', true)
    expect(esErrorTiempo(error)).toBe(true)
    // Se puede encolar/reintentar, pero la UI no debe decir "sin conexión".
    expect(esErrorRed(error)).toBe(true)
  })

  it('un fallo de conexión sí es un error de red', () => {
    expect(esErrorRed(new ApiError(0, 'No se pudo conectar'))).toBe(true)
    expect(esErrorTiempo(new ApiError(0, 'No se pudo conectar'))).toBe(false)
  })

  it('un 5xx es reintentable como red', () => {
    expect(esErrorRed(new ApiError(503, 'No disponible'))).toBe(true)
  })

  it('un 4xx no se trata como caída de red', () => {
    expect(esErrorRed(new ApiError(400, 'Datos inválidos'))).toBe(false)
  })
})
