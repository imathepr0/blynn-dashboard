import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import ProcessingScreen from "./ProcessingScreen";

describe("ProcessingScreen", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const avanzar = (ms) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
  const porcentaje = () => Number(screen.getByText(/^\d+%$/).textContent.replace("%", ""));

  it("no dice que usa IA (el escáner no usa inteligencia artificial)", () => {
    render(<ProcessingScreen done={false} />);
    expect(screen.getByText(/Leyendo tu boleta/)).toBeInTheDocument();
    expect(screen.queryByText(/\bIA\b/)).toBeNull();
  });

  it("la barra sigue avanzando en una espera larga (no se queda quieta) y nunca llega al 100% sola", async () => {
    render(<ProcessingScreen done={false} />);
    await avanzar(20_000);
    const a = porcentaje();
    await avanzar(40_000);
    const b = porcentaje();
    expect(b).toBeGreaterThan(a);
    expect(b).toBeLessThan(95);
    await avanzar(600_000);
    expect(porcentaje()).toBeLessThanOrEqual(95);
  });

  it("pasados 15 s explica que puede estar despertando; antes de eso no", async () => {
    render(<ProcessingScreen done={false} />);
    await avanzar(14_000);
    expect(screen.queryByRole("status")).toBeNull();
    await avanzar(2_000);
    expect(screen.getByRole("status")).toHaveTextContent(/despertando/);
  });

  it("al terminar completa la barra, avisa una vez y quita el aviso de demora", async () => {
    const onComplete = vi.fn();
    const { rerender } = render(<ProcessingScreen done={false} onComplete={onComplete} />);
    await avanzar(20_000);
    expect(screen.getByRole("status")).toBeInTheDocument();
    rerender(<ProcessingScreen done onComplete={onComplete} />);
    await avanzar(1_000);
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(porcentaje()).toBe(100);
    expect(screen.queryByRole("status")).toBeNull();
  });
});
