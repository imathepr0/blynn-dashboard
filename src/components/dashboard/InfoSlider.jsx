import React, { useState, useEffect } from "react";
import { Target, AlertTriangle, Wallet } from "lucide-react";
import { Link } from "react-router-dom";
import { formatCLP } from "@/lib/format";

export default function InfoSlider({ goal, alert }) {
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % 2), 5000);
    return () => clearInterval(t);
  }, []);

  const alertActive = alert && (alert.pct >= 85 || alert.pct > 100);
  const alertExceeded = alert && alert.pct > 100;

  return (
    <div className="bg-[#f5f7fa] rounded-2xl p-6 shadow-md hover:shadow-lg transition-shadow duration-300">
      <div className="flex gap-1.5 mb-4">
        <button
          onClick={() => setIdx(0)}
          className={`h-1.5 rounded-full transition-all duration-300 ${idx === 0 ? "w-8 bg-sky-500" : "w-4 bg-slate-200"}`}
        />
        <button
          onClick={() => setIdx(1)}
          className={`h-1.5 rounded-full transition-all duration-300 ${idx === 1 ? "w-8 bg-emerald-500" : "w-4 bg-slate-200"}`}
        />
      </div>

      {idx === 0 && (
        <div className="animate-in fade-in duration-300">
          {goal ? (
            <>
              <div className="flex items-center gap-3 mb-4">
                <span className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-500">
                  <Target className="w-5 h-5" />
                </span>
                <span className="font-semibold text-slate-700">{goal.title}</span>
              </div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-slate-500">{formatCLP(goal.current_amount)}</span>
                <span className="text-slate-400">de {formatCLP(goal.target_amount)}</span>
              </div>
              <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full transition-all duration-500" style={{ width: `${goal.target_amount ? Math.min(100, (goal.current_amount / goal.target_amount) * 100) : 0}%` }} />
              </div>
              <div className="text-right text-sm text-emerald-500 font-semibold font-heading tabular-nums mt-2">
                {goal.target_amount ? Math.round((goal.current_amount / goal.target_amount) * 100) : 0}%
              </div>
            </>
          ) : (
            <div className="text-center py-6">
              <span className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-500 mx-auto mb-3">
                <Target className="w-5 h-5" />
              </span>
              <div className="text-sm text-slate-500 mb-1">Aún no tienes metas</div>
              <Link to="/metas" className="text-xs text-sky-500 font-medium hover:underline">Crea tu primera meta</Link>
            </div>
          )}
        </div>
      )}

      {idx === 1 && (
        <div className="animate-in fade-in duration-300">
          {alert ? (
            <>
              <div className="flex items-center gap-3 mb-4">
                <span className={`w-10 h-10 rounded-xl flex items-center justify-center ${alertActive ? "bg-amber-50 text-amber-500" : "bg-slate-100 text-slate-500"}`}>
                  {alertActive ? <AlertTriangle className="w-5 h-5" /> : <Wallet className="w-5 h-5" />}
                </span>
                <span className="font-semibold text-slate-700">{alertActive ? "Alerta de presupuesto" : "Presupuesto"}</span>
              </div>
              <div className="text-sm text-slate-400 mb-3">
                Has usado <span className={`font-bold font-heading tabular-nums ${alertExceeded ? "text-red-500" : alert.pct >= 85 ? "text-amber-500" : "text-slate-600"}`}>{Math.round(alert.pct)}%</span> del presupuesto
              </div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-slate-500">{formatCLP(alert.spent)}</span>
                <span className="text-slate-400">de {formatCLP(alert.budget)}</span>
              </div>
              <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all duration-500 ${alertExceeded ? "bg-red-500" : alert.pct >= 85 ? "bg-amber-500" : "bg-emerald-500"}`} style={{ width: `${Math.min(100, alert.pct)}%` }} />
              </div>
            </>
          ) : (
            <div className="text-center py-6">
              <span className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-slate-500 mx-auto mb-3">
                <Wallet className="w-5 h-5" />
              </span>
              <div className="text-sm text-slate-500 mb-1">Sin presupuesto mensual</div>
              <Link to="/ajustes" className="text-xs text-sky-500 font-medium hover:underline">Establécelo en Configuración</Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}