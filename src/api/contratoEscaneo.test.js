// @vitest-environment node
//
// PRUEBA DE CONTRATO DEL ESCANEO: el código REAL del frontend (api.boletas.scan y
// processBoletaFile) contra un backend REAL que a su vez habla con el servicio de escaneo.
// Solo corre si se indica un servidor (igual que contrato.test.js):
//
//   BLYNN_CONTRACT_URL=http://127.0.0.1:8000/api/v1 VITE_API_URL=http://127.0.0.1:8000/api/v1 \
//   BLYNN_CONTRACT_OCR=1 BLYNN_SCAN_IMAGE=/ruta/boleta.jpg npx vitest run src/api/contratoEscaneo.test.js
//
//   BLYNN_CONTRACT_OCR=1     el backend tiene configurado un servicio de escaneo.
//   BLYNN_SCAN_IMAGE=...     una foto de boleta real para leer de punta a punta.
//
// Corre en entorno "node" y no en jsdom: el FormData de jsdom no es compatible con el fetch
// de Node. En un navegador real fetch y FormData son del mismo motor y eso no ocurre.

import { beforeAll, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";

const URL_CONTRATO = process.env.BLYNN_CONTRACT_URL;
const CON_ESCANER = process.env.BLYNN_CONTRACT_OCR === "1";
const IMAGEN_REAL = process.env.BLYNN_SCAN_IMAGE;
const sobre = URL_CONTRATO ? describe : describe.skip;
vi.setConfig({ testTimeout: 30_000 });

// Navegador mínimo para el almacén de sesión (el entorno node no trae window ni localStorage).
const memoria = new Map();
globalThis.window = globalThis;
globalThis.localStorage = {
  getItem: (k) => (memoria.has(k) ? memoria.get(k) : null),
  setItem: (k, v) => void memoria.set(k, String(v)),
  removeItem: (k) => void memoria.delete(k),
  clear: () => memoria.clear(),
};
globalThis.addEventListener ??= () => {};
globalThis.removeEventListener ??= () => {};

let api, ApiError, tokenStore, processBoletaFile, describirErrorDeEscaneo;
let contador = 0;

async function nuevoUsuario(nombre) {
  await api.auth.register({ email: `${nombre}.${Date.now()}.${contador++}@correo.cl`, password: "Tr3s-Tristes-Tigres" });
}
const pdfDisfrazado = () => new File(["%PDF-1.4 esto no es una imagen"], "foto.jpg", { type: "image/jpeg" });

sobre("contrato real: escaneo de boletas", () => {
  beforeAll(async () => {
    ({ api, ApiError, tokenStore } = await import("./index"));
    ({ processBoletaFile, describirErrorDeEscaneo } = await import("@/lib/boletasScan"));
  });

  it("sin sesión responde 401", async () => {
    tokenStore.borrar();
    const err = await api.boletas.scan(pdfDisfrazado()).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);
  });

  it.runIf(!CON_ESCANER)("sin servicio de escaneo configurado responde 503 con un mensaje claro", async () => {
    await nuevoUsuario("escaneo-sin-servicio");
    const err = await api.boletas.scan(pdfDisfrazado()).catch((e) => e);
    expect(err.status).toBe(503);
    expect(describirErrorDeEscaneo(err)).toMatch(/no está disponible/);
  });

  it.runIf(CON_ESCANER)("un archivo que no es imagen se rechaza con 415 y un mensaje en español", async () => {
    await nuevoUsuario("escaneo-415");
    const err = await api.boletas.scan(pdfDisfrazado()).catch((e) => e);
    expect(err.status).toBe(415);
    expect(describirErrorDeEscaneo(err)).toMatch(/JPG, PNG o WEBP/);
  });

  it.runIf(CON_ESCANER && IMAGEN_REAL)(
    "lee una boleta real de punta a punta (frontend → backend → escáner) y se puede guardar como gasto",
    async () => {
      await nuevoUsuario("escaneo-real");
      const foto = new File([readFileSync(IMAGEN_REAL)], "boleta.jpg", { type: "image/jpeg" });
      const lectura = await processBoletaFile(foto, ["Alimentación", "Transporte"], { source: "camera" });
      console.log("LECTURA REAL:", JSON.stringify(lectura));
      expect(lectura.estado).toBe("SUCCESS");
      expect(lectura.confident).toBe(true);
      expect(lectura.prefill.merchant).toMatch(/SUPERMERCADO/i);
      expect(lectura.prefill.amount).toBeGreaterThan(0);
      expect(lectura.prefill.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);

      // Con la confirmación de la persona, la lectura se convierte en un gasto válido en el backend.
      const gasto = await api.expenses.create({
        merchant: lectura.prefill.merchant,
        amount: lectura.prefill.amount,
        category: "Alimentación",
        date: lectura.prefill.date,
        description: lectura.prefill.description ?? "",
        color: "#2563EB",
        is_recurring: false,
        recurring_active: false,
        ...(lectura.prefill.payment_method ? { payment_method: lectura.prefill.payment_method } : {}),
      });
      expect(gasto.amount).toBe(lectura.prefill.amount);
    },
    120_000,
  );
});
