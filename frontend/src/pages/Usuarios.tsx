import { useEffect, useState, type FormEvent } from 'react'
import {
  actualizarUsuario,
  aplicarDescuentoNomina,
  clientesDisponibles,
  crearUsuario,
  eliminarUsuario,
  obtenerDeudaNomina,
  obtenerHistorialNomina,
  paginaUsuarios,
  type DeudaNomina,
  type DescuentoNominaResultado,
  type HistorialNomina,
  type UsuarioCreate,
} from '../api/usuarios'
import type { Cliente } from '../api/clientes'
import type { RolUsuario, Usuario } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { AyudaContextual } from '../components/AyudaContextual'
import { CampoPassword } from '../components/CampoPassword'
import { Paginacion } from '../components/Paginacion'
import { ThOrdenable } from '../components/ThOrdenable'
import { useOrdenServidor } from '../lib/orden'
import { Vacio } from '../components/Vacio'
import { confirmarCierre } from '../lib/modal'
import { usePaginacion } from '../lib/usePaginacion'
import { formatoFecha, moneda } from '../lib/formato'

const ROLES: RolUsuario[] = ['Admin', 'Cajero', 'Mesero']

export function Usuarios() {
  const { usuario: actual, tienePermiso } = useAuth()

  const { orden, direccion, alternar } = useOrdenServidor()
  const { datos, skip, setSkip, buscar, setBuscar, cargando, error, recargar, tamano } =
    usePaginacion(paginaUsuarios, 25, orden, direccion)
  const usuarios = datos?.items ?? []
  const total = datos?.total ?? 0

  const [form, setForm] = useState<{ abierto: boolean; usuario: Usuario | null }>({
    abierto: false,
    usuario: null,
  })
  const [nomina, setNomina] = useState<Usuario | null>(null)
  const [errorAccion, setErrorAccion] = useState('')
  const [aviso, setAviso] = useState('')
  const [eliminandoId, setEliminandoId] = useState<number | null>(null)
  const puedeDescontar = tienePermiso('nomina.descontar')

  async function eliminar(u: Usuario) {
    if (!window.confirm(`¿Eliminar al usuario «${u.username}»? Esta acción no se puede deshacer.`))
      return
    setErrorAccion('')
    setAviso('')
    setEliminandoId(u.id)
    try {
      await eliminarUsuario(u.id)
      recargar()
    } catch (err) {
      setErrorAccion(err instanceof Error ? err.message : 'No se pudo eliminar el usuario')
    } finally {
      setEliminandoId(null)
    }
  }

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Usuarios</h1>
          <p className="ayuda">{total} usuarios</p>
        </div>
        <button className="boton" onClick={() => setForm({ abierto: true, usuario: null })}>
          + Nuevo usuario
        </button>
      </header>

      <AyudaContextual
        titulo="Qué puedes administrar aquí"
        detalle="Crea usuarios, edita su rol y restablece contraseñas. Admin tiene acceso total; Cajero y Mesero dependen de Permisos. También puedes vincular un usuario a un cliente para descontar sus compras a crédito de la nómina."
      />

      <div className="barra">
        <input
          className="campo-busqueda"
          placeholder="Buscar por usuario o nombre…"
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
        />
      </div>

      {error && <p className="error">{error}</p>}
      {errorAccion && <p className="error">{errorAccion}</p>}
      {aviso && <p className="ok">{aviso}</p>}

      {cargando ? (
        <p className="ayuda">Cargando…</p>
      ) : usuarios.length === 0 ? (
        <Vacio
          titulo={buscar.trim() ? 'Sin resultados' : 'Aún no hay usuarios'}
          detalle={
            buscar.trim()
              ? `Nada coincide con «${buscar.trim()}».`
              : 'Crea el primer usuario del sistema.'
          }
        />
      ) : (
        <>
          <div className="tabla-wrap tabla-wrap--cards">
            <table className="tabla tabla--cards">
              <thead>
                <tr>
                  <ThOrdenable campo="username" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Usuario
                  </ThOrdenable>
                  <ThOrdenable campo="nombre" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Nombre
                  </ThOrdenable>
                  <ThOrdenable campo="rol" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Rol
                  </ThOrdenable>
                  <ThOrdenable campo="activo" orden={orden} direccion={direccion} onOrdenar={alternar}>
                    Estado
                  </ThOrdenable>
                  <th>Cliente vinculado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {usuarios.map((u) => (
                  <tr key={u.id}>
                    <td data-label="Usuario">{u.username}</td>
                    <td data-label="Nombre">{u.nombre}</td>
                    <td data-label="Rol">{u.rol}</td>
                    <td data-label="Estado">
                      <span className={u.activo ? 'badge badge--on' : 'badge badge--off'}>
                        {u.activo ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    <td data-label="Cliente vinculado">{u.cliente_nombre ?? '—'}</td>
                    <td className="celda-accion">
                      <div className="acciones-fila">
                        {puedeDescontar && u.cliente_id != null && (
                          <button
                            className="boton boton--mini boton--secundario"
                            onClick={() => {
                              setAviso('')
                              setErrorAccion('')
                              setNomina(u)
                            }}
                          >
                            Nómina
                          </button>
                        )}
                        <button
                          className="boton boton--mini"
                          onClick={() => setForm({ abierto: true, usuario: u })}
                        >
                          Editar
                        </button>
                        <button
                          className="boton boton--mini boton--danger"
                          disabled={u.id === actual?.id || eliminandoId === u.id}
                          title={
                            u.id === actual?.id ? 'No puedes eliminar tu propio usuario' : undefined
                          }
                          onClick={() => void eliminar(u)}
                        >
                          {eliminandoId === u.id ? 'Eliminando…' : 'Eliminar'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginacion
            total={total}
            skip={skip}
            limit={tamano}
            onCambiar={setSkip}
            cargando={cargando}
          />
        </>
      )}

      {form.abierto && (
        <FormUsuario
          usuario={form.usuario}
          esUsuarioActual={form.usuario?.id === actual?.id}
          onCerrar={() => setForm({ abierto: false, usuario: null })}
          onGuardado={() => {
            setForm({ abierto: false, usuario: null })
            recargar()
          }}
        />
      )}

      {nomina && (
        <DescuentoNomina
          usuario={nomina}
          onCerrar={() => setNomina(null)}
          onAplicado={(mensaje) => {
            setNomina(null)
            setAviso(mensaje)
            setErrorAccion('')
            recargar()
          }}
        />
      )}
    </div>
  )
}

function FormUsuario({
  usuario,
  esUsuarioActual,
  onCerrar,
  onGuardado,
}: {
  usuario: Usuario | null
  esUsuarioActual: boolean
  onCerrar: () => void
  onGuardado: () => void
}) {
  const esEdicion = usuario !== null
  const [username, setUsername] = useState(usuario?.username ?? '')
  const [nombre, setNombre] = useState(usuario?.nombre ?? '')
  const [password, setPassword] = useState('')
  const [rol, setRol] = useState<RolUsuario>(usuario?.rol ?? 'Cajero')
  const [activo, setActivo] = useState(usuario?.activo ?? true)
  const [clienteId, setClienteId] = useState<number | null>(usuario?.cliente_id ?? null)
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [cargandoClientes, setCargandoClientes] = useState(true)
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  useEffect(() => {
    let vigente = true
    setCargandoClientes(true)
    clientesDisponibles(usuario?.id)
      .then((lista) => {
        if (vigente) setClientes(lista)
      })
      .catch(() => {
        if (vigente) setClientes([])
      })
      .finally(() => {
        if (vigente) setCargandoClientes(false)
      })
    return () => {
      vigente = false
    }
  }, [usuario?.id])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setGuardando(true)
    try {
      if (usuario) {
        await actualizarUsuario(usuario.id, {
          nombre,
          rol,
          activo,
          cliente_id: clienteId,
          ...(password ? { password } : {}),
        })
      } else {
        const data: UsuarioCreate = { username, nombre, password, rol, activo, cliente_id: clienteId }
        await crearUsuario(data)
      }
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar el usuario')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h2>{esEdicion ? 'Editar usuario' : 'Nuevo usuario'}</h2>
        {error && <p className="error">{error}</p>}
        <label>
          Usuario
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            disabled={esEdicion}
          />
        </label>
        <label>
          Nombre
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} required />
        </label>
        <label>
          Contraseña {esEdicion ? '(dejar vacío para no cambiar)' : ''}
          <CampoPassword
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required={!esEdicion}
            autoComplete="new-password"
          />
        </label>
        <label>
          Rol
          <select value={rol} onChange={(e) => setRol(e.target.value as RolUsuario)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <label>
          Cliente vinculado (nómina)
          <select
            value={clienteId ?? ''}
            disabled={cargandoClientes}
            onChange={(e) => setClienteId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Sin vincular</option>
            {clientes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
                {c.documento ? ` · ${c.documento}` : ''}
              </option>
            ))}
          </select>
        </label>
        <p className="ayuda">
          Un cliente solo puede estar vinculado a un usuario. Sirve para descontar
          de la nómina sus compras a crédito.
        </p>
        <label className="check">
          <input
            type="checkbox"
            checked={activo}
            disabled={esUsuarioActual}
            onChange={(e) => setActivo(e.target.checked)}
          />
          Activo
        </label>
        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button type="submit" className="boton" disabled={guardando}>
            {guardando ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </form>
    </div>
  )
}

function DescuentoNomina({
  usuario,
  onCerrar,
  onAplicado,
}: {
  usuario: Usuario
  onCerrar: () => void
  onAplicado: (mensaje: string) => void
}) {
  const [deuda, setDeuda] = useState<DeudaNomina | null>(null)
  const [historial, setHistorial] = useState<HistorialNomina | null>(null)
  const [monto, setMonto] = useState('')
  const [nota, setNota] = useState('')
  const [cargando, setCargando] = useState(true)
  const [aplicando, setAplicando] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let vigente = true
    setCargando(true)
    const deudaP =
      usuario.cliente_id != null
        ? obtenerDeudaNomina(usuario.id)
        : Promise.resolve<DeudaNomina | null>(null)
    Promise.allSettled([deudaP, obtenerHistorialNomina(usuario.id)])
      .then(([resDeuda, resHistorial]) => {
        if (!vigente) return
        if (resDeuda.status === 'fulfilled') {
          if (resDeuda.value) {
            setDeuda(resDeuda.value)
            setMonto(String(resDeuda.value.saldo_total))
          }
        } else {
          setError(
            resDeuda.reason instanceof Error
              ? resDeuda.reason.message
              : 'No se pudo cargar la deuda',
          )
        }
        if (resHistorial.status === 'fulfilled') setHistorial(resHistorial.value)
      })
      .finally(() => {
        if (vigente) setCargando(false)
      })
    return () => {
      vigente = false
    }
  }, [usuario.id, usuario.cliente_id])

  async function aplicar(e: FormEvent) {
    e.preventDefault()
    setError('')
    const valor = monto.trim() === '' ? null : Number(monto)
    if (valor != null && (!Number.isFinite(valor) || valor <= 0)) {
      setError('El monto debe ser mayor a 0.')
      return
    }
    setAplicando(true)
    try {
      const r: DescuentoNominaResultado = await aplicarDescuentoNomina(
        usuario.id,
        valor,
        nota,
      )
      onAplicado(
        `Se descontaron ${moneda.format(r.monto_aplicado)} de la nómina de ${usuario.nombre}. ` +
          `Saldo pendiente: ${moneda.format(r.saldo_pendiente)}.`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo aplicar el descuento')
    } finally {
      setAplicando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => confirmarCierre(onCerrar)}>
      <form className="modal modal--ancho" onClick={(e) => e.stopPropagation()} onSubmit={aplicar}>
        <h2>Descuento de nómina · {usuario.nombre}</h2>
        {error && <p className="error">{error}</p>}
        {cargando ? (
          <p className="ayuda">Cargando deuda…</p>
        ) : !deuda || deuda.facturas.length === 0 ? (
          <p className="ayuda">Este empleado no tiene deuda a crédito pendiente.</p>
        ) : (
          <>
            <p className="ayuda">
              Cliente vinculado: <strong>{deuda.cliente_nombre}</strong> · Deuda total:{' '}
              <strong>{moneda.format(deuda.saldo_total)}</strong>
            </p>
            <div className="tabla-wrap">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Factura</th>
                    <th>Fecha</th>
                    <th>Total</th>
                    <th>Saldo</th>
                  </tr>
                </thead>
                <tbody>
                  {deuda.facturas.map((f) => (
                    <tr key={f.factura_id}>
                      <td>#{f.factura_id}</td>
                      <td>{formatoFecha(f.fecha)}</td>
                      <td>{moneda.format(f.total)}</td>
                      <td>{moneda.format(f.saldo)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <label>
              Monto a descontar
              <input
                type="number"
                min="0"
                step="0.01"
                value={monto}
                onChange={(e) => setMonto(e.target.value)}
              />
            </label>
            <label>
              Nota / período (opcional)
              <input
                type="text"
                maxLength={200}
                value={nota}
                placeholder="Ej. Nómina octubre 2026"
                onChange={(e) => setNota(e.target.value)}
              />
            </label>
            <p className="ayuda">
              Se abona a las facturas más antiguas primero. Deja vacío o el total
              para descontar toda la deuda. Este abono no entra a la caja.
            </p>
          </>
        )}
        {historial && historial.items.length > 0 && (
          <section className="panel">
            <h3>Historial de descuentos</h3>
            <p className="ayuda">
              {historial.descuentos} descuento(s) · Total descontado:{' '}
              <strong>{moneda.format(historial.monto_total)}</strong>
            </p>
            {historial.items.length < historial.descuentos && (
              <p className="ayuda">
                Mostrando los últimos {historial.items.length} de{' '}
                {historial.descuentos} descuentos.
              </p>
            )}
            <div className="tabla-wrap">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Monto</th>
                    <th>Saldo después</th>
                    <th>Facturas (abono)</th>
                    <th>Aplicado por</th>
                    <th>Nota</th>
                  </tr>
                </thead>
                <tbody>
                  {historial.items.map((i) => (
                    <tr key={i.id}>
                      <td>{formatoFecha(i.fecha)}</td>
                      <td>{moneda.format(i.monto)}</td>
                      <td>{moneda.format(i.saldo_pendiente)}</td>
                      <td>
                        {i.facturas.length === 0 ? (
                          '—'
                        ) : (
                          i.facturas.map((f) => (
                            <div
                              key={f.factura_id}
                              title={`Total ${moneda.format(f.total)} · Saldo actual ${moneda.format(f.saldo_actual)}`}
                            >
                              #{f.factura_id} · {moneda.format(f.abono)}
                            </div>
                          ))
                        )}
                      </td>
                      <td>{i.registrado_por}</td>
                      <td>{i.nota ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button
            type="submit"
            className="boton"
            disabled={aplicando || cargando || !deuda || deuda.facturas.length === 0}
          >
            {aplicando ? 'Aplicando…' : 'Aplicar descuento'}
          </button>
        </div>
      </form>
    </div>
  )
}
