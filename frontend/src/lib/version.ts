// VITE_APP_VERSION permite sobrescribir la versión en un despliegue puntual.
// Si no está definida, se usa la versión del package.json inyectada por Vite.
export const APP_VERSION =
  import.meta.env.VITE_APP_VERSION || (typeof __APP_VERSION__ === 'string' ? __APP_VERSION__ : 'dev')
