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
  if (total <= limit) return null
  const pagina = Math.floor(skip / limit) + 1
  const totalPaginas = Math.max(1, Math.ceil(total / limit))
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
      <span className="ayuda">
        Página {pagina} de {totalPaginas} · {total} registros
      </span>
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
