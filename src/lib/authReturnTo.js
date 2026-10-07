// Compartido por las pantallas de acceso (Login y Register) y por
// ProtectedRoute, que manda al login recordando a qué página volver. La
// validación del destino está en un solo lugar porque es sensible para la
// seguridad y fácil de romper sin darse cuenta.

// Resuelve ?returnTo= a una ruta segura del mismo sitio; si no, "/".
//
// Comprobar solo que sea del mismo origen no basta: un valor como /.//evil.com
// o /\evil.com se interpreta como del mismo origen pero se normaliza a
// //evil.com (protocolo relativo) al asignarlo a location.href, lo que sería
// una redirección abierta. Por eso se exige que la ruta resultante tenga
// exactamente una barra inicial (sin prefijo "//" ni barras invertidas).
export function resolverReturnTo(raw, origin) {
  if (!raw) return "/";
  try {
    const url = new URL(raw, origin);
    if (url.origin !== origin) return "/";
    const path = url.pathname + url.search;
    if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\")) return "/";
    return path;
  } catch {
    return "/";
  }
}

export function safeReturnTo() {
  const raw = new URLSearchParams(window.location.search).get("returnTo");
  return resolverReturnTo(raw, window.location.origin);
}
