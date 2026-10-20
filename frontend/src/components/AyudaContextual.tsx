type Props = {
  titulo: string
  detalle: string
  id?: string
  ariaLive?: boolean
}

/**
 * Bloque de ayuda breve para explicar qué hace una pantalla o una pestaña.
 * No reemplaza la Guía de uso: solo da el contexto mínimo para operar sin
 * salir de la pantalla.
 */
export function AyudaContextual({ titulo, detalle, id, ariaLive = false }: Props) {
  return (
    <div
      className="ayuda-contextual"
      id={id}
      role="note"
      aria-live={ariaLive ? 'polite' : undefined}
    >
      <span className="ayuda-contextual__icono" aria-hidden="true">
        i
      </span>
      <div>
        <strong>{titulo}</strong>
        <p>{detalle}</p>
      </div>
    </div>
  )
}
