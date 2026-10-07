import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Hand, Percent, Repeat, Check, Info } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/ui/numeric-input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/api";
import { parseAmount, formatCLP, dateStrLocal } from "@/lib/format";
import { nextContributionDate } from "@/lib/goalEngine";
import { COLOR_PALETTE } from "@/components/CategoryIcon";

const MODES = [
  { id: "manual", icon: Hand, title: "Aportar a mano", desc: "Tú decides cuándo y cuánto aportar. Sin automatización." },
  { id: "percent_surplus", icon: Percent, title: "% del excedente", desc: "Cada mes se aparta un porcentaje del dinero que te sobre (tus ingresos menos tus gastos del mes)." },
  { id: "fixed", icon: Repeat, title: "Monto fijo automático", desc: "Se aporta un monto fijo cada cierto tiempo, de forma automática." },
];
const FREQS = [
  { value: "dias", label: "Cada día" },
  { value: "semanas", label: "Cada semana" },
  { value: "meses", label: "Cada mes" },
];

export default function GoalFormDialog({ open, onOpenChange, editGoal, goals = [], excedente = 0, onSaved }) {
  const [form, setForm] = useState({ title: "", target_amount: "", current_amount: "", deadline: "", color: "#22c55e" });
  const [mode, setMode] = useState("manual");
  const [percent, setPercent] = useState(20);
  const [fixedAmount, setFixedAmount] = useState("");
  const [freq, setFreq] = useState("meses");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      if (editGoal) {
        setForm({
          title: editGoal.title || "",
          target_amount: editGoal.target_amount ? String(editGoal.target_amount) : "",
          current_amount: editGoal.current_amount ? String(editGoal.current_amount) : "",
          deadline: editGoal.deadline || "",
          color: editGoal.color || "#22c55e",
        });
        setMode(editGoal.contribution_mode || "manual");
        setPercent(editGoal.contribution_percent || 20);
        setFixedAmount(editGoal.contribution_amount ? String(editGoal.contribution_amount) : "");
        setFreq(editGoal.contribution_frequency || "meses");
      } else {
        setForm({ title: "", target_amount: "", current_amount: "", deadline: "", color: "#22c55e" });
        setMode("manual");
        setPercent(20);
        setFixedAmount("");
        setFreq("meses");
      }
    }
  }, [open, editGoal]);

  // Tope: la suma de % de todas las metas con porcentaje no puede pasar de 100
  const maxPercent = Math.max(1, 100 - goals
    .filter((g) => g.id !== editGoal?.id && g.contribution_mode === "percent_surplus")
    .reduce((s, g) => s + (g.contribution_percent || 0), 0));

  const selectMode = (id) => {
    setMode(id);
    if (id === "percent_surplus") setPercent((p) => Math.min(p, maxPercent));
  };

  const save = async () => {
    if (!form.title || !form.target_amount) return;
    if (mode === "fixed" && parseAmount(fixedAmount) <= 0) return;
    setSaving(true);
    const effectiveFreq = mode === "fixed" ? freq : "meses";
    const payload = {
      title: form.title,
      target_amount: parseAmount(form.target_amount),
      current_amount: parseAmount(form.current_amount),
      deadline: form.deadline || undefined,
      color: form.color,
      contribution_mode: mode,
      contribution_percent: mode === "percent_surplus" ? Math.min(percent, maxPercent) : undefined,
      contribution_amount: mode === "fixed" ? parseAmount(fixedAmount) : undefined,
      contribution_frequency: mode === "manual" ? undefined : effectiveFreq,
      next_contribution_date: mode !== "manual" ? dateStrLocal(nextContributionDate({ contribution_frequency: effectiveFreq })) : undefined,
    };
    try {
      if (editGoal) await api.goals.update(editGoal.id, payload);
      else await api.goals.create(payload);
      setSaving(false);
      onOpenChange(false);
      onSaved?.();
    } catch {
      setSaving(false);
    }
  };

  const valid = form.title && form.target_amount && (mode !== "fixed" || parseAmount(fixedAmount) > 0);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md rounded-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="text-xl">{editGoal ? "Editar meta" : "Nueva meta"}</DialogTitle></DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="space-y-1.5"><Label>Nombre</Label><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Ej: Vacaciones" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5"><Label>Objetivo</Label><NumericInput value={form.target_amount} onChange={(v) => setForm({ ...form, target_amount: v })} /></div>
            <div className="space-y-1.5"><Label>Ahorrado</Label><NumericInput value={form.current_amount} onChange={(v) => setForm({ ...form, current_amount: v })} /></div>
          </div>
          <div className="space-y-1.5"><Label>Fecha límite <span className="text-slate-400 font-normal">(opcional)</span></Label><Input type="date" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} /></div>
          <div className="space-y-2">
            <Label>Color</Label>
            <div className="flex flex-wrap gap-2">
              {COLOR_PALETTE.map((c) => (
                <button
                  key={c}
                  onClick={() => setForm({ ...form, color: c })}
                  className={`w-6 h-6 rounded-full transition-all duration-200 ${form.color === c ? "ring-2 ring-offset-2 ring-slate-400 scale-110" : "hover:scale-110"}`}
                  style={{ background: c }}
                />
              ))}
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100">
            <Label className="block mb-1">¿Cómo quieres aportar a esta meta?</Label>
            <p className="text-xs text-slate-400 mb-3">Solo una opción automática. Aportar a mano siempre estará disponible.</p>
            <div className="space-y-2">
              {MODES.map((opt) => {
                const selected = mode === opt.id;
                const Icon = opt.icon;
                return (
                  <button
                    key={opt.id}
                    onClick={() => selectMode(opt.id)}
                    className={`w-full relative flex items-start gap-3 p-3 rounded-2xl border-2 text-left transition-all duration-200 ${selected ? "border-emerald-500 bg-emerald-50" : "border-slate-200 hover:border-emerald-300 hover:bg-slate-50"}`}
                  >
                    {selected && (
                      <span className="absolute top-2.5 right-2.5 w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center">
                        <Check className="w-3 h-3 text-white" />
                      </span>
                    )}
                    <span className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${selected ? "bg-emerald-100 text-emerald-600" : "bg-slate-100 text-slate-500"}`}>
                      <Icon className="w-4 h-4" />
                    </span>
                    <div>
                      <div className={`text-sm font-semibold ${selected ? "text-emerald-700" : "text-slate-700"}`}>{opt.title}</div>
                      <div className="text-xs text-slate-400 mt-0.5">{opt.desc}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <AnimatePresence mode="wait">
            {mode === "percent_surplus" && (
              <motion.div key="percent" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-700">{percent}% del excedente</span>
                    <span className="text-sm text-emerald-600 font-bold font-heading tabular-nums">{percent}%</span>
                  </div>
                  <Slider value={[percent]} onValueChange={(v) => setPercent(v[0])} min={1} max={maxPercent} step={1} />
                  <p className="text-xs text-slate-400 flex items-start gap-1.5">
                    <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    Con tu excedente actual ({formatCLP(excedente)}) esto serían ≈ {formatCLP(Math.round((excedente * percent) / 100))} este mes.
                  </p>
                  {maxPercent < 100 && (
                    <p className="text-xs text-amber-600">Puedes usar hasta {maxPercent}%: el resto ya está asignado a otras metas.</p>
                  )}
                </div>
              </motion.div>
            )}
            {mode === "fixed" && (
              <motion.div key="fixed" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label>Monto por aporte</Label>
                    <NumericInput value={fixedAmount} onChange={setFixedAmount} placeholder="0" />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Frecuencia</Label>
                    <Select value={freq} onValueChange={setFreq}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {FREQS.map((f) => <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <Button onClick={save} disabled={saving || !valid} className="w-full bg-emerald-500 hover:bg-emerald-600 rounded-xl h-11">
            {saving ? "Guardando..." : editGoal ? "Guardar cambios" : "Guardar meta"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}