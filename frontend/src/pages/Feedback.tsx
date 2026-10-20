import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  actualizarFeedback,
  obtenerCapturaFeedback,
  paginaFeedback,
  type EstadoFeedback,
  type Feedback as FeedbackItem,
  type PrioridadFeedback,
  type TipoFeedback,
} from '../api/feedback'
import type { Pagina, UsuarioSesion } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { Paginacion } from '../components/Paginacion'
import { Vacio } from '../components/Vacio'
import { formatoFecha } from '../lib/formato'

const TIPOS: TipoFeedback[] = ['Bug', 'Idea', 'Duda', 'Otro']
const ESTADOS: EstadoFeedback[] = ['Nuevo', 'En revisión', 'Resuelto', 'Descartado']
const PRIORIDADES: PrioridadFeedback[] = ['Baja', 'Media', 'Alta']

const ETIQUETA_TIPO: Record<TipoFeedback, string> = {
  Bug: 'Error',
  Idea: 'Idea',
  Duda: 'Duda',
  Otro: 'Otro',
}

const CLASE_TIPO: Record<TipoFeedback, string> = {
  Bug: 'badge badge--off',
  Idea: 'badge badge--on',
  Duda: 'badge badge--info',
  Otro: 'badge badge--warn',
}

const CLASE_ESTADO: Record<EstadoFeedback, string> = {
  Nuevo: 'badge badge--info',
  'En revisión': 'badge badge--warn',
  Resuelto: 'badge badge--on',
  Descartado: 'badge badge--off',
}

const CLASE_PRIORIDAD: Record<PrioridadFeedback, string> = {
  Baja: 'badge badge--suave',
  Media: 'badge badge--warn',
  Alta: 'badge badge--off',
}

function rutaDe(item: FeedbackItem): string {
  const ruta = item.contexto?.ruta
  return typeof ruta === 'string' ? ruta : '—'
}

function etiquetasDe(texto: string): string[] {
  return texto
    .split(',')
    .map((parte) => parte.trim())
    .filter(Boolean)
}

function ModalCaptura({
  feedback,
  onCerrar,
}: {
  feedback: FeedbackItem
  onCerrar: () => void
}) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let activo = true
    let objectUrl = ''
    setUrl('')
    setError('')
    obtenerCapturaFeedback(feedback.id)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob)
        if (activo) setUrl(objectUrl)
        else URL.revokeObjectURL(objectUrl)
      })
      .catch((err) => {
        if (activo) {
          setError(err instanceof Error ? err.message : 'No se pudo cargar la captura')
        }
      })
    return () => {
      activo = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [feedback.id])

  return (
    <div className="modal-overlay" onClick={onCerrar}>
      <div
        className="modal modal--ancho feedback-captura-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Captura del feedback"
        onClick={(evento) => evento.stopPropagation()}
      >
        <div className="feedback-modal__head">
          <h2>Captura del feedback #{feedback.id}</h2>
          <button
            type="button"
            className="feedback-cerrar"
            aria-label="Cerrar captura"
            onClick={onCerrar}
          >
            ×
          </button>
        </div>
        {error && <p className="error">{error}</p>}
        {!error && !url && <p className="ayuda">Cargando captura…</p>}
        {url && (
          <img
            src={url}
            alt={`Captura del feedback ${feedback.id}`}
            className="feedback-captura__imagen"
          />
        )}
        <div className="acciones">
          {url && (
            <a
              className="boton boton--secundario"
              href={url}
              download={feedback.captura_nombre ?? `feedback-${feedback.id}.jpg`}
            >
              Descargar
            </a>
          )}
          <button type="button" className="boton" onClick={onCerrar}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  )
}

function ModalDetalle({
  feedback,
  usuario,
  onCerrar,
  onGuardado,
  onVerCaptura,
}: {
  feedback: FeedbackItem
  usuario: UsuarioSesion | null
  onCerrar: () => void
  onGuardado: () => void
  onVerCaptura: (feedback: FeedbackItem) => void
}) {
  const [estado, setEstado] = useState<EstadoFeedback>(feedback.estado)
  const [prioridad, setPrioridad] = useState<PrioridadFeedback>(feedback.prioridad)
  const [etiquetas, setEtiquetas] = useState(feedback.etiquetas.join(', '))
  const [notas, setNotas] = useState(feedback.notas_internas ?? '')
  const [responsableId, setResponsableId] = useState<number | null>(
    feedback.responsable_id,
  )
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  const responsableNombre =
    responsableId === null
      ? 'Sin asignar'
      : responsableId === usuario?.id
        ? usuario?.nombre ?? 'Tú'
        : responsableId === feedback.responsable_id
          ? feedback.responsable_nombre ?? `Usuario #${responsableId}`
          : `Usuario #${responsableId}`

  async function guardar(evento: FormEvent) {
    evento.preventDefault()
    setError('')
    const listaEtiquetas = etiquetasDe(etiquetas)
    if (listaEtiquetas.length > 8) {
      setError('Puedes usar máximo 8 etiquetas.')
      return
    }
    if (listaEtiquetas.some((etiqueta) => etiqueta.length > 30)) {
      setError('Cada etiqueta puede tener máximo 30 caracteres.')
      return
    }
    setGuardando(true)
    try {
      await actualizarFeedback(feedback.id, {
        estado,
        prioridad,
        etiquetas: listaEtiquetas,
        notas_internas: notas.trim() || null,
        responsable_id: responsableId,
      })
      onGuardado()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo guardar el feedback.')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onCerrar}>
      <form
        className="modal modal--ancho feedback-detalle"
        role="dialog"
        aria-modal="true"
        aria-label="Detalle del feedback"
        onClick={(evento) => evento.stopPropagation()}
        onSubmit={guardar}
      >
        <div className="feedback-modal__head">
          <div>
            <h2>Feedback #{feedback.id}</h2>
            <p className="ayuda">
              {feedback.usuario_nombre} · {formatoFecha(feedback.creado_en)}
            </p>
          </div>
          <button
            type="button"
            className="feedback-cerrar"
            aria-label="Cerrar detalle"
            onClick={onCerrar}
          >
            ×
          </button>
        </div>

        <div className="feedback-card__head">
          <span className={CLASE_TIPO[feedback.tipo]}>{ETIQUETA_TIPO[feedback.tipo]}</span>
          <span className={CLASE_ESTADO[feedback.estado]}>{feedback.estado}</span>
          <span className={CLASE_PRIORIDAD[feedback.prioridad]}>{feedback.prioridad}</span>
          <span className="feedback-card__ruta">{rutaDe(feedback)}</span>
        </div>

        {error && <p className="error">{error}</p>}

        <p className="feedback-detalle__comentario">{feedback.comentario}</p>

        <div className="acciones-fila">
          {feedback.tiene_captura ? (
            <button
              type="button"
              className="boton boton--mini"
              onClick={() => onVerCaptura(feedback)}
            >
              Ver captura
            </button>
          ) : (
            <span className="ayuda">Sin captura adjunta.</span>
          )}
        </div>

        <details className="feedback-contexto">
          <summary>Contexto técnico</summary>
          <pre>{JSON.stringify(feedback.contexto, null, 2)}</pre>
        </details>

        <div className="fila-campos">
          <label>
            Estado
            <select
              value={estado}
              onChange={(evento) => setEstado(evento.target.value as EstadoFeedback)}
            >
              {ESTADOS.map((opcion) => (
                <option key={opcion} value={opcion}>
                  {opcion}
                </option>
              ))}
            </select>
          </label>
          <label>
            Prioridad
            <select
              value={prioridad}
              onChange={(evento) =>
                setPrioridad(evento.target.value as PrioridadFeedback)
              }
            >
              {PRIORIDADES.map((opcion) => (
                <option key={opcion} value={opcion}>
                  {opcion}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label>
          Etiquetas (separadas por coma)
          <input
            value={etiquetas}
            onChange={(evento) => setEtiquetas(evento.target.value)}
            placeholder="Ej.: caja, mobile, urgente"
            maxLength={250}
          />
        </label>

        <label>
          Notas internas (solo administración)
          <textarea
            value={notas}
            onChange={(evento) => setNotas(evento.target.value)}
            rows={3}
            maxLength={4000}
            placeholder="Decisiones, seguimiento o contexto para el equipo…"
          />
        </label>

        <div className="feedback-responsable">
          <span>
            Responsable: <strong>{responsableNombre}</strong>
          </span>
          <div className="acciones-fila">
            <button
              type="button"
              className="boton boton--mini"
              onClick={() => setResponsableId(usuario?.id ?? null)}
              disabled={!usuario}
            >
              Asignarme
            </button>
            <button
              type="button"
              className="boton boton--mini"
              onClick={() => setResponsableId(null)}
              disabled={responsableId === null}
            >
              Liberar
            </button>
          </div>
        </div>

        <div className="acciones">
          <button type="button" className="boton boton--secundario" onClick={onCerrar}>
            Cancelar
          </button>
          <button type="submit" className="boton" disabled={guardando}>
            {guardando ? 'Guardando…' : 'Guardar cambios'}
          </button>
        </div>
      </form>
    </div>
  )
}

export function Feedback() {
  const { usuario } = useAuth()
  const [datos, setDatos] = useState<Pagina<FeedbackItem> | null>(null)
  const [skip, setSkip] = useState(0)
  const [buscar, setBuscar] = useState('')
  const [buscarAplicado, setBuscarAplicado] = useState('')
  const [estado, setEstado] = useState<EstadoFeedback | ''>('')
  const [tipo, setTipo] = useState<TipoFeedback | ''>('')
  const [prioridad, setPrioridad] = useState<PrioridadFeedback | ''>('')
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)
  const [detalle, setDetalle] = useState<FeedbackItem | null>(null)
  const [captura, setCaptura] = useState<FeedbackItem | null>(null)

  const tamano = 20

  useEffect(() => {
    const temporizador = setTimeout(() => {
      setBuscarAplicado(buscar)
      setSkip(0)
    }, 300)
    return () => clearTimeout(temporizador)
  }, [buscar])

  useEffect(() => {
    setSkip(0)
  }, [estado, tipo, prioridad])

  useEffect(() => {
    let cancelado = false
    setCargando(true)
    paginaFeedback({
      skip,
      limit: tamano,
      buscar: buscarAplicado,
      estado,
      tipo,
      prioridad,
    })
      .then((pagina) => {
        if (cancelado) return
        setDatos(pagina)
        setError('')
      })
      .catch((err) => {
        if (cancelado) return
        setError(err instanceof Error ? err.message : 'Error al cargar el feedback')
      })
      .finally(() => {
        if (!cancelado) setCargando(false)
      })
    return () => {
      cancelado = true
    }
  }, [skip, buscarAplicado, estado, tipo, prioridad, version])

  const recargar = useCallback(() => setVersion((valor) => valor + 1), [])
  const items = datos?.items ?? []
  const total = datos?.total ?? 0

  function limpiarFiltros() {
    setBuscar('')
    setBuscarAplicado('')
    setEstado('')
    setTipo('')
    setPrioridad('')
    setSkip(0)
  }

  return (
    <div className="pagina">
      <header className="pagina__head">
        <div>
          <h1>Feedback</h1>
          <p className="ayuda">
            {total} {total === 1 ? 'comentario' : 'comentarios'} del equipo
          </p>
        </div>
      </header>

      <div className="barra">
        <input
          className="campo-busqueda"
          placeholder="Buscar por comentario, persona o etiqueta…"
          value={buscar}
          onChange={(evento) => setBuscar(evento.target.value)}
        />
        <label className="campo-fecha">
          Estado
          <select
            value={estado}
            onChange={(evento) => setEstado(evento.target.value as EstadoFeedback | '')}
          >
            <option value="">Todos</option>
            {ESTADOS.map((opcion) => (
              <option key={opcion} value={opcion}>
                {opcion}
              </option>
            ))}
          </select>
        </label>
        <label className="campo-fecha">
          Tipo
          <select
            value={tipo}
            onChange={(evento) => setTipo(evento.target.value as TipoFeedback | '')}
          >
            <option value="">Todos</option>
            {TIPOS.map((opcion) => (
              <option key={opcion} value={opcion}>
                {ETIQUETA_TIPO[opcion]}
              </option>
            ))}
          </select>
        </label>
        <label className="campo-fecha">
          Prioridad
          <select
            value={prioridad}
            onChange={(evento) =>
              setPrioridad(evento.target.value as PrioridadFeedback | '')
            }
          >
            <option value="">Todas</option>
            {PRIORIDADES.map((opcion) => (
              <option key={opcion} value={opcion}>
                {opcion}
              </option>
            ))}
          </select>
        </label>
        {(buscar || estado || tipo || prioridad) && (
          <button type="button" className="boton boton--mini" onClick={limpiarFiltros}>
            Limpiar
          </button>
        )}
      </div>

      {error && <p className="error">{error}</p>}

      {cargando ? (
        <p className="ayuda">Cargando…</p>
      ) : items.length === 0 ? (
        <Vacio
          titulo={buscar.trim() ? 'Sin resultados' : 'Aún no hay feedback'}
          detalle={
            buscar.trim() || estado || tipo || prioridad
              ? 'Ningún comentario coincide con los filtros.'
              : 'Los comentarios enviados desde el botón flotante aparecerán aquí.'
          }
        />
      ) : (
        <>
          <div className="feedback-lista">
            {items.map((item) => (
              <article className="feedback-card" key={item.id}>
                <div className="feedback-card__head">
                  <span className={CLASE_TIPO[item.tipo]}>{ETIQUETA_TIPO[item.tipo]}</span>
                  <span className={CLASE_ESTADO[item.estado]}>{item.estado}</span>
                  <span className={CLASE_PRIORIDAD[item.prioridad]}>{item.prioridad}</span>
                  <span className="ayuda">{formatoFecha(item.creado_en)}</span>
                </div>
                <p className="feedback-card__comentario">{item.comentario}</p>
                <div className="feedback-card__meta">
                  <span>{item.usuario_nombre}</span>
                  <span className="feedback-card__ruta">{rutaDe(item)}</span>
                  {item.responsable_nombre && (
                    <span>Responsable: {item.responsable_nombre}</span>
                  )}
                </div>
                {item.etiquetas.length > 0 && (
                  <div className="feedback-card__tags">
                    {item.etiquetas.map((etiqueta) => (
                      <span className="feedback-tag" key={etiqueta}>
                        {etiqueta}
                      </span>
                    ))}
                  </div>
                )}
                <div className="acciones-fila">
                  {item.tiene_captura && (
                    <button
                      type="button"
                      className="boton boton--mini"
                      onClick={() => setCaptura(item)}
                    >
                      Ver captura
                    </button>
                  )}
                  <button
                    type="button"
                    className="boton boton--mini"
                    onClick={() => setDetalle(item)}
                  >
                    Gestionar
                  </button>
                </div>
              </article>
            ))}
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

      {detalle && (
        <ModalDetalle
          key={detalle.id}
          feedback={detalle}
          usuario={usuario}
          onCerrar={() => setDetalle(null)}
          onGuardado={() => {
            setDetalle(null)
            recargar()
          }}
          onVerCaptura={setCaptura}
        />
      )}

      {captura && <ModalCaptura feedback={captura} onCerrar={() => setCaptura(null)} />}
    </div>
  )
}
