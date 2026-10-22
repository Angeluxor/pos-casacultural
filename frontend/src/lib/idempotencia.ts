/**
 * Clave única para que reintentar una venta no la duplique.
 *
 * El backend la recibe en la cabecera ``Idempotency-Key``. Si la petición
 * original sí alcanzó a guardarse pero la respuesta se perdió (timeout, red
 * móvil, cold start de Render), el reintento devuelve la misma factura.
 */
export function crearClaveIdempotencia(): string {
  const cryptoApi = globalThis.crypto
  if (cryptoApi && typeof cryptoApi.randomUUID === 'function') {
    return cryptoApi.randomUUID()
  }
  // Respaldo para navegadores antiguos o contextos no seguros.
  const aleatorio = Math.random().toString(36).slice(2)
  return `idem-${Date.now()}-${aleatorio}`
}
