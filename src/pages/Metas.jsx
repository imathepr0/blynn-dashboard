import React, { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/api";
import { Button } from "@/components/ui/button";
import GoalCard from "@/components/metas/GoalCard";
import GoalFormDialog from "@/components/metas/GoalFormDialog";
import AddContributionDialog from "@/components/metas/AddContributionDialog";
import { excedenteDelMes } from "@/lib/goalEngine";

export default function Metas() {
  const [goals, setGoals] = useState([]);
  const [incomes, setIncomes] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [contributions, setContributions] = useState([]);
  const [formOpen, setFormOpen] = useState(false);
  const [editGoal, setEditGoal] = useState(null);
  const [addFor, setAddFor] = useState(null);

  const load = () => {
    Promise.all([
      api.goals.list({ sort: "-created_date" }),
      api.incomes.list({ sort: "-date", limit: 200 }),
      api.expenses.list({ sort: "-date", limit: 300 }),
      api.contributions.list({ sort: "-date", limit: 200 }),
    ]).then(([gs, incs, exps, contribs]) => {
      setGoals(gs);
      setIncomes(incs);
      setExpenses(exps);
      setContributions(contribs);
    });
  };
  useEffect(() => { load(); }, []);

  const excedente = excedenteDelMes(incomes, expenses);

  const remove = async (g) => {
    // El servidor borra también los aportes de la meta.
    await api.goals.remove(g.id);
    load();
  };

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold font-heading text-slate-700">Metas</h1>
        <Button onClick={() => { setEditGoal(null); setFormOpen(true); }} className="bg-emerald-500 hover:bg-emerald-600 rounded-xl gap-2">
          <Plus className="w-4 h-4" /> Nueva meta
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        {goals.map((g) => (
          <GoalCard
            key={g.id}
            goal={g}
            excedente={excedente}
            contributions={contributions}
            onEdit={(goal) => { setEditGoal(goal); setFormOpen(true); }}
            onDelete={remove}
            onAdd={setAddFor}
          />
        ))}
        {goals.length === 0 && <div className="text-slate-400">Aún no tienes metas. ¡Crea una!</div>}
      </div>

      <GoalFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        editGoal={editGoal}
        goals={goals}
        excedente={excedente}
        onSaved={load}
      />
      <AddContributionDialog
        goal={addFor}
        onOpenChange={(v) => { if (!v) setAddFor(null); }}
        onDone={load}
      />
    </div>
  );
}