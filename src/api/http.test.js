import { describe, expect, it, vi } from "vitest";
import { api, ApiError, alCambiar, describirError, tokenStore } from "./index";
import { request } from "./http";
import { evaluarConfiguracion } from "./config";
import { servidor, sesion, tokensRespuesta } from "@/test/servidorFalso";

describe("peticiones básicas", () => {
  it("envía el access token y los parámetros, omitiendo los vacíos", async () => {
    tokenStore.guardar(sesion());
    const s = servidor(() => ({ status: 200, body: [] }));
    await api.expenses.list({ sort: "-date", limit: 300, category: undefined, is_recurring: null, date_from: "" });
    expect(s.llamadas[0].ruta).toBe("/expenses?sort=-date&limit=300");
    expect(s.llamadas[0].autorizacion).toBe("Bearer acceso-1");
  });

  it("nunca envía cookies ni credenciales del navegador", async () => {
    tokenStore.guardar(sesion());
    const s = servidor(() => ({ status: 200, body: [] }));
    await api.categories.list();
    expect(s.llamadas[0].init.credentials).toBe("omit");
  });

  it("una respuesta 204 devuelve null", async () => {
    tokenStore.guardar(sesion());
    servidor(() => ({ status: 204 }));
    await expect(api.expenses.remove("x")).resolves.toBeUndefined();
  });

  it("una respuesta que no es JSON no rompe la app", async () => {
    tokenStore.guardar(sesion());
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>502 Bad Gateway</html>", { status: 502 })));
    const err = await request("GET", "/expenses").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(502);
    expect(describirError(err)).toMatch(/error en el servidor/);
  });

  it("sin conexión lanza ApiError(0) y NO cierra la sesión", async () => {
    tokenStore.guardar(sesion());
    servidor(() => new TypeError("Failed to fetch"));
    const err = await api.expenses.list().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
    expect(tokenStore.leer()).toEqual(sesion());
  });

  it("un tiempo de espera agotado se informa claramente", async () => {
    tokenStore.guardar(sesion());
    const abortar = new Error("abortado");
    abortar.name = "AbortError";
    servidor(() => abortar);
    const err = await api.expenses.list().catch((e) => e);
    expect(err.status).toBe(0);
    expect(describirError(err)).toMatch(/tardó demasiado/);
  });
});

describe("renovación de sesión", () => {
  it("ante un 401 renueva los tokens y reintenta con el nuevo access token", async () => {
    tokenStore.guardar(sesion(1));
    const s = servidor(({ ruta, autorizacion }) => {
      if (ruta === "/auth/refresh") return { status: 200, body: tokensRespuesta(2) };
      return autorizacion === "Bearer acceso-2" ? { status: 200, body: [{ id: 1 }] } : { status: 401, body: { detail: "No autorizado." } };
    });
    await expect(api.expenses.list()).resolves.toEqual([{ id: 1 }]);
    expect(s.cuantas("/auth/refresh")).toBe(1);
    expect(s.llamadas.find((l) => l.ruta === "/auth/refresh").cuerpo).toEqual({ refresh_token: "refresco-1" });
    expect(tokenStore.leer()).toEqual(sesion(2)); // los tokens rotaron y quedaron guardados
  });

  it("muchas peticiones que fallan a la vez comparten UNA sola renovación", async () => {
    tokenStore.guardar(sesion(1));
    const s = servidor(async ({ ruta, autorizacion }) => {
      if (ruta === "/auth/refresh") {
        await new Promise((r) => setTimeout(r, 30)); // la renovación tarda
        return { status: 200, body: tokensRespuesta(2) };
      }
      return autorizacion === "Bearer acceso-2" ? { status: 200, body: [] } : { status: 401, body: { detail: "No autorizado." } };
    });
    const resultados = await Promise.all([
      api.expenses.list(), api.incomes.list(), api.categories.list(), api.goals.list(), api.contributions.list(),
      api.me.get(), api.expenses.list({ limit: 5 }),
    ]);
    expect(resultados).toHaveLength(7);
    expect(s.cuantas("/auth/refresh")).toBe(1); // clave: el backend cerraría la sesión si se usara dos veces
  });

  it("si otra pestaña ya renovó mientras esperábamos, usa sus tokens sin llamar al servidor", async () => {
    tokenStore.guardar(sesion(1));
    // Simula el bloqueo entre pestañas: la función espera hasta que "la otra pestaña" termine.
    let liberar;
    const espera = new Promise((r) => (liberar = r));
    const locks = { request: vi.fn(async (nombre, trabajo) => { await espera; return trabajo(); }) };
    vi.stubGlobal("navigator", { ...navigator, locks });

    const s = servidor(({ ruta, autorizacion }) => {
      if (ruta === "/auth/refresh") return { status: 200, body: tokensRespuesta(99) }; // no debería llamarse
      return autorizacion === "Bearer acceso-2" ? { status: 200, body: ["ok"] } : { status: 401, body: {} };
    });

    const pendiente = api.expenses.list();
    await vi.waitFor(() => expect(locks.request).toHaveBeenCalled());
    tokenStore.guardar(sesion(2)); // la otra pestaña renovó
    liberar();

    await expect(pendiente).resolves.toEqual(["ok"]);
    expect(s.cuantas("/auth/refresh")).toBe(0);
    expect(locks.request.mock.calls[0][0]).toBe("blynn-auth-refresh");
  });

  it("si el backend rechaza el refresh token (401), la sesión termina y se avisa", async () => {
    tokenStore.guardar(sesion(1));
    const avisos = [];
    const cancelar = tokenStore.suscribir((t) => avisos.push(t));
    servidor(({ ruta }) => ({ status: 401, body: { detail: ruta === "/auth/refresh" ? "Sesión inválida o expirada. Inicia sesión nuevamente." : "No autorizado." } }));

    const err = await api.expenses.list().catch((e) => e);
    cancelar();
    expect(err.status).toBe(401);
    expect(tokenStore.leer()).toEqual({ access: null, refresh: null });
    expect(avisos.at(-1)).toEqual({ access: null, refresh: null });
  });

  it.each([
    ["sin red", () => new TypeError("Failed to fetch")],
    ["error 500", () => ({ status: 500, body: null })],
    ["límite de intentos 429", () => ({ status: 429, body: { detail: "Demasiados intentos." } })],
  ])("un fallo transitorio al renovar (%s) NO cierra la sesión", async (_nombre, respuestaRefresh) => {
    tokenStore.guardar(sesion(1));
    servidor(({ ruta }) => (ruta === "/auth/refresh" ? respuestaRefresh() : { status: 401, body: {} }));
    const err = await api.expenses.list().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(tokenStore.leer()).toEqual(sesion(1)); // la sesión sigue; se podrá reintentar
  });

  it("si tras renovar el servidor sigue respondiendo 401, cierra la sesión (no hay bucle)", async () => {
    tokenStore.guardar(sesion(1));
    const s = servidor(({ ruta }) => (ruta === "/auth/refresh" ? { status: 200, body: tokensRespuesta(2) } : { status: 401, body: {} }));
    const err = await api.expenses.list().catch((e) => e);
    expect(err.status).toBe(401);
    expect(s.cuantas("/auth/refresh")).toBe(1);
    expect(s.cuantas("/expenses")).toBe(2); // original + UN reintento
    expect(tokenStore.leer()).toEqual({ access: null, refresh: null });
  });

  it("los endpoints públicos (auth: false) nunca intentan renovar", async () => {
    tokenStore.guardar(sesion(1));
    const s = servidor(() => ({ status: 401, body: { detail: "Correo o contraseña incorrectos." } }));
    const err = await api.auth.login("a@b.cl", "mala").catch((e) => e);
    expect(err.status).toBe(401);
    expect(describirError(err)).toBe("Correo o contraseña incorrectos.");
    expect(s.cuantas("/auth/refresh")).toBe(0);
    expect(tokenStore.leer()).toEqual(sesion(1));
  });

  it("sin sesión iniciada, un 401 no intenta renovar", async () => {
    const s = servidor(() => ({ status: 401, body: { detail: "No autorizado." } }));
    await api.me.get().catch(() => {});
    expect(s.cuantas("/auth/refresh")).toBe(0);
  });
});

describe("sesión: registro, login y logout", () => {
  const usuario = { id: "u1", email: "ana@correo.cl", full_name: null };

  it("login guarda los tokens y devuelve el usuario", async () => {
    const s = servidor(() => ({ status: 200, body: { ...tokensRespuesta(1), user: usuario } }));
    await expect(api.auth.login("ana@correo.cl", "clave")).resolves.toEqual(usuario);
    expect(tokenStore.leer()).toEqual(sesion(1));
    expect(s.llamadas[0].autorizacion).toBeUndefined();
  });

  it("registro envía el nombre solo si se indicó", async () => {
    const s = servidor(() => ({ status: 201, body: { ...tokensRespuesta(1), user: usuario } }));
    await api.auth.register({ email: "ana@correo.cl", password: "clave-larga-1" });
    await api.auth.register({ email: "ana@correo.cl", password: "clave-larga-1", fullName: "Ana" });
    expect(s.llamadas[0].cuerpo).toEqual({ email: "ana@correo.cl", password: "clave-larga-1" });
    expect(s.llamadas[1].cuerpo).toEqual({ email: "ana@correo.cl", password: "clave-larga-1", full_name: "Ana" });
  });

  it("logout avisa al servidor con el refresh token y borra los tokens", async () => {
    tokenStore.guardar(sesion(1));
    const s = servidor(() => ({ status: 204 }));
    await api.auth.logout();
    expect(s.llamadas[0].ruta).toBe("/auth/logout");
    expect(s.llamadas[0].cuerpo).toEqual({ refresh_token: "refresco-1" });
    expect(tokenStore.leer()).toEqual({ access: null, refresh: null });
  });

  it("logout cierra la sesión local aunque no haya conexión", async () => {
    tokenStore.guardar(sesion(1));
    servidor(() => new TypeError("Failed to fetch"));
    await api.auth.logout();
    expect(tokenStore.leer()).toEqual({ access: null, refresh: null });
  });
});

describe("datos", () => {
  it("bulkCreate envía de a 50 y junta los resultados", async () => {
    tokenStore.guardar(sesion());
    const s = servidor(({ cuerpo }) => ({ status: 201, body: cuerpo.items.map((it, i) => ({ ...it, id: i })) }));
    const items = Array.from({ length: 120 }, (_, i) => ({ merchant: `T${i}` }));
    const creados = await api.expenses.bulkCreate(items);
    expect(creados).toHaveLength(120);
    expect(s.llamadas.map((l) => l.cuerpo.items.length)).toEqual([50, 50, 20]);
  });

  it("bulkCreate sin elementos no hace ninguna petición", async () => {
    const s = servidor(() => ({ status: 201, body: [] }));
    await expect(api.expenses.bulkCreate([])).resolves.toEqual([]);
    expect(s.llamadas).toHaveLength(0);
  });

  it("registrar un aporte envía solo lo necesario y devuelve aporte y meta", async () => {
    tokenStore.guardar(sesion());
    const s = servidor(() => ({ status: 201, body: { contribution: { id: "a" }, goal: { id: "g" } } }));
    const r = await api.goals.addContribution("g", { amount: 1000, date: "2026-09-29", mode: "aprobado", next_contribution_date: "2026-10-29" });
    expect(r).toEqual({ contribution: { id: "a" }, goal: { id: "g" } });
    expect(s.llamadas[0].ruta).toBe("/goals/g/contributions");
    expect(s.llamadas[0].cuerpo).toEqual({ amount: 1000, date: "2026-09-29", mode: "aprobado", next_contribution_date: "2026-10-29" });
    await api.goals.addContribution("g", { amount: 5, date: "2026-09-29" });
    expect(s.llamadas[1].cuerpo).toEqual({ amount: 5, date: "2026-09-29", mode: "manual" }); // sin fecha: el servidor no la toca
  });

  it("reiniciar la cuenta exige confirmar y avisa a todas las vistas", async () => {
    tokenStore.guardar(sesion());
    const s = servidor(() => ({ status: 200, body: { id: "u1" } }));
    const avisos = [];
    const cancelar = ["expenses", "incomes", "goals", "categories", "contributions"].map((e) => alCambiar(e, () => avisos.push(e)));
    await api.me.reset();
    cancelar.forEach((c) => c());
    expect(s.llamadas[0].cuerpo).toEqual({ confirm: true });
    expect(avisos.sort()).toEqual(["categories", "contributions", "expenses", "goals", "incomes"]);
  });

  it("toda modificación de gastos avisa a las vistas que muestran totales", async () => {
    tokenStore.guardar(sesion());
    servidor(({ ruta }) => ({ status: 200, body: ruta === "/expenses/bulk" ? [{}] : {} }));
    let avisos = 0;
    const cancelar = alCambiar("expenses", () => avisos++);
    await api.expenses.create({});
    await api.expenses.update("x", {});
    await api.expenses.remove("x");
    await api.expenses.bulkCreate([{}]);
    await api.expenses.list(); // leer no avisa
    await api.incomes.create({}); // otra entidad: no avisa a gastos
    cancelar();
    await api.expenses.create({}); // ya cancelado
    expect(avisos).toBe(4);
  });

  it("una modificación fallida no avisa de cambios", async () => {
    tokenStore.guardar(sesion());
    servidor(() => ({ status: 422, body: { detail: [] } }));
    let avisos = 0;
    const cancelar = alCambiar("expenses", () => avisos++);
    await api.expenses.create({}).catch(() => {});
    cancelar();
    expect(avisos).toBe(0);
  });
});

describe("mensajes de error", () => {
  const validacion = (loc, type, msg = "") => new ApiError(422, [{ loc: ["body", ...loc], type, msg }]);

  it.each([
    [validacion(["amount"], "greater_than"), "El monto debe ser mayor que 0."],
    [validacion(["amount"], "int_type"), "El monto debe ser un número entero."],
    [validacion(["date"], "date_parsing"), "La fecha no es una fecha válida."],
    [validacion(["merchant"], "string_too_long"), "El comercio es demasiado largo."],
    [validacion(["email"], "value_error", "value is not a valid email address"), "Ingresa un correo electrónico válido."],
    [validacion(["color"], "string_pattern_mismatch"), "El color tiene un formato inválido."],
    [validacion(["items", 2, "amount"], "greater_than"), "El monto debe ser mayor que 0."],
    [validacion(["category"], "value_error", "Value error, algo propio del backend"), "La categoría algo propio del backend."],
  ])("traduce errores de validación a español", (error, esperado) => {
    expect(describirError(error)).toBe(esperado);
  });

  it("junta varios errores sin repetirlos y limita la cantidad", () => {
    const err = new ApiError(422, ["amount", "date", "merchant", "category", "amount"].map((c) => ({ loc: ["body", c], type: "missing" })));
    expect(describirError(err)).toBe("El monto es obligatorio. La fecha es obligatorio. El comercio es obligatorio.");
  });

  it("usa el texto del servidor en los errores de negocio", () => {
    expect(describirError(new ApiError(409, "Ya existe una categoría con ese nombre."))).toBe("Ya existe una categoría con ese nombre.");
    expect(describirError(new ApiError(429, "Demasiados intentos. Intenta nuevamente en 15 min."))).toMatch(/Demasiados intentos/);
  });

  it("no expone detalles internos de errores 500", () => {
    expect(describirError(new ApiError(500, "Traceback: secreto"))).not.toMatch(/secreto/);
  });

  it("errores que no son de la API conservan su mensaje o uno genérico", () => {
    expect(describirError(new Error("boom"))).toBe("boom");
    expect(describirError(undefined)).toMatch(/inesperado/);
  });
});

describe("configuración", () => {
  it("exige la variable en producción y https", () => {
    expect(evaluarConfiguracion("", true)).toMatch(/VITE_API_URL/);
    expect(evaluarConfiguracion("http://api.blynn.cl/api/v1", true)).toMatch(/https/);
    expect(evaluarConfiguracion("https://api.blynn.cl/api/v1", true)).toBeNull();
  });
  it("permite http solo hacia localhost (pruebas locales de la versión de producción)", () => {
    expect(evaluarConfiguracion("http://localhost:8000/api/v1", true)).toBeNull();
    expect(evaluarConfiguracion("http://127.0.0.1:8000/api/v1", true)).toBeNull();
    expect(evaluarConfiguracion("http://localhost.evil.com/api/v1", true)).toMatch(/https/);
  });
  it("en desarrollo no exige https", () => {
    expect(evaluarConfiguracion("http://192.168.1.10:8000/api/v1", false)).toBeNull();
  });
});

describe("almacén de tokens", () => {
  it("guarda, lee, borra y avisa a los suscriptores", () => {
    const avisos = [];
    const cancelar = tokenStore.suscribir((t) => avisos.push(t));
    tokenStore.guardar(sesion(3));
    expect(tokenStore.leer()).toEqual(sesion(3));
    tokenStore.borrar();
    expect(tokenStore.leer()).toEqual({ access: null, refresh: null });
    cancelar();
    tokenStore.guardar(sesion(4));
    expect(avisos).toEqual([sesion(3), { access: null, refresh: null }]);
  });

  it("avisa cuando otra pestaña cambia los tokens (evento storage)", () => {
    const avisos = [];
    const cancelar = tokenStore.suscribir((t) => avisos.push(t));
    window.localStorage.setItem("blynn.access_token", "de-otra-pestaña");
    window.dispatchEvent(new StorageEvent("storage", { key: "blynn.access_token" }));
    window.dispatchEvent(new StorageEvent("storage", { key: "otra-clave-ajena" }));
    cancelar();
    expect(avisos).toHaveLength(1);
    expect(avisos[0].access).toBe("de-otra-pestaña");
  });

  it("un suscriptor que falla no impide avisar a los demás", () => {
    const bien = vi.fn();
    const c1 = tokenStore.suscribir(() => { throw new Error("falla"); });
    const c2 = tokenStore.suscribir(bien);
    tokenStore.guardar(sesion());
    c1(); c2();
    expect(bien).toHaveBeenCalled();
  });

  it("si localStorage no está disponible usa memoria", () => {
    const original = Object.getOwnPropertyDescriptor(window, "localStorage");
    Object.defineProperty(window, "localStorage", { configurable: true, get() { throw new Error("bloqueado"); } });
    try {
      tokenStore.guardar(sesion(7));
      expect(tokenStore.leer()).toEqual(sesion(7));
      tokenStore.borrar();
      expect(tokenStore.leer()).toEqual({ access: null, refresh: null });
    } finally {
      Object.defineProperty(window, "localStorage", original);
    }
  });
});

describe("subida de archivos (escaneo de boletas)", () => {
  it("envía FormData sin fijar Content-Type (el navegador agrega el boundary) y con la sesión", async () => {
    tokenStore.guardar(sesion());
    const s = servidor(() => ({ status: 200, body: { estado: "SUCCESS", mensaje: "ok" } }));
    const foto = new File([new Uint8Array(20)], "boleta.jpg", { type: "image/jpeg" });
    const r = await api.boletas.scan(foto, "camera");
    expect(r.estado).toBe("SUCCESS");
    const llamada = s.llamadas[0];
    expect(llamada.metodo).toBe("POST");
    expect(llamada.ruta).toBe("/boletas/scan");
    expect(llamada.autorizacion).toBe("Bearer acceso-1");
    expect(llamada.init.headers["Content-Type"]).toBeUndefined();
    expect(llamada.formData.get("source")).toBe("camera");
    expect(llamada.formData.get("file").name).toBe("boleta.jpg");
  });

  it("si la sesión caducó, renueva y reintenta la MISMA subida una vez", async () => {
    tokenStore.guardar(sesion());
    let intentos = 0;
    const s = servidor(({ ruta, autorizacion }) => {
      if (ruta === "/auth/refresh") return { status: 200, body: tokensRespuesta(2) };
      intentos += 1;
      return autorizacion === "Bearer acceso-1" ? { status: 401, body: { detail: "expirado" } } : { status: 200, body: { estado: "SUCCESS", mensaje: "ok" } };
    });
    const r = await api.boletas.scan(new File([new Uint8Array(5)], "b.jpg", { type: "image/jpeg" }));
    expect(r.estado).toBe("SUCCESS");
    expect(intentos).toBe(2);
    expect(s.llamadas.filter((l) => l.ruta === "/boletas/scan").every((l) => l.formData instanceof FormData)).toBe(true);
  });

  it("un escaneo tiene un tiempo máximo propio, mayor que el de las demás peticiones", async () => {
    const { TIMEOUT_ESCANEO_MS } = await import("./http");
    expect(TIMEOUT_ESCANEO_MS).toBeGreaterThan(180_000); // más que OCR_SERVICE_TIMEOUT_SECONDS del backend
    tokenStore.guardar(sesion());
    vi.useFakeTimers();
    let senal;
    vi.stubGlobal("fetch", vi.fn((url, init) => new Promise((_, rechazar) => { senal = init.signal; init.signal.addEventListener("abort", () => rechazar(new DOMException("abortado", "AbortError"))); })));
    const pendiente = api.boletas.scan(new File([new Uint8Array(5)], "b.jpg", { type: "image/jpeg" })).catch((e) => e);
    await vi.advanceTimersByTimeAsync(31_000);
    expect(senal.aborted).toBe(false); // a los 31 s (el corte normal) sigue esperando
    await vi.advanceTimersByTimeAsync(TIMEOUT_ESCANEO_MS);
    const err = await pendiente;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
    vi.useRealTimers();
  });
});
