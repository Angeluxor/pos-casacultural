import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import './App.css'
import App from './App.tsx'
import { AuthProvider } from './auth/AuthProvider.tsx'
import { OfflineProvider } from './offline/OfflineProvider.tsx'
import { instalarCapturaErrores } from './lib/feedbackContext.ts'
import { iniciarCapturaInstalacion } from './lib/instalarApp.ts'
import { getToken } from './api/client.ts'
import { enviarMuestrasCliente } from './api/metricas.ts'
import { iniciarMetricasCliente } from './lib/metricasCliente.ts'

instalarCapturaErrores()
iniciarCapturaInstalacion()
// Tiempos de respuesta vistos por el navegador, para diagnosticar lentitud.
iniciarMetricasCliente(async (lote) => {
  if (getToken()) await enviarMuestrasCliente(lote)
})

if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    void navigator.serviceWorker
      .register('/sw.js', { updateViaCache: 'none' })
      .catch(() => {
        // Sin service worker la app sigue funcionando, pero no abre sin red.
      })
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <OfflineProvider>
          <App />
        </OfflineProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
