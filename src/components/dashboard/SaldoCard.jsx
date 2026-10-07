import React from "react";
import { Link } from "react-router-dom";
import { Wallet } from "lucide-react";
import { formatCLP } from "@/lib/format";

export default function SaldoCard({ available, totalBudget, totalSpent, excedente = 0 }) {
  const budget = Math.max(0, totalBudget || 0);
  const spent = Math.max(0, totalSpent || 0);
  const exc = Math.max(0, excedente || 0);
  const hasExcedente = exc > 0;
  const overshoot = Math.max(0, spent - budget);
  const remaining = Math.max(0, budget - spent);
  const total = budget + exc;
  const w = (v) => (total > 0 ? Math.min(100, (v / total) * 100) : 0);

  return (
    <Link to="/ingresos" className="group block bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-6 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 text-white relative overflow-hidden cursor-pointer">
      <div className="absolute -top-10 -right-10 w-28 h-28 rounded-full blur-2xl opacity-60" style={{ background: "radial-gradient(circle, rgba(56,189,248,0.3), transparent 70%)", animation: "blob-float 6s ease-in-out infinite" }} />
      <div className="flex items-center gap-2 mb-3">
        <span className="w-9 h-9 rounded-xl bg-white/10 flex items-center justify-center">
          <Wallet className="w-4 h-4 text-sky-400" />
        </span>
        <span className="text-sm text-slate-300 font-medium">Presupuesto disponible</span>
      </div>
      <div className={`text-3xl font-bold font-heading tabular-nums mb-3 ${available < 0 ? "text-red-400" : ""}`}>{formatCLP(available)}</div>
      <div className="space-y-1.5">
        <div className="flex justify-between text-xs text-slate-400">
          <span>Gastado: {formatCLP(spent)}</span>
          <span>de {formatCLP(budget)}</span>
        </div>
        <div className="h-2 bg-white/10 rounded-full overflow-hidden flex">
          <div className="h-full bg-gradient-to-r from-sky-500 to-sky-400 transition-all duration-500" style={{ width: `${w(Math.min(spent, budget))}%` }} />
          {overshoot > 0 && <div className="h-full bg-red-500 transition-all duration-500" style={{ width: `${w(Math.min(overshoot, budget))}%` }} />}
          <div className="h-full bg-white/25 transition-all duration-500" style={{ width: `${w(remaining)}%` }} />
          {hasExcedente && <div className="h-full bg-gradient-to-r from-emerald-400 to-emerald-500 transition-all duration-500" style={{ width: `${w(exc)}%` }} />}
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-400 pt-1">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-sky-500" /> Gastado</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-white/25" /> Presupuesto</span>
          {hasExcedente && <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-400" /> Excedente del sueldo</span>}
        </div>
        {hasExcedente && (
          <div className="text-xs text-emerald-400 font-medium pt-1">Excedente del sueldo: {formatCLP(exc)}</div>
        )}
      </div>
    </Link>
  );
}