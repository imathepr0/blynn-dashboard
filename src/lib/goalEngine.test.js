import { describe, expect, it } from "vitest";
import { addManualContribution, approveContribution, autoContribute, nextContributionDate, skipContribution, undoContribution } from "./goalEngine";
import { dateStrLocal } from "./format";
import { tokenStore } from "@/api";
import { servidor, sesion } from "@/test/servidorFalso";

const META = { id: "g1", title: "Notebook", contribution_mode: "fixed", contribution_frequency: "semanas", current_amount: 0, target_amount: 600000 };
const HOY = () => dateStrLocal(new Date());

function conSesion(manejador) {
  tokenStore.guardar(sesion());
  return servidor(manejador);
}

describe("nextContributionDate", () => {
  const base = new Date(2026, 8, 15); // 15 sep 2026
  it("suma un día, una semana o un mes según la frecuencia", () => {
    expect(nextContributionDate({ contribution_frequency: "dias" }, base)).toBe("2026-09-16");
    expect(nextContributionDate({ contribution_frequency: "semanas" }, base)).toBe("2026-09-22");
    expect(nextContributionDate({ contribution_frequency: "meses" }, base)).toBe("2026-10-15");
    expect(nextContributionDate({}, base)).toBe("2026-10-15"); // por defecto, mensual
  });
});

describe("aportes: una llamada atómica por operación", () => {
  it("aporte automático: envía modo, fecha de hoy y próxima fecha; devuelve el aporte", async () => {
    const s = conSesion(() => ({ status: 201, body: { contribution: { id: "a1" }, goal: { id: "g1" } } }));
    await expect(autoContribute(META, 40000)).resolves.toEqual({ id: "a1" });
    expect(s.llamadas).toHaveLength(1); // antes eran dos llamadas (crear aporte + actualizar meta)
    expect(s.llamadas[0]).toMatchObject({ metodo: "POST", ruta: "/goals/g1/contributions" });
    expect(s.llamadas[0].cuerpo).toEqual({ amount: 40000, date: HOY(), mode: "auto", next_contribution_date: nextContributionDate(META) });
  });

  it("aprobar un aporte: modo 'aprobado' y devuelve la meta actualizada", async () => {
    const s = conSesion(() => ({ status: 201, body: { contribution: { id: "a1" }, goal: { id: "g1", current_amount: 5000 } } }));
    await expect(approveContribution(META, 5000)).resolves.toEqual({ id: "g1", current_amount: 5000 });
    expect(s.llamadas[0].cuerpo.mode).toBe("aprobado");
  });

  it.each([[0], [-5], [NaN], [undefined]])("aprobar un monto de %s equivale a omitir (el servidor exige montos > 0)", async (monto) => {
    const s = conSesion(() => ({ status: 200, body: { id: "g1" } }));
    await approveContribution(META, monto);
    expect(s.llamadas).toHaveLength(1);
    expect(s.llamadas[0]).toMatchObject({ metodo: "PATCH", ruta: "/goals/g1" });
    expect(s.llamadas[0].cuerpo).toEqual({ next_contribution_date: nextContributionDate(META) });
  });

  it("omitir solo reprograma la próxima fecha", async () => {
    const s = conSesion(() => ({ status: 200, body: { id: "g1" } }));
    await skipContribution(META);
    expect(s.llamadas[0].cuerpo).toEqual({ next_contribution_date: nextContributionDate(META) });
  });

  it("aporte manual: no toca la próxima fecha", async () => {
    const s = conSesion(() => ({ status: 201, body: { contribution: {}, goal: { id: "g1", current_amount: 3000 } } }));
    await expect(addManualContribution(META, 3000)).resolves.toMatchObject({ current_amount: 3000 });
    expect(s.llamadas[0].cuerpo).toEqual({ amount: 3000, date: HOY(), mode: "manual" });
  });

  it("deshacer: una sola llamada que devuelve la meta con el monto descontado", async () => {
    const s = conSesion(() => ({ status: 200, body: { id: "g1", current_amount: 0 } }));
    await expect(undoContribution("g1", { id: "a1" })).resolves.toMatchObject({ current_amount: 0 });
    expect(s.llamadas).toHaveLength(1);
    expect(s.llamadas[0]).toMatchObject({ metodo: "DELETE", ruta: "/contributions/a1" });
  });

  it("si el servidor rechaza el aporte, el error llega a quien llamó (no se pierde en silencio)", async () => {
    conSesion(() => ({ status: 404, body: { detail: "No encontrado." } }));
    await expect(autoContribute(META, 100)).rejects.toMatchObject({ status: 404 });
  });
});
