import { apiBlob, apiFetch, apiJson } from './client'
import type { Pagina } from './types'

export type TipoFeedback = 'Bug' | 'Idea' | 'Duda' | 'Otro'
export type EstadoFeedback = 'Nuevo' | 'En revisión' | 'Resuelto' | 'Descartado'
export type PrioridadFeedback = 'Baja' | 'Media' | 'Alta'

export type Feedback = {
  id: number
  tipo: TipoFeedback
  comentario: string
  contexto: Record<string, unknown>
  estado: EstadoFeedback
  prioridad: PrioridadFeedback
  etiquetas: string[]
  usuario_id: number | null
  usuario_nombre: string
  responsable_id: number | null
  responsable_nombre: string | null
  tiene_captura: boolean
  captura_mime: string | null
  captura_nombre: string | null
  notas_internas: string | null
  creado_en: string
  actualizado_en: string
  resuelto_en: string | null
}

export type FeedbackCrear = {
  tipo: TipoFeedback
  comentario: string
  contexto: Record<string, unknown>
  captura_base64?: string
  captura_mime?: string
  captura_nombre?: string
}

export type FeedbackActualizar = {
  estado?: EstadoFeedback
  prioridad?: PrioridadFeedback
  etiquetas?: string[]
  notas_internas?: string | null
  responsable_id?: number | null
}

export function crearFeedback(datos: FeedbackCrear): Promise<Feedback> {
  return apiJson<Feedback>('/api/feedback/', 'POST', datos)
}

export function paginaFeedback(params: {
  skip: number
  limit: number
  buscar?: string
  estado?: EstadoFeedback | ''
  tipo?: TipoFeedback | ''
  prioridad?: PrioridadFeedback | ''
}): Promise<Pagina<Feedback>> {
  const q = new URLSearchParams()
  q.set('skip', String(params.skip))
  q.set('limit', String(params.limit))
  if (params.buscar) q.set('buscar', params.buscar)
  if (params.estado) q.set('estado', params.estado)
  if (params.tipo) q.set('tipo', params.tipo)
  if (params.prioridad) q.set('prioridad', params.prioridad)
  return apiFetch<Pagina<Feedback>>(`/api/feedback/?${q.toString()}`)
}

export function actualizarFeedback(
  id: number,
  datos: FeedbackActualizar,
): Promise<Feedback> {
  return apiJson<Feedback>(`/api/feedback/${id}`, 'PATCH', datos)
}

export function obtenerCapturaFeedback(id: number): Promise<Blob> {
  return apiBlob(`/api/feedback/${id}/captura`)
}
