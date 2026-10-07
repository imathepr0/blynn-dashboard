import React, { useEffect, useState } from "react";
import { api } from "@/api";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid, PieChart, Pie, Cell, AreaChart, Area, Legend } from "recharts";
import { formatCLP, colorForCategory, dateStrLocal, isSameMonth, monthKeyOf } from "@/lib/format";
import { TrendingUp, TrendingDown, Wallet } from "lucide-react";
import CompositionCard from "@/components/estadisticas/CompositionCard";
import GoalsProgressCard from "@/components/estadisticas/GoalsProgressCard";
import { excedenteDelMes } from "@/lib/goalEngine";

const MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
const MONTHS_FULL = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-[#f5f7fa] rounded-2xl p-5 shadow-sm flex items-center gap-4">
      <span className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: `${color}15`, color }}>
        <Icon className="w-5 h-5" />
      </span>
      <div>
        <div className="text-sm text-slate-400">{label}</div>
        <div className="text-xl font-bold font-heading tabular-nums text-slate-800">{value}</div>
      </div>
    </div>
  );
}

export default function Estadisticas() {
  const [expenses, setExpenses] = useState([]);
  const [incomes, setIncomes] = useState([]);
  const [goals, setGoals] = useState([]);
  const [contributions, setContributions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.expenses.list({ sort: "-date", limit: 500 }),
      api.incomes.list({ sort: "-date", limit: 200 }),
      api.goals.list({ sort: "-created_date" }),
      api.contributions.list({ sort: "-date", limit: 200 }),
    ]).then(([exps, incs, gs, cs]) => {
      setExpenses(exps);
      setIncomes(incs);
      setGoals(gs);
      setContributions(cs);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-8 h-8 border-4 border-slate-200 border-t-sky-500 rounded-full animate-spin" />
      </div>
    );
  }

  const now = new Date();

  // Monthly expense data
  const byMonth = {};
  expenses.forEach((e) => {
    byMonth[monthKeyOf(e.date)] = (byMonth[monthKeyOf(e.date)] || 0) + (e.amount || 0);
  });
  const monthlyData = [];
  for (let i = 5; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const key = monthKeyOf(d);
    monthlyData.push({ name: MONTHS[d.getMonth()], total: Math.round(byMonth[key] || 0) });
  }

  // Category donut
  const byCat = {};
  expenses.forEach((e) => { byCat[e.category] = (byCat[e.category] || 0) + (e.amount || 0); });
  const donutData = Object.entries(byCat).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);

  // Daily trend last 30 days
  const dailyData = [];
  for (let i = 29; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const ds = dateStrLocal(d);
    const total = expenses.filter((e) => e.date === ds).reduce((s, e) => s + (e.amount || 0), 0);
    dailyData.push({ name: `${d.getDate()}/${d.getMonth() + 1}`, total: Math.round(total) });
  }

  // Income vs Expense
  const incVsExp = [];
  for (let i = 3; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const mKey = monthKeyOf(d);
    const exp = byMonth[mKey] || 0;
    const inc = incomes
      .filter((i) => monthKeyOf(i.date) === mKey)
      .reduce((s, i) => s + (i.amount || 0), 0);
    incVsExp.push({ name: MONTHS[d.getMonth()], gastos: Math.round(exp), ingresos: Math.round(inc) });
  }

  // Summary
  const monthExp = byMonth[monthKeyOf(now)] || 0;
  const monthInc = incomes
    .filter((i) => isSameMonth(i.date, now))
    .reduce((s, i) => s + (i.amount || 0), 0);
  const balance = monthInc - monthExp;

  const tooltipStyle = { borderRadius: 12, border: "none", boxShadow: "0 4px 20px rgba(0,0,0,0.08)" };

  return (
    <div className="max-w-6xl space-y-6">
      <h1 className="text-3xl font-bold font-heading text-slate-700">Estadísticas</h1>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard icon={TrendingDown} label="Gastos del mes" value={formatCLP(monthExp)} color="#ef4444" />
        <StatCard icon={TrendingUp} label="Ingresos del mes" value={formatCLP(monthInc)} color="#22c55e" />
        <StatCard icon={Wallet} label="Balance del mes" value={formatCLP(balance)} color={balance >= 0 ? "#22c55e" : "#ef4444"} />
      </div>

      {/* Monthly bar chart */}
      <div className="bg-[#f5f7fa] rounded-3xl p-7 shadow-sm">
        <h3 className="text-lg font-semibold font-heading text-slate-700 mb-1">Gasto mensual</h3>
        <p className="text-sm text-slate-400 mb-6">Últimos 6 meses</p>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={monthlyData}>
              <CartesianGrid vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "#94a3b8" }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: "#94a3b8" }} tickFormatter={(v) => formatCLP(v)} width={90} />
              <Tooltip formatter={(v) => formatCLP(v)} cursor={{ fill: "#f0fdf4" }} contentStyle={tooltipStyle} />
              <Bar dataKey="total" fill="#22c55e" radius={[10, 10, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category donut */}
        <div className="bg-[#f5f7fa] rounded-3xl p-7 shadow-sm">
          <h3 className="text-lg font-semibold font-heading text-slate-700 mb-1">Gasto por categoría</h3>
          <p className="text-sm text-slate-400 mb-6">Distribución total</p>
          <div className="h-72">
            {donutData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={donutData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={3}>
                    {donutData.map((entry, i) => (
                      <Cell key={i} fill={colorForCategory(entry.name)} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => formatCLP(v)} contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: "12px" }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-400">Sin datos</div>
            )}
          </div>
        </div>

        {/* Daily trend */}
        <div className="bg-[#f5f7fa] rounded-3xl p-7 shadow-sm">
          <h3 className="text-lg font-semibold font-heading text-slate-700 mb-1">Tendencia diaria</h3>
          <p className="text-sm text-slate-400 mb-6">Últimos 30 días</p>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={dailyData}>
                <defs>
                  <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "#94a3b8", fontSize: 11 }} interval={4} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: "#94a3b8" }} tickFormatter={(v) => formatCLP(v)} width={90} />
                <Tooltip formatter={(v) => formatCLP(v)} contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="total" stroke="#38bdf8" strokeWidth={2} fill="url(#colorTotal)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Income vs Expense */}
      <div className="bg-[#f5f7fa] rounded-3xl p-7 shadow-sm">
        <h3 className="text-lg font-semibold font-heading text-slate-700 mb-1">Ingresos vs Gastos</h3>
        <p className="text-sm text-slate-400 mb-6">Comparación mensual</p>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={incVsExp}>
              <CartesianGrid vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "#94a3b8" }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: "#94a3b8" }} tickFormatter={(v) => formatCLP(v)} width={90} />
              <Tooltip formatter={(v) => formatCLP(v)} contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              <Bar dataKey="ingresos" fill="#22c55e" radius={[8, 8, 0, 0]} />
              <Bar dataKey="gastos" fill="#ef4444" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Composición del mes + Progreso de metas */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CompositionCard incomes={incomes} expenses={expenses} contributions={contributions} />
        <GoalsProgressCard goals={goals} contributions={contributions} excedente={excedenteDelMes(incomes, expenses)} />
      </div>
    </div>
  );
}