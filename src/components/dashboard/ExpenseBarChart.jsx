import React from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid, Cell } from "recharts";
import { formatCLP, colorForCategory } from "@/lib/format";

export default function ExpenseBarChart({ data }) {
  return (
    <div className="bg-[#f5f7fa] rounded-2xl p-7 shadow-md hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-xl font-semibold font-heading text-slate-700">Gastos por categoría</h3>
          <p className="text-sm text-slate-400 mt-0.5">Distribución del gasto de este mes</p>
        </div>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="#f1f5f9" />
            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fill: "#94a3b8", fontSize: 12 }} tickFormatter={(v) => "$" + (v / 1000) + "K"} width={50} />
            <Tooltip
              formatter={(v) => formatCLP(v)}
              cursor={{ fill: "#f0f9ff" }}
              contentStyle={{ borderRadius: 12, border: "none", boxShadow: "0 4px 20px rgba(0,0,0,0.08)" }}
            />
            <Bar dataKey="value" radius={[8, 8, 0, 0]} maxBarSize={60}>
              {data.map((d) => (
                <Cell key={d.name} fill={colorForCategory(d.name)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}