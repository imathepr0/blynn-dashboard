// Almacén de los tokens de sesión en el navegador.
//
// Se guardan en localStorage, lo que permite que la sesión sobreviva al
// recargar la página y se comparta entre pestañas. Limitación conocida: si la
// app tuviera una vulnerabilidad XSS, un script malicioso podría leerlos
// (una cookie HttpOnly lo evitaría, pero exige que frontend y API estén bajo
// el mismo sitio; ver backend/README.md, "Límites conocidos", punto 7).
//
// Si localStorage no está disponible (navegación privada restrictiva), se usa
// memoria: la sesión dura hasta recargar la página.

const CLAVE_ACCESO = "blynn.access_token";
const CLAVE_REFRESCO = "blynn.refresh_token";

let memoria = { access: null, refresh: null };
const oyentes = new Set();

function obtenerAlmacenamiento() {
  try {
    const s = window.localStorage;
    const prueba = "__blynn_prueba__";
    s.setItem(prueba, "1");
    s.removeItem(prueba);
    return s;
  } catch {
    return null;
  }
}

function notificar() {
  const valor = tokenStore.leer();
  oyentes.forEach((cb) => {
    try {
      cb(valor);
    } catch {
      /* un oyente con error no debe impedir avisar a los demás */
    }
  });
}

export const tokenStore = {
  leer() {
    const s = obtenerAlmacenamiento();
    if (!s) return { ...memoria };
    return { access: s.getItem(CLAVE_ACCESO), refresh: s.getItem(CLAVE_REFRESCO) };
  },

  guardar({ access, refresh }) {
    const s = obtenerAlmacenamiento();
    if (s) {
      s.setItem(CLAVE_ACCESO, access);
      s.setItem(CLAVE_REFRESCO, refresh);
    } else {
      memoria = { access, refresh };
    }
    notificar();
  },

  borrar() {
    const s = obtenerAlmacenamiento();
    if (s) {
      s.removeItem(CLAVE_ACCESO);
      s.removeItem(CLAVE_REFRESCO);
    } else {
      memoria = { access: null, refresh: null };
    }
    notificar();
  },

  /** Avisa de cualquier cambio de tokens, propio o hecho desde otra pestaña. */
  suscribir(cb) {
    oyentes.add(cb);
    return () => oyentes.delete(cb);
  },
};

// Cambios hechos desde OTRA pestaña (el evento "storage" no se dispara en la
// misma pestaña que escribe).
if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key === null || e.key === CLAVE_ACCESO || e.key === CLAVE_REFRESCO) notificar();
  });
}
