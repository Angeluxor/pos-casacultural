export function Vacio({ titulo, detalle }: { titulo: string; detalle?: string }) {
  return (
    <div className="vacio">
      <strong>{titulo}</strong>
      {detalle && <span className="ayuda">{detalle}</span>}
    </div>
  )
}
