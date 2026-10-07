import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/api";
import { useAuth } from "@/lib/AuthContext";
import ComparisonCard from "@/components/dashboard/ComparisonCard";
import ExpenseBarChart from "@/components/dashboard/ExpenseBarChart";
import SaldoCard from "@/components/dashboard/SaldoCard";
import InfoSlider from "@/components/dashboard/InfoSlider";
import RecentExpenses from "@/components/dashboard/RecentExpenses";
import ResumenSkeleton from "@/components/dashboard/ResumenSkeleton";
import { formatCLP, dateStrLocal, isSameMonth, monthKeyOf } from "@/lib/format";

export default function Resumen() {
  const { user: usuarioActual } = useAuth();
  const [data, setData] = useState(null);

  useEffect(() => {
    Promise.all([
      api.expenses.list({ sort: "-date", limit: 300 }),
      api.categories.list(),
      api.goals.list({ sort: "-created_date", limit: 1 }),
      Promise.resolve(usuarioActual),
      api.incomes.list({ sort: "-date", limit: 100 }),
    ]).then(([expenses, categories, goals, user, incomes]) => {
      const now = new Date();

      // Daily: last 7 days
      const dailyData = [];
      for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        const ds = dateStrLocal(d);
        const total = expenses.filter((e) => e.date === ds).reduce((s, e) => s + (e.amount || 0), 0);
        dailyData.push(total);
      }
      const todayTotal = dailyData[dailyData.length - 1] || 0;
      const prevDaysAvg = dailyData.slice(0, -1).reduce((s, v) => s + v, 0) / 6;
      const dailyDelta = prevDaysAvg ? (((todayTotal - prevDaysAvg) / prevDaysAvg) * 100).toFixed(0) : 0;

      // Monthly: gastos del mes actual
      const thisMonthTotal = expenses
        .filter((e) => isSameMonth(e.date, now))
        .reduce((s, e) => s + (e.amount || 0), 0);

      // Monthly sparkline: last 6 months
      const monthLabels = [];
      const monthlyData = [];
      const shortMonths = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
      for (let i = 5; i >= 0; i--) {
        const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
        monthLabels.push(shortMonths[d.getMonth()]);
        const total = expenses
          .filter((e) => monthKeyOf(e.date) === monthKeyOf(d))
          .reduce((s, e) => s + (e.amount || 0), 0);
        monthlyData.push(total);
      }

      // Bar chart: by category (solo gastos del mes actual)
      const byCat = {};
      expenses
        .filter((e) => isSameMonth(e.date, now))
        .forEach((e) => { byCat[e.category] = (byCat[e.category] || 0) + (e.amount || 0); });
      const barData = Object.entries(byCat).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);

      // Saldo: presupuesto mensual del usuario si está definido, si no, suma de presupuestos por categoría
      const userBudget = user?.monthly_budget || 0;
      const categoriesBudget = categories.reduce((s, c) => s + (c.budget || 0), 0);
      const totalBudget = userBudget > 0 ? userBudget : categoriesBudget;
      const available = totalBudget - thisMonthTotal;
      const monthIncome = incomes.filter((i) => isSameMonth(i.date, now)).reduce((s, i) => s + (i.amount || 0), 0);
      const excedente = Math.max(0, monthIncome - totalBudget);

      // Goal
      const goal = goals[0];

      // Alert: presupuesto mensual del usuario (encuesta / configuración)
      const alert = userBudget > 0 ? {
        spent: thisMonthTotal,
        budget: userBudget,
        pct: (thisMonthTotal / userBudget) * 100,
      } : null;

      setData({
        recent: expenses.slice(0, 5),
        dailyData, todayTotal, dailyDelta,
        monthlyData, monthLabels, thisMonthTotal,
        barData,
        available, totalBudget, totalSpent: thisMonthTotal, excedente,
        goal, alert,
      });
    });
  }, []);

  if (!data) {
    return <ResumenSkeleton />;
  }

  return (
    <div className="max-w-6xl">
      <h1 className="text-3xl font-bold font-heading text-slate-700 mb-6">Resumen General</h1>

      {/* Row 1: Comparison cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-6">
        <ComparisonCard
          label="Gasto de hoy"
          value={formatCLP(data.todayTotal)}
          sublabel="vs promedio últimos 7 días"
          data={data.dailyData}
          labels={["L", "M", "X", "J", "V", "S", "H"]}
          color="#38bdf8"
          delta={data.dailyDelta}
        />
        <ComparisonCard
          label="Gasto del mes"
          value={formatCLP(data.thisMonthTotal)}
          sublabel="Evolución últimos 6 meses"
          data={data.monthlyData}
          labels={data.monthLabels}
          color="#22c55e"
        />
      </div>

      {/* Row 2: Bar chart + Side panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-6">
        <Link to="/estadisticas" className="lg:col-span-2 block hover:opacity-95 transition-opacity cursor-pointer">
          <ExpenseBarChart data={data.barData} />
        </Link>
        <div className="space-y-5">
          <SaldoCard available={data.available} totalBudget={data.totalBudget} totalSpent={data.totalSpent} excedente={data.excedente} />
          <InfoSlider goal={data.goal} alert={data.alert} />
        </div>
      </div>

      {/* Row 3: Recent expenses */}
      <RecentExpenses items={data.recent} />
    </div>
  );
}