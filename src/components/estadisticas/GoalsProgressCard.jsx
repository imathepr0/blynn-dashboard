import React from "react";
import { Target } from "lucide-react";
import { formatCLP } from "@/lib/format";
import { monthlyRate, projectedCompletion } from "@/lib/goalEngine";

const MONTHS_FULL = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

export default function GoalsProgressCard({ goals = [], contributions = [], excedente = 0 }) {
  return (
    <div className="bg-[#f5f7fa] rounded-3xl p-7 shadow-sm">
      <h3 className="text-lg font-semibold font-heading text-slate-700 mb-1">Progreso de metas</h3>
      <p className="text-sm text-slate-400 mb-6">Avance y proyección de tus metas de ahorro</p>
      {goals.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-slate-400 text-sm gap-2">
          <Target className="w-8 h-8 text-slate-300" />
          <span>Aún no tienes metas</span>
        </div>
      ) : (
        <div className="space-y-5 max-h-72 overflow-y-auto pr-1">
          {goals.map((g) => {
            const pct = g.target_amount ? Math.min(100, ((g.current_amount || 0) / g.target_amount) * 100) : 0;
            const done = g.target_amount > 0 && (g.current_amount || 0) >= g.target_amount;
            const rate = monthlyRate(g, excedente, contributions);
            const proj = done ? null : projectedCompletion(g, rate);
            const color = g.color || "#22c55e";
            return (
              <div key={g.id}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-sm font-medium text-slate-700 truncate">{g.title}</span>
                  <span className="text-xs text-slate-400 shrink-0 ml-2">{formatCLP(g.current_amount)} / {formatCLP(g.target_amount)}</span>
                </div>
                <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: color }} />
                </div>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-xs font-semibold" style={{ color }}>{Math.round(pct)}%</span>
                  {done ? (
                    <span className="text-xs text-emerald-600 font-medium">¡Meta lograda!</span>
                  ) : proj ? (
                    <span className="text-xs text-slate-400">Al este ritmo: {MONTHS_FULL[proj.getMonth()]} {proj.getFullYear()}</span>
                  ) : (
                    <span className="text-xs text-slate-300">Sin proyección aún</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}