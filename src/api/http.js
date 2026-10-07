// Cliente HTTP del backend de Blynn.
//
// Responsabilidades:
//  * Enviar las peticiones con el access token y traducir las respuestas/errores.
//  * Renovar la sesión cuando el access token vence (401), UNA sola vez y sin
//    que dos renovaciones simultáneas se pisen.
//
// Por qué la renovación es tan cuidadosa: el backend usa refresh tokens de un
// solo uso. Si el MISMO refresh token llega dos veces lo interpreta como robo
// y cierra la sesión completa. Por eso:
//   1. Dentro de la pestaña, todas las peticiones que fallan con 401 comparten
//      UNA sola renovación ("single-flight").
//   2. Entre pestañas, la renovación se hace bajo un bloqueo del navegador
//      (Web Locks). Al obtenerlo se vuelve a leer el almacén: si otra pestaña
//      ya renovó mientras esperábamos, se usan sus tokens sin llamar al servidor.
//   3. Un fallo de red o del servidor al renovar NO cierra la sesión (solo un
//      401 del backend, que significa que el refresh token ya no sirve, lo hace).

import { API_URL, problemaDeConfiguracion } from "./config";
import { tokenStore } from "./tokenStore";
import { ApiError } from "./errors";

const TIMEOUT_MS = 30_000;
// Un escaneo de boleta puede incluir despertar el servicio de OCR (el plan gratuito
// se duerme) y procesar la foto. Debe ser MAYOR que OCR_SERVICE_TIMEOUT_SECONDS del
// backend (180 s) para que el error que se muestre sea el del servidor, no un corte
// nuestro.
export const TIMEOUT_ESCANEO_MS = 200_000;
const NOMBRE_BLOQUEO = "blynn-auth-refresh";

function construirUrl(ruta, params) {
  const url = `${API_URL}${ruta}`;
  if (!params) return url;
  const consulta = new URLSearchParams();
  for (const [clave, valor] of Object.entries(params)) {
    if (valor !== undefined && valor !== null && valor !== "") consulta.set(clave, String(valor));
  }
  const texto = consulta.toString();
  return texto ? `${url}?${texto}` : url;
}

async function leerCuerpo(respuesta) {
  if (respuesta.status === 204) return null;
  const texto = await respuesta.text();
  if (!texto) return null;
  try {
    return JSON.parse(texto);
  } catch {
    return null; // respuesta que no es JSON (p. ej. página de error de un proxy)
  }
}

/** Una petición HTTP sin lógica de sesión. Lanza ApiError(0) si no hay respuesta. */
async function enviar(metodo, ruta, { json, formData, params, token, timeoutMs = TIMEOUT_MS } = {}) {
  const control = new AbortController();
  const temporizador = setTimeout(() => control.abort(), timeoutMs);
  const cabeceras = { Accept: "application/json" };
  if (json !== undefined) cabeceras["Content-Type"] = "application/json";
  // Con `formData` NO se pone Content-Type: el navegador lo agrega con el "boundary" correcto.
  if (token) cabeceras.Authorization = `Bearer ${token}`;

  let respuesta;
  try {
    respuesta = await fetch(construirUrl(ruta, params), {
      method: metodo,
      headers: cabeceras,
      body: json !== undefined ? JSON.stringify(json) : formData,
      credentials: "omit", // la autenticación va por cabecera, nunca por cookies
      signal: control.signal,
    });
  } catch (e) {
    const agotado = e?.name === "AbortError";
    throw new ApiError(
      0,
      agotado
        ? "El servidor tardó demasiado en responder. Inténtalo de nuevo."
        : "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo."
    );
  } finally {
    clearTimeout(temporizador);
  }
  const cuerpo = await leerCuerpo(respuesta);
  return { status: respuesta.status, ok: respuesta.ok, cuerpo };
}

// --------------------------------------------------------------------- //
// Renovación de sesión
// --------------------------------------------------------------------- //
let renovacionEnCurso = null;

async function ejecutarRenovacion(tokenUsado) {
  const { access, refresh } = tokenStore.leer();
  if (!refresh) throw new ApiError(401, "Tu sesión expiró. Inicia sesión nuevamente.");

  // Otra pestaña (o una llamada anterior) ya renovó: usar sus tokens.
  if (access && access !== tokenUsado) return access;

  // Si esto lanza ApiError(0) (sin red) la sesión se conserva.
  const r = await enviar("POST", "/auth/refresh", { json: { refresh_token: refresh } });

  if (r.ok) {
    tokenStore.guardar({ access: r.cuerpo.access_token, refresh: r.cuerpo.refresh_token });
    return r.cuerpo.access_token;
  }
  if (r.status === 401 || r.status === 422) {
    // El refresh token ya no sirve (vencido, revocado o reutilizado): sesión terminada.
    tokenStore.borrar();
    throw new ApiError(401, "Tu sesión expiró. Inicia sesión nuevamente.");
  }
  // 429, 5xx...: fallo transitorio, NO se cierra la sesión.
  throw errorDesdeRespuesta(r);
}

/** Renueva la sesión una sola vez aunque lo pidan muchas peticiones a la vez. */
export function renovarSesion(tokenUsado) {
  if (!renovacionEnCurso) {
    const trabajo = () => ejecutarRenovacion(tokenUsado);
    const conBloqueo =
      typeof navigator !== "undefined" && navigator.locks?.request
        ? navigator.locks.request(NOMBRE_BLOQUEO, trabajo)
        : trabajo();
    renovacionEnCurso = Promise.resolve(conBloqueo).finally(() => {
      renovacionEnCurso = null;
    });
  }
  return renovacionEnCurso;
}

// --------------------------------------------------------------------- //
// API pública del cliente
// --------------------------------------------------------------------- //
function errorDesdeRespuesta(r) {
  return new ApiError(r.status, r.cuerpo?.detail ?? null);
}

/**
 * Hace una petición al backend.
 * @param {string} metodo  GET, POST, PATCH, DELETE
 * @param {string} ruta    Ruta bajo la URL base, p. ej. "/expenses"
 * @param {{json?: any, formData?: FormData, params?: object, auth?: boolean, timeoutMs?: number}} opciones
 *        auth=false para endpoints públicos (login, registro, refresh...).
 *        formData para subir archivos; timeoutMs para operaciones largas (por defecto 30 s).
 */
export async function request(metodo, ruta, { json, formData, params, auth = true, timeoutMs } = {}) {
  const problema = problemaDeConfiguracion();
  if (problema) throw new ApiError(0, problema, { code: "config" });

  const tokenUsado = auth ? tokenStore.leer().access : null;
  let r = await enviar(metodo, ruta, { json, formData, params, token: tokenUsado, timeoutMs });

  if (r.status === 401 && auth && tokenUsado) {
    // El access token venció: una renovación y UN reintento.
    const nuevo = await renovarSesion(tokenUsado);
    r = await enviar(metodo, ruta, { json, formData, params, token: nuevo, timeoutMs });
    if (r.status === 401) tokenStore.borrar(); // sigue sin servir: la sesión no es válida
  }

  if (!r.ok) throw errorDesdeRespuesta(r);
  return r.cuerpo;
}
