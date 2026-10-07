import React from 'react'
import ReactDOM from 'react-dom/client'
import App from '@/App.jsx'
import { ApiError } from '@/api'
import { mostrarError } from '@/lib/errores'
import '@/index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
    <App />
)

// Red de seguridad: si una pantalla llama a la API sin atrapar el error (p. ej.
// sin conexión o un dato rechazado por el servidor), se avisa con un mensaje
// claro en vez de fallar en silencio. Los 401 los maneja la sesión (AuthContext).
window.addEventListener('unhandledrejection', (event) => {
  const error = event.reason
  if (error instanceof ApiError && error.status !== 401) {
    event.preventDefault()
    mostrarError(error)
  }
})
