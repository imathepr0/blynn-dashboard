// API de Blynn: una función por operación del backend (ver backend/README.md).
//
// Las pantallas importan `api` de aquí; nunca llaman a fetch directamente.
// Toda modificación de datos avisa a la app (ver events.js) para que las vistas
// con totales se actualicen.

import { request, TIMEOUT_ESCANEO_MS } from "./http";
import { tokenStore } from "./tokenStore";
import { emitirCambio } from "./events";

export { ApiError, describirError } from "./errors";
export { alCambiar } from "./events";
export { tokenStore } from "./tokenStore";

const MAX_POR_LOTE = 50; // límite del backend para POST /expenses/bulk

// Recurso REST estándar: listar, obtener, crear, actualizar (PATCH) y borrar.
function recurso(ruta, entidad) {
  return {
    list: (params) => request("GET", ruta, { params }),
    get: (id) => request("GET", `${ruta}/${id}`),
    async create(datos) {
      const creado = await request("POST", ruta, { json: datos });
      emitirCambio(entidad);
      return creado;
    },
    async update(id, cambios) {
      const actualizado = await request("PATCH", `${ruta}/${id}`, { json: cambios });
      emitirCambio(entidad);
      return actualizado;
    },
    async remove(id) {
      await request("DELETE", `${ruta}/${id}`);
      emitirCambio(entidad);
    },
  };
}

function guardarSesion(respuesta) {
  tokenStore.guardar({ access: respuesta.access_token, refresh: respuesta.refresh_token });
  return respuesta.user;
}

export const api = {
  // ---- Sesión ----------------------------------------------------------
  auth: {
    /** Crea la cuenta e inicia sesión. Devuelve el usuario. */
    async register({ email, password, fullName }) {
      const json = { email, password };
      if (fullName) json.full_name = fullName;
      return guardarSesion(await request("POST", "/auth/register", { json, auth: false }));
    },
    /** Inicia sesión. Devuelve el usuario. */
    async login(email, password) {
      return guardarSesion(await request("POST", "/auth/login", { json: { email, password }, auth: false }));
    },
    /**
     * Cierra la sesión. Los tokens locales se borran AL INSTANTE (antes de cualquier
     * espera de red) y luego se avisa al servidor para que revoque la sesión; si no
     * hay conexión, la sesión local igual queda cerrada.
     */
    async logout() {
      const { refresh } = tokenStore.leer();
      tokenStore.borrar();
      if (!refresh) return;
      try {
        await request("POST", "/auth/logout", { json: { refresh_token: refresh }, auth: false });
      } catch {
        /* sin red: el servidor revocará el token cuando venza */
      }
    },
    /** Cierra TODAS las sesiones de la cuenta (p. ej. si se perdió un dispositivo). */
    async logoutAll() {
      try {
        await request("POST", "/auth/logout-all");
      } finally {
        tokenStore.borrar();
      }
    },
  },

  // ---- Perfil ----------------------------------------------------------
  me: {
    get: () => request("GET", "/me"),
    /** Cambia nombre, preferencias, encuesta o presupuesto mensual. */
    update: (cambios) => request("PATCH", "/me", { json: cambios }),
    /** Borra todos los datos y recrea las categorías por defecto (operación atómica). */
    async reset() {
      const usuario = await request("POST", "/me/reset", { json: { confirm: true } });
      ["categories", "expenses", "incomes", "goals", "contributions"].forEach(emitirCambio);
      return usuario;
    },
  },

  // ---- Datos -----------------------------------------------------------
  categories: {
    ...recurso("/categories", "categories"),
    /** Crea las categorías por defecto que falten (se puede llamar varias veces). */
    async ensureDefaults() {
      const lista = await request("POST", "/categories/defaults");
      emitirCambio("categories");
      return lista;
    },
  },

  expenses: {
    ...recurso("/expenses", "expenses"),
    /** Crea muchos gastos; se envían de a 50 (cada tanda es atómica). */
    async bulkCreate(items) {
      const creados = [];
      for (let i = 0; i < items.length; i += MAX_POR_LOTE) {
        const lote = items.slice(i, i + MAX_POR_LOTE);
        creados.push(...(await request("POST", "/expenses/bulk", { json: { items: lote } })));
      }
      if (creados.length) emitirCambio("expenses");
      return creados;
    },
  },

  incomes: recurso("/incomes", "incomes"),

  // ---- Escaneo de boletas ----------------------------------------------
  boletas: {
    /**
     * Envía la foto de una boleta al backend, que la lee con el servicio de escaneo.
     * Devuelve la LECTURA (estado, datos, confianza): NO crea ningún gasto; la persona
     * siempre revisa y confirma antes de guardar. Ver `processBoletaFile`.
     * @param {File|Blob} archivo  JPG, PNG o WEBP (máx. 10 MB)
     * @param {"camera"|"file"} origen
     */
    scan(archivo, origen = "file") {
      const formData = new FormData();
      formData.append("file", archivo, archivo.name || "boleta.jpg");
      formData.append("source", origen);
      return request("POST", "/boletas/scan", { formData, timeoutMs: TIMEOUT_ESCANEO_MS });
    },
  },

  goals: {
    ...recurso("/goals", "goals"),
    /**
     * Registra un aporte y suma su monto a la meta en una sola operación.
     * Devuelve { contribution, goal }.
     */
    async addContribution(goalId, { amount, date, mode = "manual", next_contribution_date }) {
      const json = { amount, date, mode };
      if (next_contribution_date !== undefined) json.next_contribution_date = next_contribution_date;
      const resultado = await request("POST", `/goals/${goalId}/contributions`, { json });
      emitirCambio("goals");
      emitirCambio("contributions");
      return resultado;
    },
  },

  contributions: {
    list: (params) => request("GET", "/contributions", { params }),
    /** Deshace un aporte y descuenta su monto de la meta. Devuelve la meta actualizada. */
    async undo(contributionId) {
      const meta = await request("DELETE", `/contributions/${contributionId}`);
      emitirCambio("goals");
      emitirCambio("contributions");
      return meta;
    },
  },
};
