import React from "react";
import { motion } from "framer-motion";
import { Receipt, Sparkles, Check, ShoppingBag, DollarSign, Cloud } from "lucide-react";

export function MagnifierReceipt() {
  const items = [
    ["Pan integral", "$1.990"],
    ["Frutas", "$2.490"],
    ["Verduras", "$1.690"],
    ["Limpieza", "$2.890"],
  ];
  return (
    <div className="relative w-48">
      <motion.div
        className="bg-white rounded-lg shadow-lg border border-slate-100 p-3"
        animate={{ rotate: [-0.5, 0.5, -0.5] }}
        transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
      >
        <div className="flex items-center gap-1.5 mb-2">
          <Cloud className="w-3.5 h-3.5 text-sky-500 shrink-0" />
          <span className="text-[10px] font-bold tracking-widest text-slate-800">BOLETA</span>
        </div>
        <div className="text-[8px] text-slate-500 leading-relaxed mb-2">
          <div>Fecha: 28 oct 2023</div>
          <div>Nº BOL-9471</div>
          <div>De: Almacén Central</div>
        </div>
        <div className="space-y-1 mb-2">
          {items.map(([name, price]) => (
            <div key={name} className="flex justify-between text-[8px] text-slate-600">
              <span>{name}</span>
              <span>{price}</span>
            </div>
          ))}
        </div>
        <div className="flex justify-between text-[8px] text-slate-700 bg-emerald-100 rounded px-1 py-0.5 mb-1">
          <span>Subtotal:</span>
          <span>$9.060</span>
        </div>
        <div className="flex justify-between text-[8px] text-slate-500 mb-1">
          <span>IVA (19%):</span>
          <span>$1.721</span>
        </div>
        <div className="flex justify-between text-[8px] font-semibold text-slate-700 border-t border-slate-100 pt-1">
          <span>Total:</span>
          <span>$10.781</span>
        </div>
        <div className="text-[9px] font-bold text-sky-500 text-center mt-2">
          TOTAL PAGADO: $10.781
        </div>
      </motion.div>
      <motion.div
        className="absolute w-14 h-14 rounded-full border-2 border-sky-500 bg-white/25 shadow-lg z-10"
        animate={{ x: [-34, 26, -34], y: [58, 84, 58] }}
        transition={{ repeat: Infinity, duration: 3.6, ease: "easeInOut" }}
      >
        <span className="absolute -bottom-1.5 -right-1.5 w-4 h-1.5 rounded-full bg-sky-500 rotate-[-45deg]" />
      </motion.div>
    </div>
  );
}

export function BoletaTotal() {
  return (
    <motion.div
      className="w-28 h-36 bg-white rounded-xl shadow-lg border border-slate-100 p-3 flex flex-col"
      animate={{ y: [0, -5, 0] }}
      transition={{ repeat: Infinity, duration: 2.2, ease: "easeInOut" }}
    >
      <div className="text-center text-[10px] font-bold tracking-widest text-slate-400 mb-2">BOLETA</div>
      <div className="space-y-1.5">
        <div className="h-1.5 bg-slate-100 rounded w-full" />
        <div className="h-1.5 bg-slate-100 rounded w-4/5" />
        <div className="h-1.5 bg-slate-100 rounded w-2/3" />
      </div>
      <div className="mt-auto pt-2 border-t border-dashed border-slate-200">
        <div className="text-[9px] text-slate-400 font-medium tracking-wide">TOTAL</div>
        <motion.div
          className="font-bold text-emerald-500 text-lg leading-tight"
          animate={{ opacity: [0.4, 1, 0.4], scale: [0.96, 1.04, 0.96] }}
          transition={{ repeat: Infinity, duration: 1.6, ease: "easeInOut" }}
        >
          $12.990
        </motion.div>
      </div>
    </motion.div>
  );
}

export function DonutChart() {
  return (
    <div className="relative w-28 h-28 flex items-center justify-center">
      <svg viewBox="0 0 100 100" className="w-24 h-24 -rotate-90">
        <circle cx="50" cy="50" r="42" fill="none" stroke="#e2e8f0" strokeWidth="10" />
        <motion.circle
          cx="50" cy="50" r="42" fill="none" stroke="#0ea5e9" strokeWidth="10" strokeLinecap="round"
          strokeDasharray="264"
          animate={{ strokeDashoffset: [264, 80, 264] }}
          transition={{ repeat: Infinity, duration: 2.6, ease: "easeInOut" }}
        />
      </svg>
      <motion.span
        className="absolute"
        animate={{ scale: [1, 1.15, 1], opacity: [0.7, 1, 0.7] }}
        transition={{ repeat: Infinity, duration: 1.6, ease: "easeInOut" }}
      >
        <DollarSign className="w-8 h-8 text-sky-500" />
      </motion.span>
    </div>
  );
}

export function CategoryChips() {
  const cats = [
    { name: "Transporte", color: "#0ea5e9" },
    { name: "Alimentación", color: "#22c55e" },
    { name: "Hogar", color: "#f59e0b" },
    { name: "Ocio", color: "#a78bfa" },
  ];
  return (
    <div className="w-32 flex flex-col gap-2">
      {cats.map((c, i) => (
        <motion.div
          key={c.name}
          className="rounded-lg px-2.5 py-1.5 text-[11px] font-semibold flex items-center gap-1.5 shadow-sm"
          style={{ backgroundColor: `${c.color}15`, color: c.color }}
          animate={{ x: [-8, 0, -8], opacity: [0.3, 1, 0.3] }}
          transition={{ repeat: Infinity, duration: 2.4, delay: i * 0.3, ease: "easeInOut" }}
        >
          <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: c.color }} />
          {c.name}
        </motion.div>
      ))}
    </div>
  );
}

export function ReceiptFlurry() {
  return (
    <div className="relative w-32 h-32 flex items-center justify-center">
      <motion.div
        className="w-14 h-20 bg-white rounded-lg shadow-lg border-t-4 border-emerald-400 z-10 flex flex-col gap-1.5 p-2"
        animate={{ y: [0, -5, 0], rotate: [-2, 2, -2] }}
        transition={{ repeat: Infinity, duration: 2.4, ease: "easeInOut" }}
      >
        <div className="text-[7px] font-bold text-slate-400 tracking-widest text-center">BOLETA</div>
        <div className="h-1.5 bg-slate-100 rounded w-full" />
        <div className="h-1.5 bg-slate-100 rounded w-3/4" />
        <div className="text-[8px] font-bold text-emerald-500 text-center mt-auto">TOTAL $12.990</div>
      </motion.div>
      {[{ x: -42, delay: 0 }, { x: 42, delay: 0.7 }].map((o, i) => (
        <motion.div
          key={i}
          className="absolute w-8 h-11 bg-white rounded-md shadow-md border-t-2 border-sky-300 flex items-center justify-center"
          animate={{ y: [14, -14, 14], opacity: [0.4, 1, 0.4], rotate: o.x > 0 ? [6, -4, 6] : [-6, 4, -6] }}
          transition={{ repeat: Infinity, duration: 2.2, delay: o.delay, ease: "easeInOut" }}
          style={{ x: o.x }}
        >
          <Receipt className="w-4 h-4 text-sky-400" />
        </motion.div>
      ))}
    </div>
  );
}

export function AIChecks() {
  const steps = ["Comercio detectado", "Fecha leída", "Total encontrado"];
  return (
    <div className="w-40 bg-white rounded-xl shadow-lg border border-slate-100 p-3 flex flex-col gap-2">
      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-sky-500">
        <Sparkles className="w-3.5 h-3.5 shrink-0" /> IA leyendo tu boleta
      </div>
      {steps.map((s, i) => (
        <motion.div
          key={s}
          className="flex items-center gap-1.5"
          animate={{ opacity: [0.25, 1, 0.25] }}
          transition={{ repeat: Infinity, duration: 2.1, delay: i * 0.5, ease: "easeInOut" }}
        >
          <motion.span
            className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-500 flex items-center justify-center shrink-0"
            animate={{ scale: [0.8, 1.15, 0.8] }}
            transition={{ repeat: Infinity, duration: 1.4, delay: i * 0.5 }}
          >
            <Check className="w-2.5 h-2.5" />
          </motion.span>
          <span className="text-[11px] text-slate-600 font-medium">{s}</span>
        </motion.div>
      ))}
    </div>
  );
}

export function GastoCard() {
  return (
    <motion.div
      className="w-36 bg-white rounded-xl shadow-lg border border-slate-100 p-3"
      animate={{ y: [0, -5, 0] }}
      transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
    >
      <div className="flex items-center gap-2">
        <motion.div
          className="w-8 h-8 rounded-lg bg-sky-100 text-sky-500 flex items-center justify-center shrink-0"
          animate={{ rotate: [0, -6, 6, 0] }}
          transition={{ repeat: Infinity, duration: 2 }}
        >
          <ShoppingBag className="w-4 h-4" />
        </motion.div>
        <div>
          <div className="text-[11px] font-semibold text-slate-700 leading-tight">Gasto registrado</div>
          <div className="text-[9px] text-slate-400">Alimentación · Hoy</div>
        </div>
      </div>
      <div className="mt-2 pt-2 border-t border-dashed border-slate-100 flex items-center justify-between">
        <span className="text-[9px] text-slate-400 font-medium">Monto</span>
        <motion.span
          className="font-bold text-emerald-500 text-sm"
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ repeat: Infinity, duration: 1.4 }}
        >
          $4.990
        </motion.span>
      </div>
    </motion.div>
  );
}

export function SaldoCompare() {
  return (
    <div className="w-32 bg-white rounded-xl shadow-lg border border-slate-100 p-3 flex flex-col gap-2.5">
      <div className="text-[11px] font-semibold text-slate-700">Resumen del mes</div>
      <div>
        <div className="flex justify-between text-[9px] text-slate-400 font-medium mb-1">
          <span>Ingresos</span><span>$500.000</span>
        </div>
        <div className="h-2.5 rounded-full bg-slate-100 overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-emerald-400"
            animate={{ width: ["10%", "88%", "10%"] }}
            transition={{ repeat: Infinity, duration: 2.6, ease: "easeInOut" }}
          />
        </div>
      </div>
      <div>
        <div className="flex justify-between text-[9px] text-slate-400 font-medium mb-1">
          <span>Gastos</span><span>$184.520</span>
        </div>
        <div className="h-2.5 rounded-full bg-slate-100 overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-sky-500"
            animate={{ width: ["10%", "46%", "10%"] }}
            transition={{ repeat: Infinity, duration: 2.6, delay: 0.2, ease: "easeInOut" }}
          />
        </div>
      </div>
    </div>
  );
}

export function MetaProgreso() {
  return (
    <div className="w-32 bg-white rounded-xl shadow-lg border border-slate-100 p-3 text-center">
      <div className="text-[11px] font-semibold text-slate-700 mb-1.5">Meta: Viaje</div>
      <div className="relative w-16 h-16 mx-auto">
        <svg viewBox="0 0 100 100" className="w-16 h-16 -rotate-90">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#e2e8f0" strokeWidth="14" />
          <motion.circle
            cx="50" cy="50" r="40" fill="none" stroke="#22c55e" strokeWidth="14" strokeLinecap="round"
            strokeDasharray="251"
            animate={{ strokeDashoffset: [251, 120, 251] }}
            transition={{ repeat: Infinity, duration: 2.8, ease: "easeInOut" }}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-[11px] font-bold text-slate-700">45%</span>
      </div>
      <div className="text-[9px] text-slate-400 font-medium mt-1.5">$225.000 de $500.000</div>
    </div>
  );
}