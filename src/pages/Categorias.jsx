import React, { useEffect, useState } from "react";
import { api } from "@/api";
import { motion } from "framer-motion";
import { Plus, Trash2, Pencil } from "lucide-react";
import { formatCLP, parseAmount, isSameMonth } from "@/lib/format";
import CategoryIcon, { COLOR_PALETTE } from "@/components/CategoryIcon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/ui/numeric-input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export default function Categorias() {
  const [categories, setCategories] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editCat, setEditCat] = useState(null);
  const [form, setForm] = useState({ name: "", color: "#3b82f6", budget: "" });
  const [error, setError] = useState("");

  const load = async () => {
    const [cats, exps] = await Promise.all([
      api.categories.list(),
      api.expenses.list({ sort: "-date", limit: 300 }),
    ]);
    setCategories(cats);
    setExpenses(exps);
  };

  useEffect(() => { load(); }, []);

  const now = new Date();
  const byCat = {};
  expenses.forEach((e) => { byCat[e.category] = (byCat[e.category] || 0) + (e.amount || 0); });
  const byCatThisMonth = {};
  expenses
    .filter((e) => isSameMonth(e.date, now))
    .forEach((e) => { byCatThisMonth[e.category] = (byCatThisMonth[e.category] || 0) + (e.amount || 0); });

  const sortedCategories = [...categories]
    .filter((c) => c.name !== "Otros")
    .sort((a, b) => (byCatThisMonth[b.name] || 0) - (byCatThisMonth[a.name] || 0));

  const save = async () => {
    if (!form.name.trim()) return;
    const trimmed = form.name.trim();
    const dup = categories.find((c) => c.name.toLowerCase() === trimmed.toLowerCase() && c.id !== editCat?.id);
    if (dup) { setError("Ya existe una categoría con ese nombre"); return; }
    setError("");
    const payload = { name: trimmed, color: form.color, budget: parseAmount(form.budget) };
    if (editCat) {
      await api.categories.update(editCat.id, payload);
    } else {
      await api.categories.create(payload);
    }
    setDialogOpen(false);
    setEditCat(null);
    setForm({ name: "", color: "#3b82f6", budget: "" });
    load();
  };

  const remove = async (id) => {
    await api.categories.remove(id);
    load();
  };

  const openAdd = () => { setEditCat(null); setError(""); setForm({ name: "", color: "#3b82f6", budget: "" }); setDialogOpen(true); };
  const openEdit = (c) => { setEditCat(c); setError(""); setForm({ name: c.name, color: c.color, budget: c.budget ? String(c.budget) : "" }); setDialogOpen(true); };

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold font-heading text-slate-700">Categorías</h1>
          <p className="text-slate-400 text-sm mt-1">Administra tus categorías y presupuestos</p>
        </div>
        <Button onClick={openAdd} className="bg-emerald-500 hover:bg-emerald-600 rounded-xl gap-2">
          <Plus className="w-4 h-4" /> Nueva categoría
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        {sortedCategories.map((c, i) => {
          const spent = byCatThisMonth[c.name] || 0;
          const totalSpent = byCat[c.name] || 0;
          const count = expenses.filter((e) => e.category === c.name).length;
          const pct = c.budget ? Math.min(100, (spent / c.budget) * 100) : 0;
          const overBudget = c.budget && spent > c.budget;
          return (
            <motion.div
              key={c.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="group bg-[#f5f7fa] rounded-3xl p-6 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300"
            >
              <div className="flex items-center gap-3 mb-4">
                <CategoryIcon category={c.name} color={c.color} />
                <div className="flex-1">
                  <div className="font-semibold text-slate-700">{c.name}</div>
                  <div className="text-sm text-slate-400">{count} {count === 1 ? "gasto" : "gastos"}</div>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => openEdit(c)} className="text-slate-400 hover:text-sky-500 p-2 rounded-lg hover:bg-sky-50 transition-colors">
                    <Pencil className="w-4 h-4" />
                  </button>
                  <button onClick={() => remove(c.id)} className="text-slate-400 hover:text-red-500 p-2 rounded-lg hover:bg-red-50 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="flex items-end justify-between mb-2">
                <div>
                  <div className="text-xs text-slate-400">Gastado este mes</div>
                  <div className="text-xl font-bold font-heading tabular-nums text-slate-800">{formatCLP(spent)}</div>
                </div>
                {c.budget ? (
                  <div className="text-right">
                    <div className="text-xs text-slate-400">Presupuesto</div>
                    <div className="text-sm font-medium text-slate-600">{formatCLP(c.budget)}</div>
                  </div>
                ) : (
                  <div className="text-right">
                    <div className="text-xs text-slate-300">Sin presupuesto</div>
                  </div>
                )}
              </div>

              {c.budget ? (
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${pct}%`, background: overBudget ? "#ef4444" : c.color }}
                  />
                </div>
              ) : (
                <div className="h-2 bg-slate-100 rounded-full" />
              )}

              <div className="mt-3 pt-3 border-t border-slate-50 text-sm text-slate-400">
                Total histórico: <span className="font-medium text-slate-600">{formatCLP(totalSpent)}</span>
              </div>
            </motion.div>
          );
        })}
      </div>

      {categories.length === 0 && (
        <div className="text-center py-16">
          <div className="text-slate-400 mb-4">No tienes categorías creadas</div>
          <Button onClick={openAdd} className="bg-emerald-500 hover:bg-emerald-600 rounded-xl gap-2">
            <Plus className="w-4 h-4" /> Crear primera categoría
          </Button>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle className="text-xl">{editCat ? "Editar categoría" : "Nueva categoría"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label>Nombre</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Ej: Entretenimiento" />
              {error && <p className="text-xs text-red-500">{error}</p>}
            </div>
            <div className="space-y-1.5">
              <Label>Presupuesto mensual</Label>
              <NumericInput value={form.budget} onChange={(v) => setForm({ ...form, budget: v })} placeholder="0" />
            </div>
            <div className="space-y-2">
              <Label>Color</Label>
              <div className="flex flex-wrap gap-2">
                {COLOR_PALETTE.map((c) => (
                  <button
                    key={c}
                    onClick={() => setForm({ ...form, color: c })}
                    className={`w-7 h-7 rounded-full transition-all duration-200 ${form.color === c ? "ring-2 ring-offset-2 ring-slate-400 scale-110" : "hover:scale-110"}`}
                    style={{ background: c }}
                  />
                ))}
              </div>
            </div>
            <Button onClick={save} className="w-full bg-emerald-500 hover:bg-emerald-600 rounded-xl h-11">
              {editCat ? "Guardar cambios" : "Crear categoría"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}