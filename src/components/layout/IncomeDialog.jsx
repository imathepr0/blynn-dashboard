import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { api } from "@/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/ui/numeric-input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { COLOR_PALETTE } from "@/components/CategoryIcon";
import { parseAmount, dateStrLocal } from "@/lib/format";

const TODAY = dateStrLocal(new Date());

const INCOME_TYPES = [
  { value: "sueldo", label: "Sueldo" },
  { value: "bono", label: "Bono" },
  { value: "transferencia", label: "Transferencia" },
  { value: "efectivo", label: "Efectivo" },
  { value: "otros", label: "Otros" },
];

export default function IncomeDialog({ open, onOpenChange, onCreated, editIncome }) {
  const [form, setForm] = useState({ source: "", amount: "", date: TODAY, type: "otros", description: "", color: "#22c55e" });
  const [saving, setSaving] = useState(false);
  const [dateError, setDateError] = useState(false);

  useEffect(() => {
    if (open) {
      if (editIncome) {
        setForm({
          source: editIncome.source || "",
          amount: editIncome.amount ? String(editIncome.amount) : "",
          date: editIncome.date || TODAY,
          type: editIncome.type || "otros",
          description: editIncome.description || "",
          color: editIncome.color || "#22c55e",
        });
      } else {
        setForm({ source: "", amount: "", date: TODAY, type: "otros", description: "", color: "#22c55e" });
      }
      setDateError(false);
    }
  }, [open, editIncome]);

  const handleDateChange = (val) => {
    if (val > TODAY) {
      setDateError(true);
      return;
    }
    setDateError(false);
    setForm({ ...form, date: val });
  };

  const submit = async () => {
    if (!form.source || !form.amount) return;
    setSaving(true);
    const payload = { ...form, amount: parseAmount(form.amount) };
    if (editIncome) {
      await api.incomes.update(editIncome.id, payload);
    } else {
      await api.incomes.create(payload);
    }
    setSaving(false);
    onOpenChange(false);
    onCreated?.();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onOpenChange(false); }}>
      <DialogContent className="sm:max-w-md rounded-2xl">
        <DialogHeader>
          <DialogTitle className="text-xl">{editIncome ? "Editar ingreso" : "Nuevo ingreso"}</DialogTitle>
        </DialogHeader>

        <motion.div key="manual" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label>Origen</Label>
            <Input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} placeholder="Ej: Sueldo Empresa XYZ" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Monto</Label>
              <NumericInput value={form.amount} onChange={(v) => setForm({ ...form, amount: v })} placeholder="0" />
            </div>
            <div className="space-y-1.5">
              <Label>Fecha</Label>
              <Input type="date" max={TODAY} value={form.date} onChange={(e) => handleDateChange(e.target.value)} />
              {dateError && <p className="text-xs text-red-500">No puedes poner fechas futuras</p>}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Tipo</Label>
              <Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {INCOME_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Descripción <span className="text-slate-400 font-normal">(opcional)</span></Label>
            <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Contexto o detalle del ingreso" rows={2} />
          </div>
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
          <Button onClick={submit} disabled={saving} className="w-full bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl h-11">
            {saving ? "Guardando..." : editIncome ? "Guardar cambios" : "Guardar ingreso"}
          </Button>
        </motion.div>
      </DialogContent>
    </Dialog>
  );
}