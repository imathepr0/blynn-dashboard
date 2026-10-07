import { vi } from "vitest";

// Servidor falso para pruebas: `manejador({metodo, ruta, cuerpo, autorizacion, init})`
// devuelve `{status, body}` (o un Error para simular que no hay red).
export function servidor(manejador) {
  const llamadas = [];
  const fetchFalso = vi.fn(async (url, init) => {
    const ruta = url.replace(/^https?:\/\/[^/]+\/api\/v1/, "");
    const info = {
      metodo: init.method,
      ruta,
      cuerpo: typeof init.body === "string" ? JSON.parse(init.body) : undefined,
      formData: init.body instanceof FormData ? init.body : undefined,
      autorizacion: init.headers.Authorization,
      init,
    };
    llamadas.push(info);
    const r = await manejador(info);
    if (r instanceof Error) throw r;
    return new Response(r.status === 204 ? null : JSON.stringify(r.body ?? null), { status: r.status });
  });
  vi.stubGlobal("fetch", fetchFalso);
  return { llamadas, fetchFalso, cuantas: (ruta) => llamadas.filter((l) => l.ruta === ruta).length };
}

export const sesion = (n = 1) => ({ access: `acceso-${n}`, refresh: `refresco-${n}` });
export const tokensRespuesta = (n) => ({ access_token: `acceso-${n}`, refresh_token: `refresco-${n}`, token_type: "bearer", expires_in: 900 });
export const usuarioEjemplo = (extra = {}) => ({ id: "u1", email: "ana@correo.cl", full_name: "Ana", role: "user", onboarded: true, monthly_budget: 0, preferences: {}, created_date: "2026-09-29T00:00:00Z", ...extra });
