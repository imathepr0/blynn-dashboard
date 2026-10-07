import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/api";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, Trash2, Pencil, ChevronDown } from "lucide-react";
import { formatCLP, formatDateShort, dateParts } from "@/lib/format";
import CategoryIcon from "@/components/CategoryIcon";
import NewExpenseDialog from "@/components/layout/NewExpenseDialog";
import { Button } from "@/components/ui/button";

const MONTHS = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

function groupByMonth(expenses) {
  const groups = {};
  expenses.forEach((e) => {
    const p = dateParts(e.date);
    const key = `${p.y}-${String(p.m).padStart(2, "0")}`;
    if (!groups[key]) groups[key] = { label: `${MONTHS[p.m]} ${p.y}`, items: [] };
    groups[key].items.push(e);
  });
  return Object.values(groups);
}

function parseDescription(desc) {
  if (!desc) return [];
  return desc.split("\n").map((l) => l.trim()).filter(Boolean);
}

export default function Gastos() {
  const [expenses, setExpenses] = useState([]);
  const [open, setOpen] = useState(false);
  const [editExpense, setEditExpense] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const load = () => api.expenses.list({ sort: "-date", limit: 200 }).then(setExpenses);
  useEffect(() => { load(); }, []);

  useEffect(() => {
    const id = searchParams.get("expense");
    if (id && expenses.some((e) => e.id === id)) {
      setExpandedId(id);
    }
  }, [searchParams, expenses]);

  const toggleExpand = (id) => {
    const newId = expandedId === id ? null : id;
    setExpandedId(newId);
    if (newId) setSearchParams({ expense: newId });
    else setSearchParams({});
  };

  const remove = async (id) => {
    await api.expenses.remove(id);
    load();
  };

  const openEdit = (e) => {
    setEditExpense(e);
    setOpen(true);
  };

  const closeDialog = (v) => {
    setOpen(v);
    if (!v) setEditExpense(null);
  };

  const groups = groupByMonth(expenses);

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold font-heading text-slate-700">Gastos</h1>
        <Button onClick={() => { setEditExpense(null); setOpen(true); }} className="bg-emerald-500 hover:bg-emerald-600 rounded-xl gap-2">
          <Plus className="w-4 h-4" /> Nuevo
        </Button>
      </div>

      {groups.map((group) => (
        <div key={group.label} className="mb-6">
          <h2 className="text-lg font-semibold font-heading text-slate-500 mb-3 px-1">{group.label}</h2>
          <div className="bg-[#f5f7fa] rounded-3xl p-4 shadow-sm divide-y divide-slate-100">
            {group.items.map((e) => {
              const isExpanded = expandedId === e.id;
              const descLines = parseDescription(e.description);
              return (
                <div key={e.id}>
                  <div
                    className={`flex items-center py-4 px-3 group hover:bg-slate-50 rounded-2xl transition-colors cursor-pointer ${isExpanded ? "bg-slate-50" : ""}`}
                    onClick={() => toggleExpand(e.id)}
                  >
                    <CategoryIcon category={e.category} color={e.color} />
                    <div className="flex-1 min-w-0 ml-4">
                      <div className="font-semibold text-slate-800 flex items-center gap-2">
                        {e.merchant}
                        {e.is_recurring && e.recurring_active && (
                          <span className="text-[10px] bg-sky-100 text-sky-600 px-2 py-0.5 rounded-full font-medium whitespace-nowrap">Recurrente</span>
                        )}
                      </div>
                      <div className="text-sm text-slate-400">{e.category} · {formatDateShort(e.date)}</div>
                    </div>
                    <div className="text-right mr-4">
                      <div className="font-bold font-heading tabular-nums text-slate-800">{formatCLP(e.amount)}</div>
                      {e.payment_method && <div className="text-sm text-slate-400 capitalize">{e.payment_method}</div>}
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(ev) => { ev.stopPropagation(); openEdit(e); }}
                        className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-sky-500 transition-all p-2"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(ev) => { ev.stopPropagation(); remove(e.id); }}
                        className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-500 transition-all p-2"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                      <ChevronDown className={`w-4 h-4 text-slate-300 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                    </div>
                  </div>
                  <AnimatePresence>
                    {isExpanded && descLines.length > 0 && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="px-6 pb-4 pt-1 ml-14">
                          <div className="text-xs font-medium text-slate-400 mb-2 uppercase tracking-wide">Detalle</div>
                          <div className="space-y-1">
                            {descLines.map((line, i) => {
                              const parts = line.split(" - ");
                              return (
                                <div key={i} className="flex items-center justify-between text-sm text-slate-600 py-1.5 border-b border-slate-50 last:border-0">
                                  <span>{parts[0] || line}</span>
                                  {parts.length > 1 && <span className="font-medium text-slate-700">{parts.slice(1).join(" - ")}</span>}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        </div>
      ))}
      {expenses.length === 0 && <div className="text-slate-400 text-center py-12">Sin gastos aún</div>}

      <NewExpenseDialog open={open} onOpenChange={closeDialog} onCreated={load} editExpense={editExpense} />
    </div>
  );
}