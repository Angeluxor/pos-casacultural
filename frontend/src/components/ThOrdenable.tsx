import type { ReactNode } from 'react'
import type { Direccion } from '../lib/orden'

/**
 * Encabezado de tabla ordenable. Muestra una flecha según el estado y expone
 * `aria-sort` para accesibilidad. Se usa junto a `useOrdenServidor` (listas
 * paginadas) o `useOrdenLocal` (listas en memoria).
 */
export function ThOrdenable({
  campo,
  orden,
  direccion,
  onOrdenar,
  className,
  children,
}: {
  campo: string
  orden?: string
  direccion: Direccion
  onOrdenar: (campo: string) => void
  className?: string
  children: ReactNode
}) {
  const activo = orden === campo
  return (
    <th
      className={className}
      aria-sort={activo ? (direccion === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <button
        type="button"
        className={activo ? 'th-orden th-orden--activo' : 'th-orden'}
        onClick={() => onOrdenar(campo)}
        title={`Ordenar por ${typeof children === 'string' ? children : campo}`}
      >
        <span>{children}</span>
        <span className="th-orden__flecha" aria-hidden="true">
          {activo ? (direccion === 'asc' ? '▲' : '▼') : '↕'}
        </span>
      </button>
    </th>
  )
}
