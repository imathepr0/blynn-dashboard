import React from "react";
import { ResponsiveContainer, ComposedChart, Bar, Cell, XAxis, Line } from "recharts";

export default function ComparisonCard({ label, value, sublabel, data, labels, color, delta }) {
  const chartData = data.map((v, i) => ({ name: labels?.[i] || "", value: v }));
  const deltaNum = parseFloat(delta);
  const deltaTone = deltaNum > 0 ? "bg-red-50 text-red-500" : deltaNum < 0 ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-400";

  return (
    <div className="bg-[#f5f7fa] rounded-2xl p-6 shadow-md hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
      <div className="flex items-center justify-between mb-1">
        <span className="text-slate-500 font-medium text-sm">{label}</span>
        {delta !== undefined && (
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${deltaTone}`}>
            {deltaNum > 0 ? "+" : ""}{delta}%
          </span>
        )}
      </div>
      <div className="text-3xl font-bold font-heading tabular-nums text-slate-800 mb-1">{value}</div>
      <div className="text-sm text-slate-400 mb-3">{sublabel}</div>
      <div className="h-24">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "#cbd5e1", fontSize: 10 }} interval={0} />
            <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={36}>
              {chartData.map((_, i) => (
                <Cell key={i} fill={i === chartData.length - 1 ? color : `${color}66`} />
              ))}
            </Bar>
            <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2.5} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}