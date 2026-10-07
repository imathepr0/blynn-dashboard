// Configuración de la conexión con el backend de Blynn.
//
// La dirección del backend viene de la variable de entorno VITE_API_URL
// (por ejemplo https://api.blynn.cl/api/v1). En desarrollo, si no se define,
// se usa el backend local. En producción NO hay valor por defecto a propósito:
// es preferible un error claro a que la app hable con una dirección equivocada.

const ES_LOCAL = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/i;

/**
 * Evalúa una URL de backend. Devuelve un mensaje de problema o null si está bien.
 * Exigir https en producción evita que los tokens viajen sin cifrar.
 */
export function evaluarConfiguracion(url, esProduccion) {
  if (!url) {
    return "La aplicación no está configurada: falta la variable VITE_API_URL con la dirección del backend.";
  }
  if (esProduccion && !url.startsWith("https://") && !ES_LOCAL.test(url)) {
    return "VITE_API_URL debe empezar con https:// en producción (de lo contrario las credenciales viajarían sin cifrar).";
  }
  return null;
}

function resolverUrlBase() {
  const configurada = (import.meta.env.VITE_API_URL || "").trim().replace(/\/+$/, "");
  if (configurada) return configurada;
  return import.meta.env.DEV ? "http://localhost:8000/api/v1" : "";
}

export const API_URL = resolverUrlBase();

export function problemaDeConfiguracion() {
  return evaluarConfiguracion(API_URL, import.meta.env.PROD);
}
