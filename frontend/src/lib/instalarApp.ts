/**
 * Instalación de la app (PWA) desde un botón propio.
 *
 * Android Chrome dispara `beforeinstallprompt` cuando la app es instalable.
 * Guardamos ese evento y lo usamos al tocar nuestro botón, en vez de depender
 * del menú del navegador. El evento se captura lo antes posible (ver
 * `iniciarCapturaInstalacion`) porque puede dispararse antes de que React monte.
 */
import { useEffect, useState } from 'react'

type EventoInstalar = Event & {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

let eventoDiferido: EventoInstalar | null = null
const oyentes = new Set<() => void>()

function notificar() {
  oyentes.forEach((oyente) => oyente())
}

/** Registra los listeners del navegador. Llamar una sola vez al arrancar. */
export function iniciarCapturaInstalacion(): void {
  if (typeof window === 'undefined') return
  window.addEventListener('beforeinstallprompt', (evento) => {
    // Evita el banner automático del navegador: mostramos nuestro botón.
    evento.preventDefault()
    eventoDiferido = evento as EventoInstalar
    notificar()
  })
  window.addEventListener('appinstalled', () => {
    eventoDiferido = null
    notificar()
  })
}

export function puedeInstalar(): boolean {
  return eventoDiferido !== null
}

/** Abre el diálogo de instalación del navegador. */
export async function instalarApp(): Promise<void> {
  const evento = eventoDiferido
  if (!evento) return
  await evento.prompt()
  // Un evento se usa una sola vez; si el usuario canceló, el navegador
  // volverá a emitirlo más adelante.
  await evento.userChoice
  eventoDiferido = null
  notificar()
}

/** Estado reactivo para componentes: si hay instalación disponible. */
export function useInstalacion(): { puedeInstalar: boolean; instalar: () => Promise<void> } {
  const [, setVersion] = useState(0)
  useEffect(() => {
    const oyente = () => setVersion((v) => v + 1)
    oyentes.add(oyente)
    return () => {
      oyentes.delete(oyente)
    }
  }, [])
  return { puedeInstalar: puedeInstalar(), instalar: instalarApp }
}
