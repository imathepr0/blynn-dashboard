export function formatCLP(value) {
  const n = Math.round(parseAmount(value));
  return "$" + n.toLocaleString("es-CL");
}

export function sanitizeAmount(v) {
  const digits = String(v ?? "").replace(/\D/g, "");
  return digits ? digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".") : "";
}

export function parseAmount(v) {
  return Number(String(v ?? "").replace(/\D/g, "")) || 0;
}

// Fechas locales: parsear "YYYY-MM-DD" con new Date() lo interpreta como UTC
// y en Chile corre el día/mes hacia atrás (ej: 21-09 → 20-09, 01-09 → agosto).
export function dateParts(dateStr) {
  const [y, m, d] = String(dateStr || "").split("-").map(Number);
  return { y: y || 0, m: (m || 1) - 1, d: d || 1 };
}

export function dateStrLocal(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function monthKeyOf(date) {
  if (date instanceof Date) return `${date.getFullYear()}-${String(date.getMonth()).padStart(2, "0")}`;
  const p = dateParts(date);
  return `${p.y}-${String(p.m).padStart(2, "0")}`;
}

export function isSameMonth(dateStr, ref = new Date()) {
  const p = dateParts(dateStr);
  return p.y === ref.getFullYear() && p.m === ref.getMonth();
}

export function formatDateShort(dateStr) {
  if (!dateStr) return "";
  const months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  const p = dateParts(dateStr);
  return `${p.d} ${months[p.m]}`;
}

export const CATEGORY_COLORS = {
  "Alimentación": "#3b82f6",
  "Transporte": "#a78bfa",
  "Hogar": "#fb923c",
  "Suscripciones": "#facc15",
  "Salud": "#22c55e",
  "Ropa": "#ec4899",
  "Arriendo": "#14b8a6",
  "Educación": "#8b5cf6",
  "Entretenimiento": "#f97316",
  "Transferencias": "#06b6d4",
  "Tecnología": "#6366f1",
  "Otros": "#f87171",
};

export function colorForCategory(name) {
  return CATEGORY_COLORS[name] || "#94a3b8";
}