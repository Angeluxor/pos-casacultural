import { describe, expect, it } from 'vitest'
import { resolverApiUrl } from './client'

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
