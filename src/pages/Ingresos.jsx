import React, { useEffect, useState } from "react";
import { api } from "@/api";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, Trash2, Pencil, ChevronDown } from "lucide-react";
import { formatCLP, formatDateShort, dateParts } from "@/lib/format";
import IncomeDialog from "@/components/layout/IncomeDialog";
import { Button } from "@/components/ui/button";
import { hexToRgba } from "@/components/CategoryIcon";
import { Wallet, Gift, ArrowLeftRight, Banknote, Package } from "lucide-react";

const MONTHS = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

const INCOME_ICONS = { sueldo: Wallet, bono: Gift, transferencia: ArrowLeftRight, efectivo: Banknote, otros: Package };
const INCOME_COLORS = { sueldo: "#22c55e", bono: "#8b5cf6", transferencia: "#38bdf8", efectivo: "#f59e0b", otros: "#94a3b8" };
const TYPE_LABELS = { sueldo: "Sueldo", bono: "Bono", transferencia: "Transferencia", efectivo: "Efectivo", otros: "Otros" };

function groupByMonth(incomes) {
  const groups = {};
  incomes.forEach((i) => {
    const p = dateParts(i.date);
    const key = `${p.y}-${String(p.m).padStart(2, "0")}`;
    if (!groups[key]) groups[key] = { label: `${MONTHS[p.m]} ${p.y}`, items: [] };
    groups[key].items.push(i);
  });
  return Object.values(groups);
}

export default function Ingresos() {
  const [incomes, setIncomes] = useState([]);
  const [open, setOpen] = useState(false);
  const [editIncome, setEditIncome] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  const load = () => api.incomes.list({ sort: "-date", limit: 200 }).then(setIncomes);
  useEffect(() => { load(); }, []);

  const remove = async (id) => {
    await api.incomes.remove(id);
    load();
  };

  const openEdit = (i) => { setEditIncome(i); setOpen(true); };
  const closeDialog = (v) => { setOpen(v); if (!v) setEditIncome(null); };

  const groups = groupByMonth(incomes);
  const total = incomes.reduce((s, i) => s + (i.amount || 0), 0);

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold font-heading text-slate-700">Ingresos</h1>
          <p className="text-slate-400 text-sm mt-1">Total registrado: {formatCLP(total)}</p>
        </div>
        <Button onClick={() => { setEditIncome(null); setOpen(true); }} className="bg-emerald-500 hover:bg-emerald-600 rounded-xl gap-2">
          <Plus className="w-4 h-4" /> Nuevo ingreso
        </Button>
      </div>

      {groups.map((group) => (
        <div key={group.label} className="mb-6">
          <h2 className="text-lg font-semibold font-heading text-slate-500 mb-3 px-1">{group.label}</h2>
          <div className="bg-[#f5f7fa] rounded-3xl p-4 shadow-sm divide-y divide-slate-100">
            {group.items.map((i) => {
              const Icon = INCOME_ICONS[i.type] || Package;
              const color = i.color || INCOME_COLORS[i.type] || "#94a3b8";
              const isExpanded = expandedId === i.id;
              return (
                <div key={i.id}>
                  <div
                    className={`flex items-center py-4 px-3 group hover:bg-slate-50 rounded-2xl transition-colors cursor-pointer ${isExpanded ? "bg-slate-50" : ""}`}
                    onClick={() => setExpandedId(isExpanded ? null : i.id)}
                  >
                    <span className="w-10 h-10 rounded-xl shrink-0 flex items-center justify-center border" style={{ background: hexToRgba(color, 0.12), borderColor: hexToRgba(color, 0.3), color }}>
                      <Icon className="w-5 h-5" />
                    </span>
                    <div className="flex-1 min-w-0 ml-4">
                      <div className="font-semibold text-slate-800">{i.source}</div>
                      <div className="text-sm text-slate-400">{TYPE_LABELS[i.type] || "Otros"} · {formatDateShort(i.date)}</div>
                    </div>
                    <div className="font-bold font-heading tabular-nums text-emerald-600 mr-4">{formatCLP(i.amount)}</div>
                    <div className="flex items-center gap-1">
                      <button onClick={(ev) => { ev.stopPropagation(); openEdit(i); }} className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-sky-500 transition-all p-2">
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button onClick={(ev) => { ev.stopPropagation(); remove(i.id); }} className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-500 transition-all p-2">
                        <Trash2 className="w-4 h-4" />
                      </button>
                      <ChevronDown className={`w-4 h-4 text-slate-300 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                    </div>
                  </div>
                  <AnimatePresence>
                    {isExpanded && i.description && (
                      <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                        <div className="px-6 pb-4 pt-1 ml-14">
                          <div className="text-xs font-medium text-slate-400 mb-2 uppercase tracking-wide">Descripción</div>
                          <p className="text-sm text-slate-600">{i.description}</p>
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
      {incomes.length === 0 && <div className="text-slate-400 text-center py-12">Sin ingresos registrados</div>}

      <IncomeDialog open={open} onOpenChange={closeDialog} onCreated={load} editIncome={editIncome} />
    </div>
  );
}