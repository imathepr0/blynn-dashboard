// Errores de la API y su traducción a mensajes para el usuario.

export class ApiError extends Error {
  /**
   * @param {number} status  Código HTTP; 0 = no hubo respuesta (red caída, tiempo agotado, mala configuración).
   * @param {string|Array} detail  El campo `detail` del backend: texto, o lista de errores de validación (422).
   */
  constructor(status, detail, { code } = {}) {
    super(typeof detail === "string" ? detail : "Error de validación");
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

const ETIQUETAS = {
  amount: "El monto", merchant: "El comercio", category: "La categoría", date: "La fecha",
  description: "La descripción", payment_method: "El método de pago", color: "El color",
  source: "El origen", type: "El tipo", name: "El nombre", icon: "El ícono", budget: "El presupuesto",
  title: "El título", target_amount: "El monto objetivo", current_amount: "El monto actual",
  deadline: "La fecha límite", contribution_mode: "El modo de aporte", contribution_percent: "El porcentaje",
  contribution_amount: "El monto del aporte", contribution_frequency: "La frecuencia",
  next_contribution_date: "La próxima fecha de aporte", full_name: "El nombre",
  monthly_budget: "El presupuesto mensual", preferences: "Las preferencias", password: "La contraseña",
  email: "El correo", items: "La lista", mode: "El modo",
};

// Razón por tipo de error de Pydantic. Los mensajes propios del backend
// (value_error) ya vienen en español y se usan tal cual.
const RAZONES = {
  missing: "es obligatorio",
  int_parsing: "debe ser un número entero",
  int_type: "debe ser un número entero",
  float_type: "debe ser un número",
  float_parsing: "debe ser un número",
  bool_type: "debe ser verdadero o falso",
  greater_than: "debe ser mayor que 0",
  greater_than_equal: "no puede ser negativo",
  less_than_equal: "es demasiado grande",
  string_type: "debe ser texto",
  string_too_short: "es obligatorio",
  string_too_long: "es demasiado largo",
  string_pattern_mismatch: "tiene un formato inválido",
  literal_error: "tiene un valor no permitido",
  date_type: "debe ser una fecha",
  date_parsing: "no es una fecha válida",
  date_from_datetime_parsing: "no es una fecha válida",
  too_short: "no puede estar vacía",
  too_long: "tiene demasiados elementos",
  extra_forbidden: "no está permitido",
};

function describirValidacion(lista) {
  const partes = [];
  for (const item of lista) {
    const loc = Array.isArray(item.loc) ? item.loc : [];
    const campo = [...loc].reverse().find((x) => typeof x === "string" && x !== "body");
    if (campo === "email") {
      partes.push("Ingresa un correo electrónico válido");
      continue;
    }
    const etiqueta = ETIQUETAS[campo] || (campo ? `El campo «${campo}»` : "Un dato");
    let razon = RAZONES[item.type];
    if (!razon && item.type === "value_error" && typeof item.msg === "string") {
      razon = item.msg.replace(/^Value error,\s*/i, "");
    }
    partes.push(`${etiqueta} ${razon || "no es válido"}`);
  }
  const unicas = [...new Set(partes)];
  if (unicas.length === 0) return "Revisa los datos ingresados.";
  return unicas.slice(0, 3).join(". ") + ".";
}

/** Mensaje en español, apto para mostrar al usuario. */
export function describirError(err) {
  if (!(err instanceof ApiError)) {
    return err?.message || "Ocurrió un error inesperado.";
  }
  const { status, detail } = err;
  if (status === 0) {
    return typeof detail === "string" && detail
      ? detail
      : "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.";
  }
  if (Array.isArray(detail)) return describirValidacion(detail);
  if (status >= 500) return "Ocurrió un error en el servidor. Intenta nuevamente en unos minutos.";
  if (typeof detail === "string" && detail) return detail;
  if (status === 401) return "Tu sesión expiró. Inicia sesión nuevamente.";
  if (status === 403) return "No tienes permiso para hacer esto.";
  if (status === 404) return "No se encontró lo que buscabas.";
  return "No se pudo completar la operación.";
}
