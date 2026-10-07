// Aviso de cambios de datos dentro de la app.
//
// La plataforma anterior avisaba en tiempo real ("subscribe") cuando cambiaba un gasto; el
// backend propio no tiene tiempo real. Como toda modificación pasa por la capa
// de API de esta pestaña, basta avisar desde ahí: las pantallas que muestran
// totales (p. ej. el gasto del mes en el menú) se actualizan al instante.
// No cubre cambios hechos desde OTRO dispositivo hasta que se recargue la vista.

const bus = new EventTarget();

export function emitirCambio(entidad) {
  bus.dispatchEvent(new CustomEvent("cambio", { detail: entidad }));
}

/** Llama a `cb` cuando cambien datos de `entidad`. Devuelve la función para cancelar. */
export function alCambiar(entidad, cb) {
  const manejador = (e) => {
    if (e.detail === entidad) cb();
  };
  bus.addEventListener("cambio", manejador);
  return () => bus.removeEventListener("cambio", manejador);
}
