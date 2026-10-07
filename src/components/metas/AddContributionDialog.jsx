import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { NumericInput } from "@/components/ui/numeric-input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { parseAmount, formatCLP } from "@/lib/format";
import { addManualContribution } from "@/lib/goalEngine";

export default function AddContributionDialog({ goal, onOpenChange, onDone }) {
  const [amount, setAmount] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (goal) setAmount("");
  }, [goal]);

  const save = async () => {
    if (!goal || parseAmount(amount) <= 0) return;
    setSaving(true);
    try {
      await addManualContribution(goal, parseAmount(amount));
      setSaving(false);
      onOpenChange(false);
      onDone?.();
    } catch {
      setSaving(false);
    }
  };

  return (
    <Dialog open={!!goal} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm rounded-2xl">
        <DialogHeader><DialogTitle className="text-xl">Aportar a «{goal?.title}»</DialogTitle></DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="text-sm text-slate-400">
            Llevas {formatCLP(goal?.current_amount || 0)} de {formatCLP(goal?.target_amount || 0)}
          </div>
          <div className="space-y-1.5">
            <Label>Monto a aportar</Label>
            <NumericInput value={amount} onChange={setAmount} placeholder="0" autoFocus />
          </div>
          <Button onClick={save} disabled={saving || parseAmount(amount) <= 0} className="w-full bg-emerald-500 hover:bg-emerald-600 rounded-xl h-11">
            {saving ? "Guardando..." : "Aportar"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}