import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ReceiptFlurry } from "@/components/loading/LoadingAnimations";

const TIPS = [
  "Esto puede tardar un poco...",
  "Espera mientras el sistema lee tu boleta",
  "Asegúrate de haber tomado la foto en un lugar con buena iluminación",
  "Estamos extrayendo el comercio, la fecha y el total",
  "Mantén la boleta plana y sin sombras para un mejor resultado",
];

// La barra sube rápido al inicio y luego cada vez más lento, pero SIEMPRE se mueve (sin pasar
// de 95% hasta que el servidor responde). Una lectura normal tarda unos segundos; la primera
// del día puede tardar más de un minuto porque el servicio de lectura se duerme por inactividad.
const TAU_MS = 25000;
const LENTO_MS = 15000; // pasado este tiempo, se explica por qué tarda

export default function ProcessingScreen({ type = "boleta", done = false, onComplete }) {
  const [progress, setProgress] = useState(0);
  const [tipIdx, setTipIdx] = useState(0);
  const [lento, setLento] = useState(false);
  const progressRef = useRef(0);
  const doneRef = useRef(false);
  doneRef.current = done;

  // Avanza hacia 95% (sin llegar) mientras el backend trabaja
  useEffect(() => {
    const start = Date.now();
    const t = setInterval(() => {
      if (doneRef.current) return;
      const p = 95 * (1 - Math.exp(-(Date.now() - start) / TAU_MS));
      progressRef.current = p;
      setProgress(p);
    }, 200);
    return () => clearInterval(t);
  }, []);

  // Si tarda más de lo normal, avisa (no es un error: el servicio puede estar despertando)
  useEffect(() => {
    const t = setTimeout(() => setLento(true), LENTO_MS);
    return () => clearTimeout(t);
  }, []);

  // Mensajes que van cambiando con los segundos
  useEffect(() => {
    const t = setInterval(() => setTipIdx((i) => (i + 1) % TIPS.length), 5000);
    return () => clearInterval(t);
  }, []);

  // Cuando el backend responde: completa la barra y avisa
  useEffect(() => {
    if (!done) return;
    const startP = progressRef.current;
    const start = Date.now();
    const t = setInterval(() => {
      const k = Math.min(1, (Date.now() - start) / 700);
      const p = startP + (100 - startP) * k;
      progressRef.current = p;
      setProgress(p);
      if (k >= 1) {
        clearInterval(t);
        onComplete?.();
      }
    }, 50);
    return () => clearInterval(t);
  }, [done]);

  return (
    <div className="flex flex-col items-center gap-6 py-2 w-full max-w-xs mx-auto">
      <ReceiptFlurry />

      <div className="w-full">
        <div className="flex justify-between text-xs font-medium text-slate-400 mb-1.5">
          <span>Leyendo tu {type}</span>
          <span>{Math.round(progress)}%</span>
        </div>
        <div className="w-full h-2.5 bg-slate-200 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-400 transition-[width] duration-200 ease-linear"
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="h-6 mt-3 flex items-center justify-center">
          <AnimatePresence mode="wait">
            <motion.p
              key={tipIdx}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.3 }}
              className="text-sm text-slate-500 text-center"
            >
              {TIPS[tipIdx]}
            </motion.p>
          </AnimatePresence>
        </div>

        {lento && !done && (
          <p role="status" className="mt-2 text-xs text-slate-400 text-center">
            Está tardando más de lo normal: el servicio de lectura puede estar despertando. La primera lectura del
            día puede demorar un par de minutos. No cierres esta ventana.
          </p>
        )}
      </div>
    </div>
  );
}