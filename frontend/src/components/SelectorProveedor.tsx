import { useEffect, useState } from 'react'
import {
  crearProveedor,
  listarProveedores,
  type Proveedor,
} from '../api/proveedores'
import { useAuth } from '../auth/useAuth'

/**
 * Selector de proveedor para el formulario de Ingresos.
 *
 * Carga el catálogo y permite crear uno nuevo sin salir del formulario. Si el
 * usuario no tiene permiso para ver proveedores, muestra el campo deshabilitado
 * en lugar de ocultarlo, para que quede claro por qué no puede elegir.
 */
export function SelectorProveedor({
  value,
  onChange,
  disabled = false,
}: {
  value: number | null
  onChange: (id: number | null) => void
  disabled?: boolean
}) {
  const { tienePermiso } = useAuth()
  const puedeVer = tienePermiso('proveedores.ver')
  const puedeCrear = tienePermiso('proveedores.crear')
  const [proveedores, setProveedores] = useState<Proveedor[]>([])
  const [cargando, setCargando] = useState(puedeVer)
  const [creando, setCreando] = useState(false)
  const [nombre, setNombre] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  useEffect(() => {
    if (!puedeVer) return
    let activo = true
    listarProveedores()
      .then((lista) => {
        if (activo) setProveedores(lista)
      })
      .catch(() => {
        if (activo) setError('No se pudieron cargar los proveedores.')
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    return () => {
      activo = false
    }
  }, [puedeVer])

  async function crear() {
    const limpio = nombre.trim()
    if (!limpio) {
      setError('Escribe el nombre del proveedor.')
      return
    }
    // Si ya existe (sin distinguir mayúsculas), se reutiliza en lugar de
    // duplicarlo.
    const existente = proveedores.find(
      (p) => p.nombre.trim().toLocaleLowerCase('es') === limpio.toLocaleLowerCase('es'),
    )
    if (existente) {
      onChange(existente.id)
      setCreando(false)
      setNombre('')
      setError('')
      return
    }
    setError('')
    setGuardando(true)
    try {
      const nuevo = await crearProveedor({ nombre: limpio })
      setProveedores((prev) =>
        [...prev, nuevo].sort((a, b) => a.nombre.localeCompare(b.nombre)),
      )
      onChange(nuevo.id)
      setCreando(false)
      setNombre('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo crear el proveedor.')
    } finally {
      setGuardando(false)
    }
  }

  if (!puedeVer) {
    return (
      <label>
        Proveedor
        <input value="" readOnly disabled placeholder="Sin permiso para ver proveedores" />
      </label>
    )
  }

  return (
    <div className="selector-proveedor">
      <label>
        Proveedor
        <select
          value={value != null ? String(value) : ''}
          disabled={disabled || cargando}
          onChange={(e) => {
            const elegido = e.target.value
            if (elegido === 'nuevo') {
              setCreando(true)
              setError('')
              return
            }
            onChange(elegido ? Number(elegido) : null)
          }}
        >
          <option value="">— Sin proveedor —</option>
          {proveedores.map((p) => (
            <option key={p.id} value={p.id}>
              {p.nombre}
            </option>
          ))}
          {puedeCrear && <option value="nuevo">＋ Nuevo proveedor…</option>}
        </select>
      </label>

      {creando && (
        <div className="selector-proveedor__nuevo">
          <input
            autoFocus
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="Nombre del proveedor"
            disabled={guardando}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                void crear()
              }
            }}
          />
          <button
            type="button"
            className="boton boton--mini"
            onClick={() => void crear()}
            disabled={guardando}
          >
            {guardando ? 'Creando…' : 'Crear'}
          </button>
          <button
            type="button"
            className="boton boton--mini boton--secundario"
            onClick={() => {
              setCreando(false)
              setNombre('')
              setError('')
            }}
            disabled={guardando}
          >
            Cancelar
          </button>
        </div>
      )}

      {error && <p className="error">{error}</p>}
    </div>
  )
}
