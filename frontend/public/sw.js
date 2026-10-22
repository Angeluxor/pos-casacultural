/*
 * Service worker del POS.
 *
 * Objetivo: que la aplicación abra aunque no haya red. Las llamadas a /api
 * nunca se cachean: los datos de ventas viven en la cola local y se
 * sincronizan cuando vuelve la conexión.
 */
const CACHE = 'pos-casacultural-v1'
const SHELL = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/icon-192.png',
  '/icon-512.png',
  '/icon-maskable-512.png',
  '/apple-touch-icon.png',
  '/LogoCO-Photoroom.png',
  '/favicon.svg',
  '/icons.svg',
]

async function precachear() {
  const cache = await caches.open(CACHE)
  await cache.addAll(SHELL)

  // El HTML referencia assets con hash (JS/CSS) que no conocemos en tiempo de
  // compilación. Se leen del index y se cachean para que la app abra offline
  // incluso si el usuario cierra la pestaña después de la primera carga.
  try {
    const respuesta = await fetch('/index.html', { cache: 'no-cache' })
    if (!respuesta.ok) return
    const html = await respuesta.clone().text()
    await cache.put('/index.html', respuesta)
    const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[^"]+\.(?:js|css))"/g)].map(
      (coincidencia) => coincidencia[1],
    )
    await Promise.allSettled(assets.map((url) => cache.add(url)))
  } catch {
    // Si falla el precache de assets, el runtime cache los guardará al vuelo.
  }
}

self.addEventListener('install', (event) => {
  event.waitUntil(precachear().then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((claves) =>
        Promise.all(
          claves.filter((clave) => clave !== CACHE).map((clave) => caches.delete(clave)),
        ),
      )
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') return

  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/')) return

  // Navegación: red primero para recoger despliegues nuevos; si falla, se
  // sirve el index cacheado y la SPA arranca offline.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copia = response.clone()
            caches.open(CACHE).then((cache) => cache.put('/index.html', copia))
          }
          return response
        })
        .catch(() => caches.match('/index.html')),
    )
    return
  }

  // Assets con hash de Vite: caché primero, red como respaldo.
  event.respondWith(
    caches.match(request).then((cacheado) => {
      if (cacheado) return cacheado
      return fetch(request).then((response) => {
        if (response.ok && response.type === 'basic') {
          const copia = response.clone()
          caches.open(CACHE).then((cache) => cache.put(request, copia))
        }
        return response
      })
    }),
  )
})
