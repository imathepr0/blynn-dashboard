import React, { useEffect, useState } from "react";
import { api } from "@/api";
import { motion } from "framer-motion";
import { Pencil, Trash2, CreditCard, Banknote, ArrowLeftRight } from "lucide-react";
import { formatCLP, formatDateShort, colorForCategory } from "@/lib/format";
import CategoryIcon from "@/components/CategoryIcon";
import NewExpenseDialog from "@/components/layout/NewExpenseDialog";

const PAYMENT_ICONS = { efectivo: Banknote, debito: CreditCard, credito: CreditCard, transferencia: ArrowLeftRight };
const PAYMENT_LABELS = { efectivo: "Efectivo", debito: "Débito", credito: "Crédito", transferencia: "Transferencia" };

function parseItems(desc) {
  if (!desc) return [];
  return desc.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
    const parts = l.split(" - ");
    return { name: parts[0] || l, price: parts.length > 1 ? parts.slice(1).join(" - ") : "" };
  });
}

export default function Boletas() {
  const [expenses, setExpenses] = useState([]);
  const [open, setOpen] = useState(false);
  const [editExpense, setEditExpense] = useState(null);

  const load = () => api.expenses.list({ sort: "-date", limit: 200 }).then(setExpenses);
  useEffect(() => { load(); }, []);

  const openEdit = (e) => { setEditExpense(e); setOpen(true); };
  const closeDialog = (v) => { setOpen(v); if (!v) setEditExpense(null); };
  const remove = async (id) => { await api.expenses.remove(id); load(); };

  return (
    <div className="max-w-6xl">
      <h1 className="text-3xl font-bold font-heading text-slate-700 mb-6">Boletas</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {expenses.map((e, i) => {
          const items = parseItems(e.description);
          const PayIcon = PAYMENT_ICONS[e.payment_method];
          return (
            <motion.div
              key={e.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05, type: "spring", stiffness: 260, damping: 20 }}
              className="group bg-[#f5f7fa] rounded-2xl shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all duration-300 overflow-hidden flex flex-col"
            >
              {/* Header strip */}
              <div className="h-1.5" style={{ background: e.color || colorForCategory(e.category) }} />

              <div className="p-5 flex flex-col flex-1">
                <div className="flex items-start justify-between mb-3">
                  <CategoryIcon category={e.category} color={e.color} size="sm" />
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => openEdit(e)} className="text-slate-400 hover:text-sky-500 p-1.5 rounded-lg hover:bg-sky-50 transition-colors">
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={() => remove(e.id)} className="text-slate-400 hover:text-red-500 p-1.5 rounded-lg hover:bg-red-50 transition-colors">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                <div className="font-semibold text-slate-800 text-lg leading-tight">{e.merchant}</div>
                <div className="text-sm text-slate-400 mb-3">{e.category} · {formatDateShort(e.date)}</div>

                {items.length > 0 && (
                  <div className="mb-3 py-2 border-y border-dashed border-slate-200 space-y-1">
                    {items.slice(0, 3).map((item, j) => (
                      <div key={j} className="flex items-center justify-between text-xs text-slate-500">
                        <span className="truncate">{item.name}</span>
                        {item.price && <span className="font-medium text-slate-600 ml-2 shrink-0">{item.price}</span>}
                      </div>
                    ))}
                    {items.length > 3 && <div className="text-xs text-slate-400 italic">+{items.length - 3} más...</div>}
                  </div>
                )}

                <div className="mt-auto flex items-end justify-between">
                  <div className="text-2xl font-bold font-heading tabular-nums text-slate-800">{formatCLP(e.amount)}</div>
                  {e.payment_method && (
                    <div className="flex items-center gap-1 text-xs text-slate-400 bg-slate-100 px-2 py-1 rounded-full">
                      {PayIcon && <PayIcon className="w-3 h-3" />}
                      {PAYMENT_LABELS[e.payment_method] || e.payment_method}
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
      {expenses.length === 0 && <div className="text-slate-400 text-center py-12">Sin boletas registradas</div>}

      <NewExpenseDialog open={open} onOpenChange={closeDialog} onCreated={load} editExpense={editExpense} />
    </div>
  );
}