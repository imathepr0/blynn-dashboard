import { describe, expect, it } from "vitest";
import { resolverReturnTo } from "./authReturnTo";

const ORIGEN = "https://app.blynn.cl";

describe("resolverReturnTo (protección contra redirecciones abiertas)", () => {
  it.each([
    ["/gastos", "/gastos"],
    ["/gastos?mes=9", "/gastos?mes=9"],
    ["/metas", "/metas"],
    [null, "/"],
    ["", "/"],
  ])("acepta rutas propias: %s", (entrada, esperado) => {
    expect(resolverReturnTo(entrada, ORIGEN)).toBe(esperado);
  });

  it.each([
    "https://evil.com/robo",
    "//evil.com",
    "/.//evil.com",
    "/\\evil.com",
    "\\\\evil.com",
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "https://app.blynn.cl.evil.com/",
    "http://app.blynn.cl/gastos", // otro esquema = otro origen
    "///evil.com",
    "/%5Cevil.com/../..//evil.com",
  ])("rechaza destinos peligrosos: %s", (entrada) => {
    const r = resolverReturnTo(entrada, ORIGEN);
    expect(r === "/" || (r.startsWith("/") && !r.startsWith("//") && !r.includes("\\"))).toBe(true);
    expect(r).not.toMatch(/evil/);
  });
});
