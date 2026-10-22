import { createContext } from 'react'
import type { OperacionOffline } from './almacen'
import type { ResultadoSincronizacion } from './sync'

export type OfflineContexto = {
  enLinea: boolean
  operaciones: OperacionOffline[]
  pendientes: number
  sincronizando: boolean
  ultimoError: string | null
  /** Se incrementa después de una sincronización exitosa. */
  version: number
  sincronizarAhora: () => Promise<ResultadoSincronizacion | null>
  recargarCola: () => void
}

const noop = async () => null

export const OfflineContext = createContext<OfflineContexto>({
  enLinea: true,
  operaciones: [],
  pendientes: 0,
  sincronizando: false,
  ultimoError: null,
  version: 0,
  sincronizarAhora: noop,
  recargarCola: () => {},
})
