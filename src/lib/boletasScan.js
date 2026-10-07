import { dateStrLocal } from "@/lib/format";
import { api, ApiError, describirError } from "@/api";

export const CONFIDENCE_THRESHOLD = 75;

export function normalizeDate(v, today) {
  const T = today || dateStrLocal(new Date());
  if (typeof v !== "string" || !v.trim()) return T;
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return v > T ? T : v;
  const d = new Date(v);
  if (!isNaN(d.getTime())) {
    const s = dateStrLocal(d);
    return s > T ? T : s;
  }
  return T;
}

// ESCANEO AUTOMÁTICO DE BOLETAS.
//
// La foto se envía al backend de Blynn (`api.boletas.scan`), que comprueba la sesión, la
// valida y se la pasa al servicio de escaneo (OpenCV + Tesseract, sin IA). Aquí solo se
// traduce esa lectura al borrador que entiende el formulario de gasto.
//
// `processBoletaFile` devuelve { confident, prefill, estado, mensaje, advertencias } y
// NUNCA guarda nada por su cuenta: la persona siempre revisa y confirma los datos en el
// formulario antes de guardar, incluso cuando la lectura es buena.
export const ESCANEO_DISPONIBLE = true;

export const MAX_IMAGE_BYTES = 10 * 1024 * 1024; // el mismo límite del backend
const REDUCIR_DESDE_BYTES = 1.5 * 1024 * 1024; // fotos más livianas se envían tal cual
const LADO_MAXIMO_PX = 2000; // el escáner igual reduce a 2000 px: no se pierde detalle útil
const CALIDAD_JPEG = 0.88;

/**
 * Reduce una foto pesada (las cámaras de celular entregan 3-12 MB) a un JPEG de a lo más
 * 2000 px antes de subirla: sube más rápido con datos móviles y no choca con el límite de
 * 10 MB. Si algo falla (navegador sin soporte, imagen rara), devuelve la original.
 */
export async function prepararImagen(archivo) {
  if (!archivo || archivo.size <= REDUCIR_DESDE_BYTES) return archivo;
  if (!/^image\/(jpeg|png|webp)$/.test(archivo.type)) return archivo;
  try {
    if (typeof createImageBitmap !== "function") return archivo;
    const imagen = await createImageBitmap(archivo);
    try {
      const escala = Math.min(1, LADO_MAXIMO_PX / Math.max(imagen.width, imagen.height));
      const ancho = Math.max(1, Math.round(imagen.width * escala));
      const alto = Math.max(1, Math.round(imagen.height * escala));
      const lienzo = document.createElement("canvas");
      lienzo.width = ancho;
      lienzo.height = alto;
      const ctx = lienzo.getContext("2d");
      if (!ctx) return archivo;
      ctx.fillStyle = "#ffffff"; // un PNG con transparencia no debe quedar sobre negro
      ctx.fillRect(0, 0, ancho, alto);
      ctx.drawImage(imagen, 0, 0, ancho, alto);
      const blob = await new Promise((resolve) => lienzo.toBlob(resolve, "image/jpeg", CALIDAD_JPEG));
      if (!blob || blob.size >= archivo.size) return archivo;
      return new File([blob], "boleta.jpg", { type: "image/jpeg" });
    } finally {
      imagen.close?.();
    }
  } catch {
    return archivo;
  }
}

const sinAcentos = (s) =>
  String(s ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();

/** "Débito", "Redcompra", "Tarjeta de crédito"... → el valor del selector de pago, o null. */
export function metodoDePago(texto) {
  const t = sinAcentos(texto);
  if (!t) return null;
  if (/\b(debito|redcompra|red compra)\b/.test(t)) return "debito";
  if (/\bcredito\b/.test(t)) return "credito";
  if (/\befectivo\b/.test(t)) return "efectivo";
  if (/\btransfer/.test(t)) return "transferencia";
  return null;
}

// Sugerencia de categoría por el nombre del comercio. Es una REGLA SIMPLE (el escáner no
// clasifica y no usa IA): solo acierta con comercios conocidos y deja el resto sin tocar.
// Solo se sugiere una categoría que la persona realmente tenga.
const REGLAS_CATEGORIA = [
  ["Alimentación", ["jumbo", "lider", "unimarc", "santa isabel", "tottus", "acuenta", "ekono", "supermercado", "panaderia", "restaurant", "restaurante", "cafeteria", "pizzeria", "mcdonalds", "burger king", "starbucks", "juan maestro"]],
  ["Transporte", ["copec", "shell", "petrobras", "enex", "uber", "cabify", "didi", "estacionamiento", "autopista", "turbus", "pullman"]],
  ["Salud", ["farmacia", "ahumada", "cruz verde", "salcobrand", "clinica", "laboratorio", "dental", "optica"]],
  ["Hogar", ["sodimac", "easy", "construmart", "homecenter", "ferreteria"]],
  ["Suscripciones", ["netflix", "spotify", "disney", "hbo", "amazon prime", "youtube premium"]],
  ["Tecnología", ["pc factory", "pcfactory"]],
  ["Entretenimiento", ["cine", "cinemark", "cinehoyts", "hoyts", "ticketmaster", "puntoticket"]],
];

const escaparRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function sugerirCategoria(comercio, cats = []) {
  const nombre = sinAcentos(comercio);
  if (!nombre) return null;
  for (const [categoria, palabras] of REGLAS_CATEGORIA) {
    if (!cats.includes(categoria)) continue;
    const coincide = palabras.some((p) => new RegExp(`(^|[^a-z0-9])${escaparRegex(p)}([^a-z0-9]|$)`).test(nombre));
    if (coincide) return categoria;
  }
  return null;
}

/** Productos → texto de varias líneas "nombre - precio", el formato que usa la grilla de descripción. */
export function descripcionDeProductos(productos) {
  if (!Array.isArray(productos)) return "";
  const lineas = [];
  for (const p of productos.slice(0, 40)) {
    const nombre = String(p?.nombre ?? "").replace(/\s+-\s+/g, " ").replace(/\s+/g, " ").trim();
    if (!nombre) continue;
    const cantidad = Number.isFinite(p.cantidad) && p.cantidad > 0 ? p.cantidad : 1;
    const precio = Number.isFinite(p.precio_unitario) && p.precio_unitario > 0 ? Math.round(p.precio_unitario * cantidad) : 0;
    const etiqueta = cantidad > 1 ? `${cantidad} x ${nombre}` : nombre;
    lineas.push(precio ? `${etiqueta} - ${precio}` : etiqueta);
  }
  return lineas.join("\n").slice(0, 1500);
}

/**
 * La lectura del escáner → { confident, prefill, estado, mensaje, advertencias }.
 * `prefill` usa los nombres del formulario de gasto (merchant, amount, date, ...) y solo
 * trae lo que realmente se leyó. `confident` es verdadero únicamente con una lectura
 * COMPLETA (SUCCESS), de confianza suficiente y con comercio y monto.
 */
export function interpretarEscaneo(lectura, cats = []) {
  const datos = lectura?.datos ?? {};
  const prefill = {};
  if (datos.comercio) prefill.merchant = datos.comercio;
  if (Number.isFinite(datos.total) && datos.total > 0) prefill.amount = Math.round(datos.total);
  if (datos.fecha) prefill.date = normalizeDate(datos.fecha);
  const pago = metodoDePago(datos.metodo_pago);
  if (pago) prefill.payment_method = pago;
  const descripcion = descripcionDeProductos(datos.productos);
  if (descripcion) prefill.description = descripcion;
  const categoria = sugerirCategoria(datos.comercio, cats);
  if (categoria) prefill.category = categoria;

  const confident =
    lectura?.estado === "SUCCESS" &&
    (lectura?.confianza_general ?? 0) >= CONFIDENCE_THRESHOLD &&
    Boolean(prefill.merchant) &&
    Boolean(prefill.amount);

  return {
    confident,
    prefill,
    estado: lectura?.estado ?? null,
    mensaje: typeof lectura?.mensaje === "string" ? lectura.mensaje : "",
    advertencias: Array.isArray(lectura?.advertencias) ? lectura.advertencias : [],
  };
}

/**
 * Lee una boleta: la reduce si pesa mucho, la envía al backend e interpreta la lectura.
 * @param {File} file
 * @param {string[]} cats  nombres de las categorías de la persona
 * @param {{source?: "camera"|"file"}} opciones
 */
export async function processBoletaFile(file, cats = [], { source = "file" } = {}) {
  const archivo = await prepararImagen(file);
  if (archivo.size > MAX_IMAGE_BYTES) {
    throw new ApiError(413, "La imagen es demasiado grande (máximo 10 MB). Toma la foto con una resolución menor.");
  }
  const lectura = await api.boletas.scan(archivo, source);
  return interpretarEscaneo(lectura, cats);
}

// Errores del escaneo con mensaje propio y útil (la app, en general, oculta el detalle de
// los errores 5xx). El backend ya los redacta en español y sin datos internos.
const ESTADOS_CON_MENSAJE = [413, 415, 422, 429, 502, 503, 504];

export function describirErrorDeEscaneo(error) {
  if (error instanceof ApiError && ESTADOS_CON_MENSAJE.includes(error.status) && typeof error.detail === "string" && error.detail) {
    return error.detail;
  }
  return describirError(error);
}
