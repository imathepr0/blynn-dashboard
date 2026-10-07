import { api } from "@/api";
import { dateStrLocal, isSameMonth } from "@/lib/format";

export const FREQ_DAYS = { dias: 1, semanas: 7, meses: 30 };
export const FREQ_LABELS = { dias: "día", semanas: "semana", meses: "mes" };
export const AUTO_CONFIDENCE_LIMIT = 3;

// El excedente del mes: ingresos reales - gastos reales (nunca negativo)
export function excedenteDelMes(incomes, expenses, now = new Date()) {
  const inc = incomes.filter((i) => isSameMonth(i.date, now)).reduce((s, i) => s + (i.amount || 0), 0);
  const exp = expenses.filter((e) => isSameMonth(e.date, now)).reduce((s, e) => s + (e.amount || 0), 0);
  return Math.max(0, inc - exp);
}

export function contributionAmount(goal, excedente) {
  if (goal.contribution_mode === "percent_surplus") {
    return Math.round(((excedente || 0) * (goal.contribution_percent || 0)) / 100);
  }
  if (goal.contribution_mode === "fixed") return goal.contribution_amount || 0;
  return 0;
}

export function nextContributionDate(goal, from = new Date()) {
  const d = new Date(from);
  const f = goal.contribution_frequency || "meses";
  if (f === "dias") d.setDate(d.getDate() + 1);
  else if (f === "semanas") d.setDate(d.getDate() + 7);
  else d.setMonth(d.getMonth() + 1);
  return dateStrLocal(d);
}

export function isContributionDue(goal, todayStr) {
  if (!goal || !goal.contribution_mode || goal.contribution_mode === "manual") return false;
  if ((goal.current_amount || 0) >= (goal.target_amount || 0)) return false;
  return !goal.next_contribution_date || goal.next_contribution_date <= todayStr;
}

// Cada operación es UNA llamada atómica al servidor: registra el aporte y suma
// su monto a la meta en la misma transacción (con la plataforma anterior eran dos llamadas y un
// corte a mitad dejaba la meta con un monto que no coincidía con sus aportes).
// El monto acumulado y el contador de aprobados los lleva el servidor.

export async function approveContribution(goal, amount) {
  // Sin excedente no hay nada que aportar (el servidor exige montos > 0):
  // aprobar un aporte de $0 equivale a omitirlo.
  if (!(amount > 0)) return skipContribution(goal);
  const { goal: actualizada } = await api.goals.addContribution(goal.id, {
    amount,
    date: dateStrLocal(new Date()),
    mode: "aprobado",
    next_contribution_date: nextContributionDate(goal),
  });
  return actualizada;
}

export async function skipContribution(goal) {
  return api.goals.update(goal.id, {
    next_contribution_date: nextContributionDate(goal),
  });
}

export async function autoContribute(goal, amount) {
  const { contribution } = await api.goals.addContribution(goal.id, {
    amount,
    date: dateStrLocal(new Date()),
    mode: "auto",
    next_contribution_date: nextContributionDate(goal),
  });
  return contribution;
}

export async function addManualContribution(goal, amount) {
  const { goal: actualizada } = await api.goals.addContribution(goal.id, {
    amount,
    date: dateStrLocal(new Date()),
    mode: "manual",
  });
  return actualizada;
}

// Deshace un aporte y descuenta su monto de la meta (el servidor nunca la deja bajo cero).
export async function undoContribution(goalId, contribution) {
  return api.contributions.undo(contribution.id);
}

// Ritmo de aporte mensual estimado (para proyecciones)
export function monthlyRate(goal, excedente, contributions, now = new Date()) {
  if (goal.contribution_mode === "percent_surplus") return contributionAmount(goal, excedente);
  if (goal.contribution_mode === "fixed") {
    const days = FREQ_DAYS[goal.contribution_frequency || "meses"];
    return ((goal.contribution_amount || 0) * 30) / days;
  }
  const cutoff = dateStrLocal(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 90));
  const cs = contributions.filter((c) => c.goal_id === goal.id && c.date >= cutoff);
  if (cs.length === 0) return null;
  return cs.reduce((s, c) => s + (c.amount || 0), 0) / 3;
}

export function projectedCompletion(goal, rate) {
  const remaining = (goal.target_amount || 0) - (goal.current_amount || 0);
  if (!rate || rate <= 0 || remaining <= 0) return null;
  const d = new Date();
  d.setMonth(d.getMonth() + Math.ceil(remaining / rate));
  return d;
}