import React from "react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { formatCLP, colorForCategory } from "@/lib/format";

export default function CategoryDonut({ data }) {
  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <div className="bg-white rounded-3xl p-7 shadow-sm hover:shadow-md transition-shadow duration-300">
      <h3 className="text-xl font-semibold font-heading text-slate-700 mb-4">Gastos por categoría</h3>
      <div className="flex items-center gap-6">
        <div className="w-44 h-44 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                innerRadius={52}
                outerRadius={80}
                paddingAngle={2}
                dataKey="value"
                stroke="none"
              >
                {data.map((d) => (
                  <Cell key={d.name} fill={colorForCategory(d.name)} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex-1 space-y-2.5">
          {data.map((d) => (
            <div key={d.name} className="flex items-center text-sm group cursor-default">
              <span className="w-3 h-3 rounded-full mr-3 transition-transform group-hover:scale-125" style={{ background: colorForCategory(d.name) }} />
              <span className="text-slate-600 flex-1">{d.name}</span>
              <span className="text-slate-400 w-12 text-right">{total ? Math.round((d.value / total) * 100) : 0}%</span>
              <span className="text-slate-700 font-semibold w-24 text-right">{formatCLP(d.value)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}