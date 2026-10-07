// Renderiza la APLICACIÓN COMPLETA en cada ruta, como si el usuario navegara.
//
//  * Siempre corre con un servidor falso: comprueba que ninguna pantalla se
//    rompe y que ninguna llama a un endpoint que no existe.
//  * Si hay un backend real (BLYNN_CONTRACT_URL), además siembra datos
//    realistas y comprueba que NINGUNA llamada de NINGUNA pantalla recibe un
//    error del servidor (parámetros inválidos, campos rechazados...).

import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "@/App";
import { api, tokenStore } from "@/api";
import { dateStrLocal } from "@/lib/format";
import { servidor, sesion, usuarioEjemplo } from "@/test/servidorFalso";

vi.setConfig({ testTimeout: 20_000 });

const RUTAS = ["/", "/estadisticas", "/gastos", "/ingresos", "/categorias", "/boletas", "/metas", "/ajustes", "/exportar-datos"];
const URL_CONTRATO = process.env.BLYNN_CONTRACT_URL;

// Espera a que la pantalla termine de cargar: ya no hay llamadas nuevas durante un rato.
async function esperarQuietud(contador, ms = 400, tope = 10_000) {
  const inicio = Date.now();
  let ultimo = -1;
  let desde = Date.now();
  while (Date.now() - inicio < tope) {
    const n = contador();
    if (n !== ultimo) { ultimo = n; desde = Date.now(); }
    if (n > 0 && Date.now() - desde >= ms) return;
    await new Promise((r) => setTimeout(r, 50));
  }
}

function montarApp(ruta) {
  window.history.pushState({}, "", ruta);
  const errores = [];
  vi.spyOn(console, "error").mockImplementation((...args) => errores.push(args.map(String).join(" ")));
  const vista = render(<App />);
  return { vista, errores };
}

const ERRORES_GRAVES = /Cannot read|is not a function|is not defined|Maximum update depth|Minified React error|The above error occurred|Uncaught/i;

describe("todas las pantallas cargan (servidor falso)", () => {
  it.each(RUTAS)("%s se muestra sin errores y solo usa endpoints que existen", async (ruta) => {
    tokenStore.guardar(sesion());
    const desconocidas = [];
    const s = servidor(({ metodo, ruta: r }) => {
      if (r === "/me") return { status: 200, body: usuarioEjemplo() };
      if (metodo === "GET" && /^\/(expenses|incomes|categories|goals|contributions)(\?|$)/.test(r)) return { status: 200, body: [] };
      if (metodo === "POST" && r === "/categories/defaults") return { status: 200, body: [] };
      desconocidas.push(`${metodo} ${r}`);
      return { status: 404, body: { detail: "No encontrado." } };
    });
    const { errores } = montarApp(ruta);
    await esperarQuietud(() => s.llamadas.length);
    expect(document.body.textContent.length).toBeGreaterThan(20); // se pintó algo
    expect(screen.queryByText("Bienvenido de nuevo")).toBeNull(); // no la mandó al login
    expect(desconocidas).toEqual([]);
    expect(errores.filter((e) => ERRORES_GRAVES.test(e))).toEqual([]);
  });

  it("una ruta inexistente muestra la página 404 en español", async () => {
    tokenStore.guardar(sesion());
    servidor(({ ruta: r }) => (r === "/me" ? { status: 200, body: usuarioEjemplo() } : { status: 200, body: [] }));
    montarApp("/no-existe");
    expect(await screen.findByText("Página no encontrada")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir al inicio" })).toHaveAttribute("href", "/");
  });

  it("al entrar a la app por primera vez (sin encuesta) se muestra la bienvenida", async () => {
    tokenStore.guardar(sesion());
    const s = servidor(({ ruta: r }) => (r === "/me" ? { status: 200, body: usuarioEjemplo({ onboarded: false }) } : { status: 200, body: [] }));
    montarApp("/");
    await esperarQuietud(() => s.llamadas.length);
    await waitFor(() => expect(document.body.textContent).toMatch(/Bienvenid|presupuesto/i));
  });

  it("si no hay categorías las pide al servidor (idempotente) en vez de crearlas una a una", async () => {
    tokenStore.guardar(sesion());
    const s = servidor(({ metodo, ruta: r }) => {
      if (r === "/me") return { status: 200, body: usuarioEjemplo() };
      if (r === "/categories/defaults" && metodo === "POST") return { status: 200, body: [] };
      return { status: 200, body: [] };
    });
    montarApp("/");
    await esperarQuietud(() => s.llamadas.length);
    expect(s.llamadas.filter((l) => l.ruta === "/categories/defaults" && l.metodo === "POST").length).toBe(1);
    expect(s.llamadas.filter((l) => l.metodo === "POST" && l.ruta === "/categories")).toHaveLength(0);
  });
});

describe.skipIf(!URL_CONTRATO)("todas las pantallas con datos reales (backend real)", () => {
  const HOY = dateStrLocal(new Date());
  const mes = (n) => { const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - n); return dateStrLocal(d); };

  async function sembrar() {
    const email = `pantallas.${Date.now()}@correo.cl`;
    await api.auth.register({ email, password: "Tr3s-Tristes-Tigres", fullName: "Ana Pérez" });
    await api.me.update({ onboarded: true, monthly_budget: 700000 });
    const cats = await api.categories.ensureDefaults();
    await api.categories.update(cats[0].id, { name: cats[0].name, color: cats[0].color, budget: 50000 });
    await api.expenses.bulkCreate([
      { merchant: "Líder Osorno", description: "Pan 1.200\nLeche 1.990", amount: 3190, category: "Alimentación", date: HOY, payment_method: "debito", color: "#3b82f6", is_recurring: false, recurring_active: false },
      { merchant: "Copec", amount: 30000, category: "Transporte", date: mes(1), payment_method: "credito", color: "#a78bfa", is_recurring: false, recurring_active: false },
      { merchant: "Netflix", amount: 8990, category: "Suscripciones", date: mes(2), payment_method: "credito", color: "#facc15", is_recurring: true, recurring_active: true },
    ]);
    await api.incomes.create({ source: "Empresa SpA", amount: 850000, date: mes(0), type: "sueldo", color: "#22c55e" });
    const meta = await api.goals.create({ title: "Notebook", target_amount: 600000, current_amount: 0, color: "#22c55e", contribution_mode: "percent_surplus", contribution_percent: 12.5, contribution_frequency: "meses", next_contribution_date: "2026-01-01" });
    await api.goals.addContribution(meta.id, { amount: 40000, date: HOY, mode: "manual" });
    await api.goals.create({ title: "Viaje", target_amount: 1500000, current_amount: 200000, color: "#3b82f6", contribution_mode: "manual", deadline: "2027-03-01" });
  }

  it.each(RUTAS)("%s carga con datos y ninguna llamada recibe error del servidor", async (ruta) => {
    await sembrar();
    const respuestasConError = [];
    const originalFetch = globalThis.fetch;
    const llamadas = { n: 0 };
    vi.stubGlobal("fetch", async (...args) => {
      llamadas.n++;
      const r = await originalFetch(...args);
      if (r.status >= 400) respuestasConError.push(`${args[1]?.method || "GET"} ${String(args[0]).replace(/^https?:\/\/[^/]+/, "")} -> ${r.status}`);
      return r;
    });
    const { errores } = montarApp(ruta);
    await esperarQuietud(() => llamadas.n, 600);
    expect(document.body.textContent).toMatch(/Ana|Alimentaci|Gastos|Resumen|Notebook|Ajustes|Ingresos|Estad|Metas|Categor|Boletas|Exportar|escáner/i);
    expect(respuestasConError).toEqual([]);
    expect(errores.filter((e) => ERRORES_GRAVES.test(e))).toEqual([]);
    expect(screen.queryByText("Bienvenido de nuevo")).toBeNull();
  });

  it("la lista de gastos muestra los datos reales del usuario", async () => {
    await sembrar();
    montarApp("/gastos");
    expect(await screen.findByText("Líder Osorno", {}, { timeout: 8000 })).toBeInTheDocument();
    expect(await screen.findByText("Copec")).toBeInTheDocument();
  });

  it("Ajustes: 'Cancelar' no borra nada y 'Sí, eliminar todo' reinicia la cuenta en el servidor real", async () => {
    await sembrar();
    montarApp("/ajustes");
    const abrir = () => screen.findByRole("button", { name: /Eliminar todos los datos/ }, { timeout: 8000 });

    await userEvent.click(await abrir());
    await userEvent.click(await screen.findByRole("button", { name: "Cancelar" }));
    // Cancelar no toca nada. Son 4 y no 3 porque, al abrir la app, Layout generó solo el
    // cobro de este mes de la suscripción recurrente (Netflix) a través del servidor.
    const gastos = await api.expenses.list();
    expect(gastos).toHaveLength(4);
    expect(gastos.filter((g) => g.merchant === "Netflix")).toHaveLength(2);

    await userEvent.click(await abrir());
    await userEvent.click(await screen.findByRole("button", { name: "Sí, eliminar todo" }));
    await waitFor(async () => expect(await api.expenses.list()).toEqual([]), { timeout: 8000 });
    expect(await api.incomes.list()).toEqual([]);
    expect(await api.goals.list()).toEqual([]);
    expect(await api.categories.list()).toHaveLength(12); // vuelven las por defecto
    expect(await api.me.get()).toMatchObject({ onboarded: false, monthly_budget: 0, full_name: "Ana Pérez" });
  });
});
