export const moneda = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
})

const fechaHora = new Intl.DateTimeFormat('es-CO', {
  dateStyle: 'short',
  timeStyle: 'short',
})

export function formatoFecha(iso: string): string {
  return fechaHora.format(new Date(iso))
}

/** Formas de pago de una venta, sin repetir (una venta puede ser mixta). */
export function formasPagoUnicas(
  pagos: { forma_pago: string }[],
): string {
  const formas = Array.from(new Set(pagos.map((p) => p.forma_pago)))
  return formas.length > 0 ? formas.join(' + ') : '—'
}
