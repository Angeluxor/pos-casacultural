import { useEffect, useState, type FormEvent } from 'react'

export function Paginacion({
  total,
  skip,
  limit,
  onCambiar,
  cargando,
}: {
  total: number
  skip: number
  limit: number
  onCambiar: (skip: number) => void
  cargando?: boolean
}) {
  const pagina = Math.floor(skip / limit) + 1
  const totalPaginas = Math.max(1, Math.ceil(total / limit))
  const [entrada, setEntrada] = useState(String(pagina))

  useEffect(() => {
    setEntrada(String(pagina))
  }, [pagina])

  if (total <= limit) return null

  function ir(e: FormEvent) {
    e.preventDefault()
    const n = Number.parseInt(entrada, 10)
    if (Number.isNaN(n)) {
      setEntrada(String(pagina))
      return
    }
    const destino = Math.min(Math.max(1, n), totalPaginas)
    setEntrada(String(destino))
    if (destino !== pagina) onCambiar((destino - 1) * limit)
  }

  return (
    <div className="paginacion">
      <button
        type="button"
        className="boton boton--mini"
        disabled={skip <= 0 || cargando}
        onClick={() => onCambiar(Math.max(0, skip - limit))}
      >
        ← Anterior
      </button>
      <form className="paginacion__ir" onSubmit={ir}>
        <span className="ayuda">Página</span>
        <input
          className="campo-pagina"
          type="number"
          min={1}
          max={totalPaginas}
          value={entrada}
          onChange={(e) => setEntrada(e.target.value)}
          disabled={cargando}
          aria-label="Número de página"
        />
        <span className="ayuda">
          de {totalPaginas} · {total} registros
        </span>
      </form>
      <button
        type="button"
        className="boton boton--mini"
        disabled={skip + limit >= total || cargando}
        onClick={() => onCambiar(skip + limit)}
      >
        Siguiente →
      </button>
    </div>
  )
}
