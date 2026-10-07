import React from "react";
import { Target, Pencil, Trash2, PlusCircle } from "lucide-react";
import { formatCLP, formatDateShort } from "@/lib/format";
import { monthlyRate, projectedCompletion, FREQ_LABELS } from "@/lib/goalEngine";

const MONTHS_FULL = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

export default function GoalCard({ goal, excedente = 0, contributions = [], onEdit, onDelete, onAdd }) {
  const pct = goal.target_amount ? Math.min(100, ((goal.current_amount || 0) / goal.target_amount) * 100) : 0;
  const done = goal.target_amount > 0 && (goal.current_amount || 0) >= goal.target_amount;
  const rate = monthlyRate(goal, excedente, contributions);
  const proj = done ? null : projectedCompletion(goal, rate);
  const color = goal.color || "#22c55e";

  let modeChip = "Aporte manual";
  if (goal.contribution_mode === "percent_surplus") modeChip = `${goal.contribution_percent || 0}% del excedente mensual`;
  else if (goal.contribution_mode === "fixed") modeChip = `${formatCLP(goal.contribution_amount)} cada ${FREQ_LABELS[goal.contribution_frequency] || "mes"}`;

  return (
    <div className="bg-[#f5f7fa] rounded-3xl p-6 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300 group">
      <div className="flex items-center gap-3 mb-4">
        <span className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: `${color}15`, color }}>
          <Target className="w-5 h-5" />
        </span>
        <div className="flex-1 min-w-0">
          <span className="font-semibold text-slate-700 block truncate">{goal.title}</span>
          <span className="text-xs text-slate-400">{modeChip}</span>
        </div>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={() => onEdit(goal)} className="text-slate-400 hover:text-sky-500 p-1.5 rounded-lg hover:bg-sky-50 transition-colors">
            <Pencil className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => onDelete(goal)} className="text-slate-400 hover:text-red-500 p-1.5 rounded-lg hover:bg-red-50 transition-colors">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <div className="flex justify-between text-sm mb-2">
        <span className="text-slate-500 font-medium">{formatCLP(goal.current_amount)}</span>
        <span className="text-slate-400">de {formatCLP(goal.target_amount)}</span>
      </div>
      <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="flex items-center justify-between mt-2">
        <span className="text-sm font-semibold" style={{ color }}>{Math.round(pct)}%</span>
        {done && <span className="text-xs font-semibold text-emerald-600">¡Meta lograda!</span>}
      </div>
      <div className="mt-3 space-y-1">
        {goal.contribution_mode !== "manual" && goal.next_contribution_date && !done && (
          <p className="text-xs text-slate-400">Próximo aporte: {formatDateShort(goal.next_contribution_date)}</p>
        )}
        {proj && (
          <p className="text-xs text-emerald-600 font-medium">Al este ritmo la lograrías hacia {MONTHS_FULL[proj.getMonth()]} {proj.getFullYear()}</p>
        )}
      </div>
      <button onClick={() => onAdd(goal)} className="mt-4 w-full flex items-center justify-center gap-2 py-2 rounded-xl border border-emerald-200 text-emerald-600 text-sm font-medium hover:bg-emerald-50 transition-colors">
        <PlusCircle className="w-4 h-4" /> Aportar ahora
      </button>
    </div>
  );
}