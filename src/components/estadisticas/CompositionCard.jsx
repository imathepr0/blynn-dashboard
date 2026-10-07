import React from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { formatCLP, isSameMonth } from "@/lib/format";

export default function CompositionCard({ incomes, expenses, contributions }) {
  const now = new Date();
  const inc = incomes.filter((i) => isSameMonth(i.date, now)).reduce((s, i) => s + (i.amount || 0), 0);
  const exp = expenses.filter((e) => isSameMonth(e.date, now)).reduce((s, e) => s + (e.amount || 0), 0);
  const aportes = contributions.filter((c) => isSameMonth(c.date, now)).reduce((s, c) => s + (c.amount || 0), 0);
  const disponible = Math.max(0, inc - exp - aportes);

  const data = [
    { name: "Gastos", value: exp, color: "#ef4444" },
    { name: "Aportes a metas", value: aportes, color: "#38bdf8" },
  ];
  if (inc > 0) data.push({ name: "Disponible", value: disponible, color: "#22c55e" });

  const tooltipStyle = { borderRadius: 12, border: "none", boxShadow: "0 4px 20px rgba(0,0,0,0.08)" };
  const hasData = data.some((d) => d.value > 0);

  return (
    <div className="bg-[#f5f7fa] rounded-3xl p-7 shadow-sm">
      <h3 className="text-lg font-semibold font-heading text-slate-700 mb-1">Composición del mes</h3>
      <p className="text-sm text-slate-400 mb-6">En qué se usa tu dinero este mes</p>
      <div className="h-72">
        {hasData ? (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={3}>
                {data.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => formatCLP(v)} contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-slate-400 text-sm gap-2">
            <span>Sin datos este mes</span>
          </div>
        )}
      </div>
      {inc === 0 && (
        <p className="text-xs text-slate-400 text-center">Registra tus ingresos para ver cuánto te queda disponible.</p>
      )}
    </div>
  );
}