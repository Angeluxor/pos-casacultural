import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import { toJpeg } from 'html-to-image'
import { crearFeedback, type TipoFeedback } from '../api/feedback'
import { useAuth } from '../auth/useAuth'
import { confirmarCierre } from '../lib/modal'
import { contextoFeedback } from '../lib/feedbackContext'

const TIPOS: { valor: TipoFeedback; etiqueta: string }[] = [
  { valor: 'Bug', etiqueta: 'Error' },
  { valor: 'Idea', etiqueta: 'Idea' },
  { valor: 'Duda', etiqueta: 'Duda' },
  { valor: 'Otro', etiqueta: 'Otro' },
]

// El backend acepta 2 MB de imagen; base64 ocupa aproximadamente un 33 % más.
const MAX_CAPTURA_BASE64 = 2_700_000

type Punto = { x: number; y: number }
type Rectangulo = { x: number; y: number; w: number; h: number }

function limitar(valor: number, minimo: number, maximo: number): number {
  return Math.min(Math.max(valor, minimo), maximo)
}

function rectanguloDesde(a: Punto, b: Punto): Rectangulo {
  return {
    x: Math.min(a.x, b.x),
    y: Math.min(a.y, b.y),
    w: Math.abs(a.x - b.x),
    h: Math.abs(a.y - b.y),
  }
}

function EditorCaptura({
  src,
  onCambiar,
}: {
  src: string
  onCambiar: (dataUrl: string) => void
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imagenRef = useRef<HTMLImageElement | null>(null)
  const onCambiarRef = useRef(onCambiar)
  const [listo, setListo] = useState(false)
  const [rects, setRects] = useState<Rectangulo[]>([])
  const [inicio, setInicio] = useState<Punto | null>(null)
  const [actual, setActual] = useState<Punto | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    onCambiarRef.current = onCambiar
  }, [onCambiar])

  const dibujar = useCallback(() => {
    const canvas = canvasRef.current
    const imagen = imagenRef.current
    if (!canvas || !imagen) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(imagen, 0, 0)
    const visibles = inicio && actual ? [...rects, rectanguloDesde(inicio, actual)] : rects
    ctx.fillStyle = '#000'
    for (const rect of visibles) {
      ctx.fillRect(rect.x, rect.y, rect.w, rect.h)
    }
  }, [rects, inicio, actual])

  useEffect(() => {
    setRects([])
    setInicio(null)
    setActual(null)
    setListo(false)
    setError('')
    const imagen = new Image()
    imagen.onload = () => {
      imagenRef.current = imagen
      const canvas = canvasRef.current
      if (canvas) {
        canvas.width = imagen.naturalWidth
        canvas.height = imagen.naturalHeight
      }
      setListo(true)
    }
    imagen.onerror = () => setError('No se pudo mostrar la captura.')
    imagen.src = src
    return () => {
      imagen.onload = null
      imagen.onerror = null
    }
  }, [src])

  useEffect(() => {
    if (listo) dibujar()
  }, [listo, dibujar])

  useEffect(() => {
    if (!listo) return
    const canvas = canvasRef.current
    if (!canvas) return
    onCambiarRef.current(canvas.toDataURL('image/jpeg', 0.85))
  }, [rects, listo])

  function punto(evento: ReactPointerEvent<HTMLCanvasElement>): Punto {
    const canvas = evento.currentTarget
    const caja = canvas.getBoundingClientRect()
    return {
      x: limitar((evento.clientX - caja.left) * (canvas.width / caja.width), 0, canvas.width),
      y: limitar((evento.clientY - caja.top) * (canvas.height / caja.height), 0, canvas.height),
    }
  }

  function alPresionar(evento: ReactPointerEvent<HTMLCanvasElement>) {
    if (evento.button !== 0) return
    evento.currentTarget.setPointerCapture?.(evento.pointerId)
    const p = punto(evento)
    setInicio(p)
    setActual(p)
  }

  function alMover(evento: ReactPointerEvent<HTMLCanvasElement>) {
    if (!inicio) return
    setActual(punto(evento))
  }

  function alSoltar(evento: ReactPointerEvent<HTMLCanvasElement>) {
    if (!inicio) return
    const fin = punto(evento)
    evento.currentTarget.releasePointerCapture?.(evento.pointerId)
    setInicio(null)
    setActual(null)
    const rect = rectanguloDesde(inicio, fin)
    if (rect.w >= 4 && rect.h >= 4) {
      setRects((previos) => [...previos, rect])
    }
  }

  function cancelarTrazo() {
    setInicio(null)
    setActual(null)
  }

  return (
    <div className="feedback-captura__editor">
      <canvas
        ref={canvasRef}
        className="feedback-captura__lienzo"
        aria-label="Captura de pantalla para redactar zonas sensibles"
        onPointerDown={alPresionar}
        onPointerMove={alMover}
        onPointerUp={alSoltar}
        onPointerCancel={cancelarTrazo}
      />
      <div className="feedback-captura__herramientas">
        <span className="ayuda">Arrastra sobre la imagen para tapar datos sensibles.</span>
        <button
          type="button"
          className="boton boton--mini"
          onClick={() => setRects((previos) => previos.slice(0, -1))}
          disabled={rects.length === 0}
        >
          Deshacer
        </button>
        <button
          type="button"
          className="boton boton--mini"
          onClick={() => setRects([])}
          disabled={rects.length === 0}
        >
          Limpiar marcas
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </div>
  )
}

export function FeedbackWidget() {
  const { usuario, tienePermiso } = useAuth()
  const [abierto, setAbierto] = useState(false)
  const [tipo, setTipo] = useState<TipoFeedback>('Idea')
  const [comentario, setComentario] = useState('')
  const [capturaOriginal, setCapturaOriginal] = useState<string | null>(null)
  const [capturaFinal, setCapturaFinal] = useState<string | null>(null)
  const [capturaMuyGrande, setCapturaMuyGrande] = useState(false)
  const [aceptaCaptura, setAceptaCaptura] = useState(false)
  const [capturando, setCapturando] = useState(false)
  const [ocultarParaCaptura, setOcultarParaCaptura] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [enviado, setEnviado] = useState<number | null>(null)

  const sucio = comentario.trim().length > 0 || capturaFinal !== null

  const limpiar = useCallback(() => {
    setTipo('Idea')
    setComentario('')
    setCapturaOriginal(null)
    setCapturaFinal(null)
    setCapturaMuyGrande(false)
    setAceptaCaptura(false)
    setError('')
  }, [])

  const cerrar = useCallback(() => {
    setAbierto(false)
    setEnviado(null)
    limpiar()
  }, [limpiar])

  const intentarCerrar = useCallback(() => {
    if (sucio && enviado === null) {
      confirmarCierre(cerrar)
      return
    }
    cerrar()
  }, [sucio, enviado, cerrar])

  useEffect(() => {
    if (!abierto) return
    function alTeclear(evento: KeyboardEvent) {
      if (evento.key === 'Escape') intentarCerrar()
    }
    window.addEventListener('keydown', alTeclear)
    return () => window.removeEventListener('keydown', alTeclear)
  }, [abierto, intentarCerrar])

  const actualizarCaptura = useCallback((dataUrl: string) => {
    if (dataUrl.length > MAX_CAPTURA_BASE64) {
      setError(
        'La captura es muy grande. Intenta enviarla desde una pantalla con menos contenido.',
      )
      setCapturaMuyGrande(true)
      return
    }
    setError('')
    setCapturaMuyGrande(false)
    setCapturaFinal(dataUrl)
  }, [])

  async function capturar() {
    setError('')
    setCapturando(true)
    setOcultarParaCaptura(true)
    try {
      // Dejar que el navegador pinte la pantalla sin el widget antes de capturar.
      await new Promise<void>((resolver) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolver()))
      })
      const dataUrl = await toJpeg(document.body, {
        quality: 0.82,
        pixelRatio: 1,
        backgroundColor: getComputedStyle(document.body).backgroundColor || '#f5ecdb',
        skipFonts: true,
        filter: (nodo) =>
          !(nodo instanceof HTMLElement && nodo.dataset.feedbackIgnore === 'true'),
      })
      if (dataUrl.length > MAX_CAPTURA_BASE64) {
        setError(
          'La captura es muy grande. Intenta enviarla desde una pantalla con menos contenido.',
        )
        return
      }
      setCapturaOriginal(dataUrl)
      setCapturaFinal(dataUrl)
      setCapturaMuyGrande(false)
      setAceptaCaptura(false)
    } catch {
      setError('No se pudo tomar la captura. Puedes enviar el comentario sin imagen.')
    } finally {
      setOcultarParaCaptura(false)
      setCapturando(false)
    }
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    setError('')
    const texto = comentario.trim()
    if (texto.length < 3) {
      setError('Cuéntanos un poco más (mínimo 3 caracteres).')
      return
    }
    if (capturaFinal && !aceptaCaptura) {
      setError('Confirma que revisaste la captura y tapaste los datos sensibles.')
      return
    }
    setEnviando(true)
    try {
      const base64 = capturaFinal ? capturaFinal.split(',')[1] : ''
      const creado = await crearFeedback({
        tipo,
        comentario: texto,
        contexto: contextoFeedback(usuario),
        ...(capturaFinal
          ? {
              captura_base64: base64,
              captura_mime: 'image/jpeg',
              captura_nombre: `feedback-${Date.now()}.jpg`,
            }
          : {}),
      })
      setEnviado(creado.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo enviar el feedback.')
    } finally {
      setEnviando(false)
    }
  }

  if (!tienePermiso('feedback.crear')) return null

  return (
    <div
      className={
        ocultarParaCaptura ? 'feedback-widget feedback-widget--oculto' : 'feedback-widget'
      }
      data-feedback-ignore="true"
    >
      <button
        type="button"
        className="feedback-fab"
        aria-label="Abrir feedback"
        title="Enviar feedback"
        onClick={() => {
          setAbierto(true)
          setError('')
        }}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M21 11.5a8.4 8.4 0 0 1-8.5 8.3 8.6 8.6 0 0 1-3.6-.8L4 21l1.7-4.4a8 8 0 0 1-1.2-4.3A8.4 8.4 0 0 1 13 4a8.4 8.4 0 0 1 8 7.5Z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
        </svg>
        <span>Feedback</span>
      </button>

      {abierto && (
        <div className="modal-overlay feedback-overlay" onClick={intentarCerrar}>
          <form
            className="modal modal--ancho feedback-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Enviar feedback"
            onClick={(evento) => evento.stopPropagation()}
            onSubmit={enviar}
          >
            <div className="feedback-modal__head">
              <div>
                <h2>Enviar feedback</h2>
                <p className="ayuda">
                  Tu comentario llega directamente al equipo administrador.
                </p>
              </div>
              <button
                type="button"
                className="feedback-cerrar"
                aria-label="Cerrar feedback"
                onClick={intentarCerrar}
              >
                ×
              </button>
            </div>

            {enviado !== null ? (
              <div className="feedback-exito" role="status">
                <strong>¡Gracias! Tu feedback quedó registrado.</strong>
                <p className="ayuda">Referencia #{enviado}. El equipo lo revisará pronto.</p>
                <div className="acciones">
                  <button type="button" className="boton boton--secundario" onClick={cerrar}>
                    Cerrar
                  </button>
                  <button
                    type="button"
                    className="boton"
                    onClick={() => {
                      setEnviado(null)
                      limpiar()
                    }}
                  >
                    Enviar otro
                  </button>
                </div>
              </div>
            ) : (
              <>
                {error && <p className="error">{error}</p>}

                <div className="feedback-tipos" role="group" aria-label="Tipo de feedback">
                  {TIPOS.map((opcion) => (
                    <button
                      key={opcion.valor}
                      type="button"
                      className={
                        tipo === opcion.valor
                          ? 'feedback-tipo feedback-tipo--activo'
                          : 'feedback-tipo'
                      }
                      aria-pressed={tipo === opcion.valor}
                      onClick={() => setTipo(opcion.valor)}
                    >
                      {opcion.etiqueta}
                    </button>
                  ))}
                </div>

                <label>
                  Comentario
                  <textarea
                    value={comentario}
                    onChange={(evento) => setComentario(evento.target.value)}
                    placeholder="¿Qué pasó? ¿Qué esperabas que pasara? Incluye los pasos para reproducirlo si es un error."
                    maxLength={4000}
                    minLength={3}
                    rows={5}
                    required
                    autoFocus
                  />
                </label>

                <div className="feedback-captura">
                  <div className="feedback-captura__acciones">
                    <button
                      type="button"
                      className="boton boton--secundario boton--mini"
                      onClick={() => void capturar()}
                      disabled={capturando || enviando}
                    >
                      {capturando
                        ? 'Capturando…'
                        : capturaOriginal
                          ? 'Volver a capturar'
                          : 'Capturar pantalla'}
                    </button>
                    {capturaFinal && (
                      <button
                        type="button"
                        className="boton boton--mini"
                        onClick={() => {
                          setCapturaOriginal(null)
                          setCapturaFinal(null)
                          setCapturaMuyGrande(false)
                          setAceptaCaptura(false)
                        }}
                      >
                        Quitar captura
                      </button>
                    )}
                  </div>
                  <p className="ayuda feedback-aviso">
                    La captura puede incluir nombres, montos o datos de clientes. Revisa y
                    tapa lo sensible antes de enviarla.
                  </p>
                  {capturaOriginal && (
                    <EditorCaptura src={capturaOriginal} onCambiar={actualizarCaptura} />
                  )}
                  {capturaFinal && (
                    <label className="check feedback-consentimiento">
                      <input
                        type="checkbox"
                        checked={aceptaCaptura}
                        onChange={(evento) => setAceptaCaptura(evento.target.checked)}
                      />
                      Confirmo que revisé la captura y tapé los datos sensibles.
                    </label>
                  )}
                </div>

                <div className="acciones">
                  <button
                    type="button"
                    className="boton boton--secundario"
                    onClick={intentarCerrar}
                    disabled={enviando}
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="boton"
                    disabled={
                      enviando ||
                      capturaMuyGrande ||
                      comentario.trim().length < 3 ||
                      (capturaFinal !== null && !aceptaCaptura)
                    }
                  >
                    {enviando ? 'Enviando…' : 'Enviar feedback'}
                  </button>
                </div>
              </>
            )}
          </form>
        </div>
      )}
    </div>
  )
}
