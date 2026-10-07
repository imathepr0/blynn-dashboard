import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api", async (original) => ({
  ...(await original()),
  api: { boletas: { scan: vi.fn() } },
}));

import { api, ApiError } from "@/api";
import {
  describirErrorDeEscaneo,
  descripcionDeProductos,
  interpretarEscaneo,
  MAX_IMAGE_BYTES,
  metodoDePago,
  prepararImagen,
  processBoletaFile,
  sugerirCategoria,
} from "./boletasScan";

// Lectura típica del escáner real (ver backend/README.md, "Integración con el escaneo").
const LECTURA = {
  estado: "SUCCESS",
  mensaje: "Boleta procesada correctamente.",
  confianza_general: 92.5,
  advertencias: [],
  datos: {
    comercio: "Jumbo",
    fecha: "2026-07-14",
    metodo_pago: "Débito",
    productos: [
      { nombre: "Pan Hallulla", cantidad: 1, precio_unitario: 1200, confianza: 93 },
      { nombre: "Leche", cantidad: 2, precio_unitario: 990, confianza: 90 },
    ],
    total: 3180,
  },
};
const CATS = ["Alimentación", "Transporte", "Salud"];

describe("interpretarEscaneo", () => {
  it("una lectura completa y confiable llena el formulario y es confiable", () => {
    const r = interpretarEscaneo(LECTURA, CATS);
    expect(r.confident).toBe(true);
    expect(r.prefill).toEqual({
      merchant: "Jumbo",
      amount: 3180,
      date: "2026-07-14",
      payment_method: "debito",
      description: "Pan Hallulla - 1200\n2 x Leche - 1980",
      category: "Alimentación",
    });
  });

  it("PARTIAL_SUCCESS y LOW_CONFIDENCE nunca son 'confiables', pero conservan lo leído", () => {
    for (const estado of ["PARTIAL_SUCCESS", "LOW_CONFIDENCE"]) {
      const r = interpretarEscaneo({ ...LECTURA, estado }, CATS);
      expect(r.confident).toBe(false);
      expect(r.prefill.amount).toBe(3180);
    }
  });

  it("SUCCESS con confianza baja, sin total o sin comercio no es confiable", () => {
    expect(interpretarEscaneo({ ...LECTURA, confianza_general: 60 }, CATS).confident).toBe(false);
    expect(interpretarEscaneo({ ...LECTURA, confianza_general: null }, CATS).confident).toBe(false);
    expect(interpretarEscaneo({ ...LECTURA, datos: { ...LECTURA.datos, total: null } }, CATS).confident).toBe(false);
    expect(interpretarEscaneo({ ...LECTURA, datos: { ...LECTURA.datos, comercio: null } }, CATS).confident).toBe(false);
  });

  it("si no se pudo leer nada, el borrador queda vacío y se conserva el mensaje del escáner", () => {
    const r = interpretarEscaneo({ estado: "IMAGE_UNREADABLE", mensaje: "Mejora la iluminación.", datos: null }, CATS);
    expect(r).toMatchObject({ confident: false, prefill: {}, estado: "IMAGE_UNREADABLE", mensaje: "Mejora la iluminación." });
  });

  it("una fecha futura se recorta a hoy", () => {
    const r = interpretarEscaneo({ ...LECTURA, datos: { ...LECTURA.datos, fecha: "2099-01-01" } }, CATS);
    expect(r.prefill.date <= new Date().toISOString().slice(0, 10)).toBe(true);
  });

  it("el total decimal se redondea a pesos enteros", () => {
    const r = interpretarEscaneo({ ...LECTURA, datos: { ...LECTURA.datos, total: 3180.6 } }, CATS);
    expect(r.prefill.amount).toBe(3181);
  });

  it("tolera una respuesta vacía o rara sin romper", () => {
    expect(interpretarEscaneo(null, CATS)).toMatchObject({ confident: false, prefill: {}, advertencias: [] });
    expect(interpretarEscaneo({ estado: "SUCCESS" }, CATS).confident).toBe(false);
  });
});

describe("metodoDePago", () => {
  it.each([
    ["Débito", "debito"], ["REDCOMPRA", "debito"], ["Tarjeta de crédito", "credito"],
    ["Efectivo", "efectivo"], ["Transferencia electrónica", "transferencia"],
  ])("%s → %s", (texto, esperado) => expect(metodoDePago(texto)).toBe(esperado));

  it("lo desconocido o vacío no inventa un método", () => {
    expect(metodoDePago("Vale canje")).toBeNull();
    expect(metodoDePago("")).toBeNull();
    expect(metodoDePago(null)).toBeNull();
  });
});

describe("sugerirCategoria", () => {
  it("reconoce comercios conocidos, con o sin tildes y mayúsculas", () => {
    expect(sugerirCategoria("LÍDER Express", CATS)).toBe("Alimentación");
    expect(sugerirCategoria("COPEC Ruta 5", CATS)).toBe("Transporte");
    expect(sugerirCategoria("Farmacias Ahumada", CATS)).toBe("Salud");
  });

  it("solo sugiere una categoría que la persona realmente tiene", () => {
    expect(sugerirCategoria("Sodimac", CATS)).toBeNull(); // 'Hogar' no está en CATS
    expect(sugerirCategoria("Jumbo", ["Transporte"])).toBeNull();
  });

  it("exige la palabra completa (no coincide a mitad de otra)", () => {
    expect(sugerirCategoria("Easyfood Ltda", ["Hogar"])).toBeNull();
    expect(sugerirCategoria("Easy Maipú", ["Hogar"])).toBe("Hogar");
  });

  it("un comercio desconocido o vacío no adivina", () => {
    expect(sugerirCategoria("Kiosko Don Pepe", CATS)).toBeNull();
    expect(sugerirCategoria("", CATS)).toBeNull();
    expect(sugerirCategoria(null, CATS)).toBeNull();
  });
});

describe("descripcionDeProductos", () => {
  it("usa el formato 'nombre - precio' y multiplica por la cantidad", () => {
    expect(descripcionDeProductos([{ nombre: "Leche", cantidad: 3, precio_unitario: 1000 }])).toBe("3 x Leche - 3000");
  });

  it("un ' - ' dentro del nombre no rompe el formato de la grilla", () => {
    expect(descripcionDeProductos([{ nombre: "Yogurt - frutilla", cantidad: 1, precio_unitario: 500 }])).toBe("Yogurt frutilla - 500");
  });

  it("omite productos sin nombre, muestra sin precio los que no lo tienen y acota el largo", () => {
    expect(descripcionDeProductos([{ nombre: "  " }, { nombre: "Bolsa" }])).toBe("Bolsa");
    expect(descripcionDeProductos(undefined)).toBe("");
    const muchos = Array.from({ length: 100 }, (_, i) => ({ nombre: `Producto número ${i}`, precio_unitario: 100 }));
    const texto = descripcionDeProductos(muchos);
    expect(texto.split("\n").length).toBe(40);
    expect(texto.length).toBeLessThanOrEqual(1500);
  });
});

describe("prepararImagen", () => {
  const archivo = (bytes, tipo = "image/jpeg", nombre = "foto.jpg") => new File([new Uint8Array(bytes)], nombre, { type: tipo });

  beforeEach(() => vi.unstubAllGlobals());

  it("una foto liviana o que no es imagen se envía tal cual", async () => {
    const chica = archivo(1000);
    expect(await prepararImagen(chica)).toBe(chica);
    const pdf = archivo(3_000_000, "application/pdf", "x.pdf");
    expect(await prepararImagen(pdf)).toBe(pdf);
  });

  it("una foto pesada se reduce a un JPEG de a lo más 2000 px", async () => {
    const grande = archivo(5_000_000);
    const cierre = vi.fn();
    vi.stubGlobal("createImageBitmap", vi.fn(async () => ({ width: 4000, height: 3000, close: cierre })));
    const dibujo = { fillRect: vi.fn(), drawImage: vi.fn(), fillStyle: "" };
    const lienzo = { width: 0, height: 0, getContext: () => dibujo, toBlob: (cb) => cb(new Blob([new Uint8Array(400_000)], { type: "image/jpeg" })) };
    const crear = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag) => (tag === "canvas" ? lienzo : crear(tag)));

    const reducida = await prepararImagen(grande);
    expect(reducida).not.toBe(grande);
    expect(reducida.type).toBe("image/jpeg");
    expect(reducida.size).toBe(400_000);
    expect([lienzo.width, lienzo.height]).toEqual([2000, 1500]);
    expect(dibujo.drawImage).toHaveBeenCalledOnce();
    expect(cierre).toHaveBeenCalled();
    vi.restoreAllMocks();
  });

  it("si el navegador no puede reducirla, usa la original sin fallar", async () => {
    const grande = archivo(5_000_000);
    vi.stubGlobal("createImageBitmap", vi.fn(async () => { throw new Error("no se pudo decodificar"); }));
    expect(await prepararImagen(grande)).toBe(grande);
    vi.unstubAllGlobals();
    expect(await prepararImagen(grande)).toBe(grande); // sin createImageBitmap
  });

  it("si el resultado no es más liviano, se queda con la original", async () => {
    const grande = archivo(2_000_000);
    vi.stubGlobal("createImageBitmap", vi.fn(async () => ({ width: 1000, height: 800, close: vi.fn() })));
    const lienzo = { getContext: () => ({ fillRect: vi.fn(), drawImage: vi.fn() }), toBlob: (cb) => cb(new Blob([new Uint8Array(3_000_000)])) };
    const crear = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag) => (tag === "canvas" ? lienzo : crear(tag)));
    expect(await prepararImagen(grande)).toBe(grande);
    vi.restoreAllMocks();
  });
});

describe("processBoletaFile", () => {
  beforeEach(() => api.boletas.scan.mockReset());

  it("envía la foto con su origen y devuelve la lectura interpretada", async () => {
    api.boletas.scan.mockResolvedValue(LECTURA);
    const foto = new File([new Uint8Array(500)], "boleta.jpg", { type: "image/jpeg" });
    const r = await processBoletaFile(foto, CATS, { source: "camera" });
    expect(api.boletas.scan).toHaveBeenCalledWith(foto, "camera");
    expect(r.confident).toBe(true);
  });

  it("por defecto el origen es 'file'", async () => {
    api.boletas.scan.mockResolvedValue(LECTURA);
    await processBoletaFile(new File([new Uint8Array(10)], "b.png", { type: "image/png" }), CATS);
    expect(api.boletas.scan.mock.calls[0][1]).toBe("file");
  });

  it("una imagen sobre 10 MB que no se pudo reducir falla antes de subir nada", async () => {
    const enorme = new File([new Uint8Array(MAX_IMAGE_BYTES + 1)], "x.jpg", { type: "image/jpeg" });
    const err = await processBoletaFile(enorme, CATS).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(413);
    expect(api.boletas.scan).not.toHaveBeenCalled();
  });

  it("los errores del servidor se propagan para mostrarse", async () => {
    api.boletas.scan.mockRejectedValue(new ApiError(503, "El escaneo de boletas no está disponible por ahora."));
    await expect(processBoletaFile(new File([new Uint8Array(10)], "b.jpg", { type: "image/jpeg" }), CATS)).rejects.toMatchObject({ status: 503 });
  });
});

describe("describirErrorDeEscaneo", () => {
  it.each([413, 415, 422, 429, 502, 503, 504])("el %s muestra el mensaje en español del backend", (status) => {
    expect(describirErrorDeEscaneo(new ApiError(status, "Mensaje claro para la persona."))).toBe("Mensaje claro para la persona.");
  });

  it("un 500 u otro error sigue usando el mensaje genérico (no filtra detalles)", () => {
    const m = describirErrorDeEscaneo(new ApiError(500, "Traceback interno"));
    expect(m).not.toMatch(/Traceback/);
  });

  it("sin conexión y tiempo agotado usan el mensaje general de la app", () => {
    expect(describirErrorDeEscaneo(new ApiError(0, "x"))).toBeTruthy();
    expect(describirErrorDeEscaneo(new Error("cualquier cosa"))).toBeTruthy();
  });
});
