export function confirmarCierre(onCerrar: () => void): void {
  if (window.confirm('¿Cerrar sin guardar? Se perderán los datos ingresados.')) {
    onCerrar()
  }
}
