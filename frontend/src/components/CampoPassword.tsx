import { useState, type InputHTMLAttributes } from 'react'

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>

/**
 * Campo de contraseña con un "ojito" para mostrar u ocultar lo digitado.
 *
 * Se usa igual que un `<input>` normal (acepta todas sus props salvo `type`,
 * que queda controlado por el componente). El botón nunca envía el formulario
 * ni roba el foco al campo.
 */
export function CampoPassword(props: Props) {
  const [visible, setVisible] = useState(false)

  return (
    <span className="campo-password">
      <input {...props} type={visible ? 'text' : 'password'} />
      <button
        type="button"
        className="campo-password__ojo"
        onClick={(e) => {
          // Evita que el <label> que envuelve al campo reenvíe el clic al input.
          e.preventDefault()
          setVisible((v) => !v)
        }}
        aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
        aria-pressed={visible}
        title={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
      >
        {visible ? <IconoOjoTachado /> : <IconoOjo />}
      </button>
    </span>
  )
}

function IconoOjo() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function IconoOjoTachado() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
      <line x1="4" y1="20" x2="20" y2="4" />
    </svg>
  )
}
