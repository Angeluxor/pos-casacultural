import { useContext } from 'react'
import { OfflineContext } from './context'

export function useOffline() {
  return useContext(OfflineContext)
}
