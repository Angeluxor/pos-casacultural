import { Fragment, useEffect, useState } from 'react'
import {
  guardarPermisosRol,
  obtenerPermisos,
  type PermisosResponse,
} from '../api/permisos'
import type { RolUsuario } from '../api/types'
import { AyudaContextual } from '../components/AyudaContextual'

// Roles editables, en el orden en que se muestran las columnas.
const ROLES: RolUsuario[] = ['Cajero', 'Mesero']

export function Permisos() {
  const [datos, setDatos] = useState<PermisosResponse | null>(null)
  const [seleccion, setSeleccion] = useState<Record<string, string[]>>({})
  const [cargando, setCargando] = useState(true)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')

  useEffect(() => {
    void cargar()
  }, [])

  async function cargar() {
    setCargando(true)
    setError('')
    try {
      const data = await obtenerPermisos()
      setDatos(data)
      setSeleccion({ ...data.roles })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron cargar los permisos')
    } finally {
      setCargando(false)
    }
  }

  function alternar(rol: RolUsuario, clave: string) {
    setOk('')
    setSeleccion((prev) => {
      const actual = new Set(prev[rol] ?? [])
      if (actual.has(clave)) actual.delete(clave)
      else actual.add(clave)
      return { ...prev, [rol]: Array.from(actual) }
    })
  }

  async function guardar() {
    setGuardando(true)
    setError('')
    setOk('')
    try {
      await Promise.all(ROLES.map((rol) => guardarPermisosRol(rol, seleccion[rol] ?? [])))
      setOk('Permisos guardados.')
      await cargar()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron guardar los permisos')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Permisos</h1>
          <p className="ayuda">
            Controla qué puede hacer cada rol. El Admin siempre tiene todo.
          </p>
        </div>
        <button
          className="boton"
          onClick={() => void guardar()}
          disabled={guardando || cargando}
        >
          {guardando ? 'Guardando…' : 'Guardar cambios'}
        </button>
      </header>

      <AyudaContextual
        titulo="Cómo funcionan los permisos"
        detalle="Define qué puede hacer cada rol Cajero y Mesero. El Admin siempre tiene todo y no se edita. Al guardar se aplican al rol; cada usuario los recibe al iniciar sesión."
      />

      {error && <p className="error">{error}</p>}
      {ok && <p className="ok">{ok}</p>}

      {cargando || !datos ? (
        <p className="ayuda">Cargando…</p>
      ) : (
        <div className="tabla-wrap">
          <table className="tabla tabla--permisos">
            <thead>
              <tr>
                <th>Permiso</th>
                <th>Admin</th>
                {ROLES.map((rol) => (
                  <th key={rol}>{rol}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {datos.modulos.map((modulo) => (
                <Fragment key={modulo.modulo}>
                  <tr className="tabla__grupo">
                    <td colSpan={ROLES.length + 2}>{modulo.modulo}</td>
                  </tr>
                  {modulo.permisos.map((permiso) => (
                    <tr key={permiso.clave}>
                      <td>{permiso.etiqueta}</td>
                      <td>
                        <input type="checkbox" checked disabled aria-label={`${permiso.etiqueta} (Admin)`} />
                      </td>
                      {ROLES.map((rol) => (
                        <td key={rol}>
                          <input
                            type="checkbox"
                            aria-label={`${permiso.etiqueta} (${rol})`}
                            checked={(seleccion[rol] ?? []).includes(permiso.clave)}
                            onChange={() => alternar(rol, permiso.clave)}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
