import { beforeAll, describe, expect, it, vi } from 'vitest'
import { iniciarCapturaInstalacion, instalarApp, puedeInstalar } from './instalarApp'

function eventoInstalar(prompt = vi.fn(async () => {})) {
  const evento = new Event('beforeinstallprompt', { cancelable: true }) as Event & {
    prompt: () => Promise<void>
    userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
  }
  evento.prompt = prompt
  evento.userChoice = Promise.resolve({ outcome: 'accepted' })
  return evento
}

beforeAll(() => {
  iniciarCapturaInstalacion()
})

describe('instalación de la app', () => {
  it('no ofrece instalar hasta que el navegador emite el evento', () => {
    expect(puedeInstalar()).toBe(false)
  })

  it('captura el evento, evita el banner automático y habilita el botón', () => {
    const evento = eventoInstalar()
    window.dispatchEvent(evento)

    expect(evento.defaultPrevented).toBe(true)
    expect(puedeInstalar()).toBe(true)
  })

  it('al instalar abre el diálogo del navegador y deja de ofrecer el botón', async () => {
    const prompt = vi.fn(async () => {})
    window.dispatchEvent(eventoInstalar(prompt))

    await instalarApp()

    expect(prompt).toHaveBeenCalledTimes(1)
    expect(puedeInstalar()).toBe(false)
  })

  it('si la app ya se instaló, deja de ofrecer el botón', () => {
    window.dispatchEvent(eventoInstalar())
    expect(puedeInstalar()).toBe(true)

    window.dispatchEvent(new Event('appinstalled'))
    expect(puedeInstalar()).toBe(false)
  })
})
