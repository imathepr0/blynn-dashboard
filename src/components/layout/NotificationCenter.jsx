import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bell, X, Check, PiggyBank, ChevronDown } from "lucide-react";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { formatCLP } from "@/lib/format";

export default function NotificationCenter({ notifications = [], onDismiss, pending = [], onApprove, onReject }) {
  const [seen, setSeen] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [busy, setBusy] = useState(false);
  const total = notifications.length + pending.length;
  const showBadge = total > 0 && !seen;

  const handleOpenChange = (v) => {
    if (v) setSeen(true);
  };

  const handleApprove = async (p, i) => {
    setBusy(true);
    try {
      await onApprove(p);
      setExpanded(null);
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async (p) => {
    setBusy(true);
    try {
      await onReject(p);
      setExpanded(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Popover onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <button className="w-11 h-11 rounded-full bg-[#f5f7fa] hover:bg-sky-50 hover:text-sky-500 hover:shadow-md hover:scale-110 flex items-center justify-center text-slate-500 transition-all duration-300 shadow-sm relative">
          <Bell className="w-5 h-5" />
          {showBadge && <span className="absolute top-2 right-2.5 w-2 h-2 bg-red-500 rounded-full ring-2 ring-white" />}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="p-4 border-b border-slate-100">
          <h3 className="font-semibold font-heading text-slate-700">Notificaciones</h3>
        </div>
        <div className="max-h-80 overflow-y-auto">
          {total === 0 ? (
            <div className="p-6 text-center text-sm text-slate-400">No hay notificaciones</div>
          ) : (
            <>
              {pending.map((p, i) => (
                <div key={`pending-${p.goal.id}`} className="border-b border-slate-50 last:border-0">
                  <button
                    onClick={() => setExpanded(expanded === i ? null : i)}
                    className="w-full text-left flex items-start gap-3 p-3 hover:bg-slate-50 transition-colors"
                  >
                    <span className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 bg-emerald-50 text-emerald-500">
                      <PiggyBank className="w-4 h-4" />
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-slate-700">Aporte a «{p.goal.title}»</div>
                      <div className="text-xs text-slate-400">{formatCLP(p.amount)} · aporte automático</div>
                    </div>
                    <ChevronDown className={`w-4 h-4 text-slate-300 mt-1 transition-transform ${expanded === i ? "rotate-180" : ""}`} />
                  </button>
                  <AnimatePresence>
                    {expanded === i && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="px-3 pb-3 flex items-center justify-between">
                          <span className="text-xs font-medium text-slate-500">¿Apruebas este aporte?</span>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleApprove(p, i)}
                              disabled={busy}
                              className="w-8 h-8 rounded-full bg-emerald-50 text-emerald-600 hover:bg-emerald-100 flex items-center justify-center transition-colors disabled:opacity-50"
                              title="Aprobar"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleReject(p)}
                              disabled={busy}
                              className="w-8 h-8 rounded-full bg-red-50 text-red-500 hover:bg-red-100 flex items-center justify-center transition-colors disabled:opacity-50"
                              title="Rechazar"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              ))}
              {notifications.map((n) => {
                const Icon = n.icon;
                return (
                  <div key={n.id} className="relative flex items-start gap-3 p-3 pr-9 hover:bg-slate-50 border-b border-slate-50 last:border-0">
                    <span className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${n.color}15`, color: n.color }}>
                      <Icon className="w-4 h-4" />
                    </span>
                    <div>
                      <div className="text-sm font-medium text-slate-700">{n.title}</div>
                      <div className="text-xs text-slate-400">{n.desc}</div>
                      {n.action && (
                        <button
                          onClick={n.action.onClick}
                          className="mt-1.5 text-xs font-semibold text-sky-600 hover:text-sky-700 transition-colors"
                        >
                          {n.action.label}
                        </button>
                      )}
                    </div>
                    <button
                      onClick={() => onDismiss(n.id)}
                      className="absolute top-2 right-2 w-6 h-6 rounded-full text-slate-300 hover:text-slate-500 hover:bg-slate-100 flex items-center justify-center transition-colors"
                      title="Descartar"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })}
            </>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}