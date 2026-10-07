// PRUEBA DE CONTRATO: ejecuta el código REAL del frontend (capa de API y
// goalEngine, con los mismos payloads que arman los formularios) contra un
// backend REAL. Solo corre si se indica un servidor:
//
//   BLYNN_CONTRACT_URL=http://127.0.0.1:8000/api/v1 VITE_API_URL=http://127.0.0.1:8000/api/v1 \
//     npx vitest run src/api/contrato.test.js
//
// Úsala con un backend de DESARROLLO (crea cuentas de prueba y datos) y arráncalo con
// AUTH_MAX_REGISTROS_POR_IP=1000: la prueba registra muchas cuentas desde la misma IP y
// el límite normal (10 cada 15 min) la bloquearía. Si cambia
// el backend o una pantalla, esta prueba avisa antes de que lo note un usuario.

import { describe, expect, it, vi } from "vitest";
import { api, ApiError, describirError, tokenStore } from "./index";
import { API_URL } from "./config";
import { approveContribution, autoContribute, addManualContribution, undoContribution, skipContribution, nextContributionDate } from "@/lib/goalEngine";
import { dateStrLocal, parseAmount } from "@/lib/format";
import { randomColor } from "@/components/CategoryIcon";

const URL_CONTRATO = process.env.BLYNN_CONTRACT_URL;
const sobre = URL_CONTRATO ? describe : describe.skip;
vi.setConfig({ testTimeout: 30_000 });

const HOY = dateStrLocal(new Date());
const CLAVE = "Tr3s-Tristes-Tigres";
let contador = 0;

async function nuevoUsuario(nombre = "contrato") {
  const email = `${nombre}.${Date.now()}.${contador++}@correo.cl`;
  const user = await api.auth.register({ email, password: CLAVE });
  return { email, user };
}

// Payloads tal como los arman los formularios (ver NewExpenseDialog, IncomeDialog, GoalFormDialog).
const payloadGasto = (extra = {}) => {
  const form = { merchant: "Líder Osorno", description: "", amount: "3.190", category: "Alimentación", date: HOY, payment_method: "", color: randomColor(), is_recurring: false, recurring_active: false, ...extra };
  const payload = { ...form, amount: parseAmount(form.amount) };
  if (!payload.payment_method) delete payload.payment_method;
  return payload;
};
const payloadIngreso = () => ({ ...{ source: "Empresa SpA", amount: "850.000", date: HOY, type: "sueldo", description: "", color: "#22c55e" }, amount: parseAmount("850.000") });
const payloadMeta = (modo) => ({
  title: `Meta ${modo}`,
  target_amount: parseAmount("600.000"),
  current_amount: parseAmount(""),
  deadline: undefined,
  color: "#22c55e",
  contribution_mode: modo,
  contribution_percent: modo === "percent_surplus" ? 12.5 : undefined,
  contribution_amount: modo === "fixed" ? parseAmount("20.000") : undefined,
  contribution_frequency: modo === "manual" ? undefined : modo === "fixed" ? "semanas" : "meses",
  next_contribution_date: modo !== "manual" ? "2026-10-29" : undefined,
});

sobre("contrato frontend ↔ backend real", () => {
  it("usa el servidor indicado", () => {
    expect(API_URL).toBe(URL_CONTRATO);
  });

  it("registro, sesión y perfil (flujo de Onboarding y Ajustes)", async () => {
    const { email, user } = await nuevoUsuario();
    expect(user.email).toBe(email);
    expect(tokenStore.leer().access).toBeTruthy();
    expect((await api.me.get()).id).toBe(user.id);

    const onboarded = await api.me.update({ onboarded: true, monthly_budget: parseAmount("700.000") });
    expect(onboarded).toMatchObject({ onboarded: true, monthly_budget: 700000 });
    const perfil = await api.me.update({ full_name: "Ana", preferences: { notifications: false } });
    expect(perfil).toMatchObject({ full_name: "Ana", preferences: { notifications: false } });
    // La foto de perfil ya no existe: ni se devuelve ni se acepta
    expect(perfil).not.toHaveProperty("photo_url");
    expect((await api.me.update({ photo_url: "" }).catch((e) => e)).status).toBe(422);
  });

  it("categorías: por defecto idempotentes, crear, duplicado y renombrado", async () => {
    await nuevoUsuario();
    expect(await api.categories.ensureDefaults()).toHaveLength(12);
    expect(await api.categories.ensureDefaults()).toHaveLength(12);
    expect(await api.categories.list()).toHaveLength(12);

    const nueva = await api.categories.create({ name: "Mascotas", color: "#3b82f6", budget: parseAmount("50.000") });
    expect(nueva.budget).toBe(50000);
    const dup = await api.categories.create({ name: "mascotas", color: "#3b82f6", budget: 0 }).catch((e) => e);
    expect(dup).toBeInstanceOf(ApiError);
    expect(dup.status).toBe(409);
    expect(describirError(dup)).toMatch(/Ya existe/);

    // Renombrar actualiza los gastos de esa categoría
    await api.expenses.create(payloadGasto({ category: "Mascotas" }));
    await api.categories.update(nueva.id, { name: "Animales", color: "#3b82f6", budget: 50000 });
    const gastos = await api.expenses.list({ sort: "-date", limit: 300 });
    expect(gastos.map((g) => g.category)).toEqual(["Animales"]);
    await api.categories.remove(nueva.id);
  });

  it("gastos: formulario, edición, listados de las pantallas, recurrentes en lote y borrado", async () => {
    await nuevoUsuario();
    const g = await api.expenses.create(payloadGasto());
    expect(g).toMatchObject({ merchant: "Líder Osorno", amount: 3190, payment_method: "debito", description: null });
    const editado = await api.expenses.update(g.id, { ...payloadGasto({ amount: "9.990", description: "Pan\nLeche" }) });
    expect(editado).toMatchObject({ amount: 9990, description: "Pan\nLeche" });

    // Suscripción recurrente + clon mensual (Layout.jsx)
    const sus = await api.expenses.create(payloadGasto({ merchant: "Netflix", category: "Suscripciones", date: "2026-08-05", is_recurring: true, recurring_active: true, payment_method: "credito" }));
    const clones = [sus].map((r) => ({
      merchant: r.merchant, description: r.description, amount: r.amount, category: r.category,
      date: HOY, payment_method: r.payment_method, color: r.color, is_recurring: false, recurring_active: false,
    }));
    expect(await api.expenses.bulkCreate(clones)).toHaveLength(1);

    // Listados con los parámetros exactos que usan las pantallas
    for (const params of [{ sort: "-date", limit: 300 }, { sort: "-date", limit: 500 }, { sort: "-created_date", limit: 10 }, { sort: "-date", limit: 100 }]) {
      expect((await api.expenses.list(params)).length).toBe(3);
    }
    await api.expenses.remove(g.id);
    expect(await api.expenses.list({ sort: "-date", limit: 300 })).toHaveLength(2);
  });

  it("ingresos: crear, editar y listar", async () => {
    await nuevoUsuario();
    const i = await api.incomes.create(payloadIngreso());
    expect(i).toMatchObject({ amount: 850000, type: "sueldo", description: null });
    expect((await api.incomes.update(i.id, { ...payloadIngreso(), amount: 900000, type: "bono" })).type).toBe("bono");
    expect(await api.incomes.list({ sort: "-date", limit: 100 })).toHaveLength(1);
  });

  it("metas y aportes con las funciones reales de goalEngine", async () => {
    await nuevoUsuario();
    const manual = await api.goals.create(payloadMeta("manual"));
    const porcentaje = await api.goals.create(payloadMeta("percent_surplus"));
    const fija = await api.goals.create(payloadMeta("fixed"));
    expect(porcentaje.contribution_percent).toBe(12.5);
    expect(fija).toMatchObject({ contribution_amount: 20000, contribution_frequency: "semanas" });
    expect(await api.goals.list({ sort: "-created_date" })).toHaveLength(3);
    expect((await api.goals.list({ sort: "-created_date", limit: 1 }))).toHaveLength(1);

    // aporte automático + deshacer (Layout)
    const auto = await autoContribute(porcentaje, 40000);
    expect(auto).toMatchObject({ amount: 40000, mode: "auto", goal_title: "Meta percent_surplus" });
    let meta = await api.goals.get(porcentaje.id);
    expect(meta.current_amount).toBe(40000);
    expect(meta.next_contribution_date).toBe(nextContributionDate(porcentaje)); // hoy + frecuencia
    const deshecha = await undoContribution(porcentaje.id, auto);
    expect(deshecha.current_amount).toBe(0);

    // aprobar con monto, aprobar con $0 (equivale a omitir) y omitir
    const aprobada = await approveContribution(fija, 20000);
    expect(aprobada).toMatchObject({ current_amount: 20000, auto_approved_count: 1 });
    const fresca = await api.goals.get(fija.id); // la app siempre trabaja con la meta recién cargada
    const cero = await approveContribution(fresca, 0);
    expect(cero.current_amount).toBe(20000); // no sumó nada
    expect(cero.next_contribution_date).toBe(nextContributionDate(fresca)); // pero sí reprogramó la fecha
    await skipContribution(fija);
    expect(await api.contributions.list({ sort: "-date", limit: 10 })).toHaveLength(1);

    // aporte manual (AddContributionDialog)
    const conManual = await addManualContribution(manual, parseAmount("5.000"));
    expect(conManual.current_amount).toBe(5000);

    // editar una meta con el payload del formulario
    const editada = await api.goals.update(manual.id, { ...payloadMeta("manual"), title: "Cambiada", current_amount: 8000 });
    expect(editada).toMatchObject({ title: "Cambiada", current_amount: 8000 });

    // borrar una meta borra sus aportes (Metas.jsx)
    await api.goals.remove(fija.id);
    expect((await api.contributions.list({ sort: "-date", limit: 10 })).map((c) => c.goal_id)).toEqual([manual.id]);
  });

  it("reiniciar la cuenta (Ajustes) deja todo como nuevo", async () => {
    await nuevoUsuario();
    await api.categories.ensureDefaults();
    await api.expenses.create(payloadGasto());
    await api.incomes.create(payloadIngreso());
    await api.goals.create(payloadMeta("manual"));
    await api.me.update({ onboarded: true, monthly_budget: 123456 });

    const usuario = await api.me.reset();
    expect(usuario).toMatchObject({ onboarded: false, monthly_budget: 0 });
    expect(await api.expenses.list()).toEqual([]);
    expect(await api.incomes.list()).toEqual([]);
    expect(await api.goals.list()).toEqual([]);
    expect(await api.categories.list()).toHaveLength(12);
  });

  it("los errores de validación del servidor se explican en español", async () => {
    await nuevoUsuario();
    const e1 = await api.expenses.create({ ...payloadGasto(), amount: 0 }).catch((e) => e);
    expect(e1.status).toBe(422);
    expect(describirError(e1)).toBe("El monto debe ser mayor que 0.");
    const e2 = await api.expenses.create({ ...payloadGasto(), date: "1999-01-01" }).catch((e) => e);
    expect(describirError(e2)).toMatch(/^La fecha/);
    const e3 = await api.categories.create({ name: "X", color: "rojo" }).catch((e) => e);
    expect(describirError(e3)).toBe("El color tiene un formato inválido.");
    const e4 = await api.auth.register({ email: "no-es-correo", password: CLAVE }).catch((e) => e);
    expect(describirError(e4)).toBe("Ingresa un correo electrónico válido.");
    const e5 = await api.auth.register({ email: `debil.${Date.now()}@correo.cl`, password: "12345678" }).catch((e) => e);
    expect(describirError(e5)).toMatch(/demasiado común/);
  });

  it("un usuario no puede acceder a los datos de otro a través del cliente", async () => {
    await nuevoUsuario("duena");
    const gasto = await api.expenses.create(payloadGasto());
    await nuevoUsuario("intruso"); // ahora la sesión es de otra cuenta
    const err = await api.expenses.get(gasto.id).catch((e) => e);
    expect(err.status).toBe(404);
    expect(await api.expenses.list()).toEqual([]);
    expect((await api.expenses.remove(gasto.id).catch((e) => e)).status).toBe(404);
  });

  describe("sesión real", () => {
    it("un access token vencido se renueva solo, UNA vez aunque haya muchas peticiones", async () => {
      await nuevoUsuario();
      const { refresh } = tokenStore.leer();
      tokenStore.guardar({ access: "token.vencido.o.falso", refresh });
      const espia = vi.spyOn(globalThis, "fetch");
      const resultados = await Promise.all([api.me.get(), api.expenses.list(), api.incomes.list(), api.goals.list(), api.categories.list(), api.contributions.list()]);
      expect(resultados).toHaveLength(6);
      const renovaciones = espia.mock.calls.filter(([url]) => String(url).endsWith("/auth/refresh"));
      expect(renovaciones).toHaveLength(1);
      expect(tokenStore.leer().refresh).not.toBe(refresh); // rotó
    });

    it("reutilizar un refresh token viejo (robo) cierra la sesión completa", async () => {
      await nuevoUsuario();
      const viejo = tokenStore.leer().refresh;
      tokenStore.guardar({ access: "vencido", refresh: viejo });
      await api.me.get(); // renueva: ahora `viejo` ya fue usado
      const ladron = await fetch(`${API_URL}/auth/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: viejo }) });
      expect(ladron.status).toBe(401);
      // el token nuevo del usuario legítimo también quedó revocado
      tokenStore.guardar({ access: "vencido", refresh: tokenStore.leer().refresh });
      const err = await api.me.get().catch((e) => e);
      expect(err.status).toBe(401);
      expect(tokenStore.leer()).toEqual({ access: null, refresh: null });
    });

    it("cerrar sesión revoca el token en el servidor", async () => {
      await nuevoUsuario();
      const { refresh } = tokenStore.leer();
      await api.auth.logout();
      expect(tokenStore.leer()).toEqual({ access: null, refresh: null });
      const r = await fetch(`${API_URL}/auth/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refresh }) });
      expect(r.status).toBe(401);
      expect((await api.me.get().catch((e) => e)).status).toBe(401);
    });

    it("login con credenciales malas: mensaje genérico y bloqueo tras varios intentos", async () => {
      const { email } = await nuevoUsuario("bloqueo");
      await api.auth.logout();
      const primero = await api.auth.login(email, "Clave-Equivocada-1").catch((e) => e);
      expect(describirError(primero)).toBe("Correo o contraseña incorrectos.");
      const inexistente = await api.auth.login("nadie@correo.cl", "Clave-Equivocada-1").catch((e) => e);
      expect(describirError(inexistente)).toBe(describirError(primero)); // no revela qué correos existen
      for (let i = 0; i < 4; i++) await api.auth.login(email, "Clave-Equivocada-1").catch(() => {});
      const bloqueado = await api.auth.login(email, CLAVE).catch((e) => e); // incluso con la clave correcta
      expect(bloqueado.status).toBe(429);
      expect(describirError(bloqueado)).toMatch(/Demasiados intentos/);
    });

    it("el login correcto devuelve el usuario y deja la sesión lista", async () => {
      const { email, user } = await nuevoUsuario("login");
      await api.auth.logout();
      const otra = await api.auth.login(email.toUpperCase(), CLAVE);
      expect(otra.id).toBe(user.id);
      expect((await api.me.get()).email).toBe(email);
    });
  });

  it("CORS: el navegador puede hacer PATCH/DELETE con Authorization desde el frontend", async () => {
    const r = await fetch(`${API_URL}/expenses/00000000-0000-0000-0000-000000000000`, {
      method: "OPTIONS",
      headers: { Origin: "http://localhost:5173", "Access-Control-Request-Method": "PATCH", "Access-Control-Request-Headers": "authorization,content-type" },
    });
    expect(r.status).toBe(200);
    expect(r.headers.get("access-control-allow-origin")).toBe("http://localhost:5173");
    expect(r.headers.get("access-control-allow-methods")).toMatch(/PATCH/);
    expect(r.headers.get("access-control-allow-methods")).toMatch(/DELETE/);
    expect(r.headers.get("access-control-allow-headers").toLowerCase()).toMatch(/authorization/);

    const ajeno = await fetch(`${API_URL}/expenses`, { method: "OPTIONS", headers: { Origin: "https://sitio-malicioso.example", "Access-Control-Request-Method": "GET" } });
    expect(ajeno.headers.get("access-control-allow-origin")).toBeNull(); // un origen desconocido no recibe permiso
  });
});
