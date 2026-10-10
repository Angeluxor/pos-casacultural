export function Stepper({
  valor,
  min = 1,
  max,
  disabled,
  onCambiar,
  etiqueta = 'cantidad',
}: {
  valor: number
  min?: number
  max?: number
  disabled?: boolean
  onCambiar: (cantidad: number) => void
  etiqueta?: string
}) {
  function fijar(n: number) {
    if (Number.isNaN(n)) return
    const acotado = Math.max(min, max !== undefined ? Math.min(max, n) : n)
    onCambiar(acotado)
  }

  return (
    <div className="stepper">
      <button
        type="button"
        className="boton boton--mini stepper__btn"
        aria-label={`Disminuir ${etiqueta}`}
        disabled={disabled || valor <= min}
        onClick={() => fijar(valor - 1)}
      >
        −
      </button>
      <input
        className="input-mini stepper__input"
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        value={valor}
        disabled={disabled}
        aria-label={`Cantidad de ${etiqueta}`}
        onChange={(e) => fijar(Number(e.target.value))}
      />
      <button
        type="button"
        className="boton boton--mini stepper__btn"
        aria-label={`Aumentar ${etiqueta}`}
        disabled={disabled || (max !== undefined && valor >= max)}
        onClick={() => fijar(valor + 1)}
      >
        +
      </button>
    </div>
  )
}
