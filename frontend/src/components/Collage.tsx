/**
 * Detalles decorativos de identidad visual.
 *
 * Son puramente ornamentales: no reciben foco, no capturan clics y no aportan
 * información, por eso van marcados como `aria-hidden`.
 */

export function CollageFondo() {
  return (
    <div className="collage-fondo" aria-hidden="true">
      <span className="collage-fondo__mancha collage-fondo__mancha--vino" />
      <span className="collage-fondo__mancha collage-fondo__mancha--mostaza" />
      <span className="collage-fondo__papel">
        <strong>casa cultural</strong>
        <small>medellín · colombia</small>
      </span>
      <span className="collage-fondo__estrella">✶</span>
      <span className="collage-fondo__linea" />
      <span className="collage-fondo__punto" />
    </div>
  )
}

export function CollageHero() {
  return (
    <div className="collage-hero" aria-hidden="true">
      <span className="collage-hero__papel">
        casa
        <br />
        cultural
      </span>
      <span className="collage-hero__estrella">✶</span>
      <span className="collage-hero__cinta" />
    </div>
  )
}
