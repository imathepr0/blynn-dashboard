import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/ui/numeric-input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { PencilLine, FileUp, ArrowLeft, CheckCircle2, Repeat, AlertTriangle, RefreshCw } from "lucide-react";
import DescriptionGrid from "@/components/layout/DescriptionGrid";
import ProcessingScreen from "@/components/layout/ProcessingScreen";
import { COLOR_PALETTE, randomColor } from "@/components/CategoryIcon";
import { processBoletaFile, describirErrorDeEscaneo, normalizeDate, ESCANEO_DISPONIBLE } from "@/lib/boletasScan";
import { parseAmount, dateStrLocal } from "@/lib/format";

const DEFAULT_CATS = ["Alimentación", "Transporte", "Hogar", "Suscripciones", "Salud", "Ropa", "Arriendo", "Educación", "Entretenimiento", "Transferencias", "Tecnología", "Otros"];
const TODAY = dateStrLocal(new Date());

const PASO_INICIAL = ESCANEO_DISPONIBLE ? "choose" : "manual";

export default function NewExpenseDialog({ open, onOpenChange, onCreated, editExpense }) {
  // Sin escaneo disponible no hay nada que elegir: se va directo al formulario.
  const [step, setStep] = useState(PASO_INICIAL);
  const [cats, setCats] = useState(DEFAULT_CATS);
  const [form, setForm] = useState({
    merchant: "", description: "", amount: "", category: "Alimentación",
    date: TODAY, payment_method: "", color: "#3b82f6", is_recurring: false, recurring_active: false,
  });
  const [saving, setSaving] = useState(false);
  const [docStatus, setDocStatus] = useState("");
  const [lowConfidence, setLowConfidence] = useState(null);
  const [lowMessage, setLowMessage] = useState("");
  const [scanError, setScanError] = useState(null);
  const [partial, setPartial] = useState(false);
  const [dateError, setDateError] = useState(false);
  const [scanDone, setScanDone] = useState(false);
  const pendingScan = useRef(null);
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (open) {
      setDocStatus("");
      setLowConfidence(null);
      setPartial(false);
      setDateError(false);
      setScanDone(false);
      setScanError(null);
      setLowMessage("");
      if (editExpense) {
        setStep("manual");
        setForm({
          merchant: editExpense.merchant || "",
          description: editExpense.description || "",
          amount: editExpense.amount ? String(editExpense.amount) : "",
          category: editExpense.category || "Alimentación",
          date: editExpense.date || TODAY,
          payment_method: editExpense.payment_method || "",
          color: editExpense.color || "#3b82f6",
          is_recurring: editExpense.is_recurring || false,
          recurring_active: editExpense.recurring_active || false,
        });
      } else {
        setStep(PASO_INICIAL);
        setForm({
          merchant: "", description: "", amount: "", category: "Alimentación",
          date: TODAY, payment_method: "", color: "#3b82f6", is_recurring: false, recurring_active: false,
        });
      }
    }
  }, [open, editExpense]);

  useEffect(() => {
    if (open) {
      api.categories.list().then((c) => {
        if (c?.length) setCats(c.map((x) => x.name));
      });
    }
  }, [open]);

  const handleDateChange = (val) => {
    if (val > TODAY) {
      setDateError(true);
      return;
    }
    setDateError(false);
    setForm({ ...form, date: val });
  };

  const handleCategoryChange = (v) => {
    if (v !== "Suscripciones") {
      setForm({ ...form, category: v, is_recurring: false, recurring_active: false });
    } else {
      setForm({ ...form, category: v });
    }
  };

  const submit = async () => {
    if (!form.merchant || !form.amount) return;
    setSaving(true);
    const payload = { ...form, amount: parseAmount(form.amount) };
    if (!payload.payment_method) delete payload.payment_method;
    if (editExpense) {
      await api.expenses.update(editExpense.id, payload);
    } else {
      await api.expenses.create(payload);
    }
    setSaving(false);
    onOpenChange(false);
    onCreated?.();
  };

  const handleFile = async (file, source = "file") => {
    if (!file) return;
    setScanError(null);
    setDocStatus("processing");
    setLowConfidence(null);
    setLowMessage("");
    setScanDone(false);
    try {
      const res = await processBoletaFile(file, cats, { source });
      pendingScan.current = res;
      setScanDone(true);
    } catch (e) {
      // Se vuelve a las opciones CON el motivo, para reintentar o ingresar a mano.
      setScanError(describirErrorDeEscaneo(e));
      setDocStatus("");
      setStep("choose");
    }
  };

  const applyScanToForm = (data, isPartial) => {
    setForm((prev) => ({
      ...prev,
      ...(data?.merchant ? { merchant: String(data.merchant) } : {}),
      ...(data?.amount ? { amount: String(data.amount) } : {}),
      ...(data?.date ? { date: normalizeDate(data.date) } : {}),
      ...(data?.description ? { description: data.description } : {}),
      ...(data?.category ? { category: data.category } : {}),
      ...(data?.payment_method ? { payment_method: data.payment_method } : {}),
      color: randomColor(),
    }));
    setPartial(isPartial);
    setLowConfidence(null);
    setDocStatus("done");
    setStep("manual");
  };

  const finishScan = () => {
    const res = pendingScan.current;
    // Nunca se guarda automáticamente: incluso con buena lectura el usuario
    // revisa y confirma los datos en el formulario antes de guardar.
    if (res?.confident) {
      applyScanToForm(res.prefill, false);
      navigate("/boletas");
      return;
    }
    setLowMessage(res?.mensaje || "");
    setLowConfidence(res?.prefill);
  };

  const retryCapture = () => {
    setLowConfidence(null);
    setLowMessage("");
    setScanDone(false);
    setDocStatus("");
    setStep("choose");
  };

  const openFilePicker = () => {
    setScanError(null);
    setStep("document");
    // The input stays mounted so the browser opens the picker during the user's click.
    fileInputRef.current?.click();
  };

  const manualFromScan = () => {
    applyScanToForm(lowConfidence, true);
    navigate("/boletas");
  };

  const OPTIONS = [
    { id: "manual", icon: PencilLine, title: "Ingresar manualmente", desc: "Completa los datos tú mismo" },
    { id: "document", icon: FileUp, title: "Subir foto de boleta", desc: "Elige la foto de tu boleta desde tu dispositivo" },
  ];

  return (
    <>
      <Dialog open={open} onOpenChange={(v) => { if (!v) onOpenChange(false); }}>
        <DialogContent className="sm:max-w-md rounded-2xl">
          <DialogHeader>
            <div className="flex items-center gap-3">
              {step !== "choose" && !editExpense && ESCANEO_DISPONIBLE && (
                <button onClick={() => setStep("choose")} className="text-slate-400 hover:text-slate-600">
                  <ArrowLeft className="w-5 h-5" />
                </button>
              )}
              <DialogTitle className="text-xl">
                {editExpense ? "Editar gasto" : step === "choose" ? "Nueva boleta" : step === "manual" ? "Ingresar manualmente" : "Subir foto de boleta"}
              </DialogTitle>
            </div>
          </DialogHeader>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) handleFile(f); }}
          />

          <AnimatePresence mode="wait">
            {step === "choose" && (
              <motion.div key="choose" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-3 pt-2">
                {scanError && (
                  <div role="alert" className="flex items-start gap-2 text-sm text-red-600 bg-red-50 rounded-xl px-3 py-2">
                    <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
                    <span>{scanError}</span>
                  </div>
                )}
                {OPTIONS.map((opt) => {
                  const Icon = opt.icon;
                  return (
                    <button
                      key={opt.id}
                      onClick={() => {
                        if (opt.id === "document") openFilePicker();
                        else setStep("manual");
                      }}
                      className="w-full flex items-center gap-4 p-4 rounded-2xl border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-all duration-200 group text-left"
                    >
                      <span className="w-11 h-11 rounded-xl bg-slate-100 group-hover:bg-slate-200 flex items-center justify-center text-slate-600 group-hover:text-slate-800 transition-all duration-200">
                        <Icon className="w-5 h-5" />
                      </span>
                      <div>
                        <div className="font-semibold text-slate-800">{opt.title}</div>
                        <div className="text-sm text-slate-400">{opt.desc}</div>
                      </div>
                    </button>
                  );
                })}
              </motion.div>
            )}

            {step === "document" && (
              <motion.div key="document" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="py-8">
                {docStatus === "processing" ? (
                  <div className="relative">
                    <ProcessingScreen type="boleta" done={scanDone} onComplete={finishScan} />
                    {lowConfidence && (
                      <motion.div
                        className="absolute inset-0 z-10 flex items-center justify-center"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.25 }}
                      >
                        <div className="absolute inset-0 bg-[#f5f7fa]/80 backdrop-blur-[2px] rounded-xl" />
                        <motion.div
                          className="relative bg-white rounded-2xl shadow-xl border border-slate-100 p-5 mx-3 text-center max-w-xs"
                          initial={{ scale: 0.9, y: 12 }}
                          animate={{ scale: 1, y: 0 }}
                          transition={{ type: "spring", stiffness: 300, damping: 20 }}
                        >
                          <div className="w-12 h-12 rounded-full bg-amber-50 flex items-center justify-center mx-auto mb-3">
                            <AlertTriangle className="w-6 h-6 text-amber-500" />
                          </div>
                          <p className="font-semibold text-slate-800 mb-1">No pudimos leer tu boleta con certeza</p>
                          <p className="text-sm text-slate-400 mb-4">{lowMessage || "¿Cómo quieres continuar?"}</p>
                          <div className="flex flex-col gap-2">
                            <Button variant="outline" onClick={retryCapture} className="rounded-xl gap-2 h-10">
                              <RefreshCw className="w-4 h-4" /> Volver a intentar
                            </Button>
                            <Button onClick={manualFromScan} className="rounded-xl gap-2 h-10 bg-emerald-500 hover:bg-emerald-600">
                              <PencilLine className="w-4 h-4" /> Ingresar manualmente
                            </Button>
                          </div>
                        </motion.div>
                      </motion.div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-3 text-center">
                    <p className="text-slate-500 font-medium">Selecciona un archivo</p>
                    <p className="text-sm text-slate-400">Foto de tu boleta (JPG, PNG o WEBP)</p>
                    <Button type="button" onClick={() => fileInputRef.current?.click()} className="mt-2 rounded-xl bg-emerald-500 hover:bg-emerald-600">
                      Elegir foto
                    </Button>
                  </div>
                )}
              </motion.div>
            )}

            {step === "manual" && (
              <motion.div key="manual" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-4 pt-2">
                {docStatus === "done" && partial && (
                  <div className="flex items-center gap-2 text-sm text-amber-600 bg-amber-50 rounded-xl px-3 py-2 mb-2">
                    <AlertTriangle className="w-4 h-4 shrink-0" /> Leímos tu boleta parcialmente. Revisa y completa los datos faltantes.
                  </div>
                )}
                {docStatus === "done" && !partial && (
                  <div className="flex items-center gap-2 text-sm text-emerald-600 bg-emerald-50 rounded-xl px-3 py-2 mb-2">
                    <CheckCircle2 className="w-4 h-4" /> Datos extraídos. Revisa y corrige si es necesario.
                  </div>
                )}
                <div className="space-y-1.5">
                  <Label>Comercio</Label>
                  <Input value={form.merchant} onChange={(e) => setForm({ ...form, merchant: e.target.value })} placeholder="Ej: Lider" />
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
                <div className="space-y-1.5">
                  <Label>Descripción <span className="text-slate-400 font-normal">(opcional)</span></Label>
                  <DescriptionGrid value={form.description} onChange={(val) => setForm({ ...form, description: val })} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label>Categoría</Label>
                    <Select value={form.category} onValueChange={handleCategoryChange}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {cats.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Pago <span className="text-slate-400 font-normal">(opcional)</span></Label>
                    <Select value={form.payment_method} onValueChange={(v) => setForm({ ...form, payment_method: v })}>
                      <SelectTrigger><SelectValue placeholder="Sin especificar" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value={null}>Sin especificar</SelectItem>
                        <SelectItem value="debito">Débito</SelectItem>
                        <SelectItem value="credito">Crédito</SelectItem>
                        <SelectItem value="efectivo">Efectivo</SelectItem>
                        <SelectItem value="transferencia">Transferencia</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {form.category === "Suscripciones" && (
                  <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200">
                    <div className="flex items-start gap-2">
                      <Repeat className={`w-4 h-4 mt-0.5 shrink-0 ${form.recurring_active ? "text-emerald-500" : "text-slate-400"}`} />
                      <div>
                        <div className="font-medium text-sm text-slate-700">Cobro fijo mensual</div>
                        <div className="text-xs text-slate-400">
                          {form.recurring_active
                            ? "Se generará automáticamente cada mes hasta que lo desactives"
                            : "Activa para generar este cobro automáticamente cada mes"}
                        </div>
                      </div>
                    </div>
                    <Switch
                      checked={form.recurring_active}
                      onCheckedChange={(checked) => setForm({ ...form, is_recurring: checked, recurring_active: checked })}
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <Label>Color del icono</Label>
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
                  {saving ? "Guardando..." : editExpense ? "Guardar cambios" : "Guardar boleta"}
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </DialogContent>
      </Dialog>

    </>
  );
}
