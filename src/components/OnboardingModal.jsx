import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Target, Wallet, PiggyBank, BarChart3, HelpCircle, Check, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { api, describirError } from "@/api";
import { useAuth } from "@/lib/AuthContext";
import LogoMark from "@/components/LogoMark";
import { sanitizeAmount, parseAmount } from "@/lib/format";

const OBJETIVOS = [
  { id: "ahorrar", label: "Ahorrar", icon: PiggyBank },
  { label: "Controlar mis gastos", icon: BarChart3, id: "controlar" },
  { id: "ambas", label: "Ambas", icon: Target },
  { id: "otro", label: "Otro", icon: HelpCircle },
];

export default function OnboardingModal({ onComplete }) {
  const { updateUser } = useAuth();
  const [step, setStep] = useState(0); // 0 = objetivo, 1 = presupuesto
  const [objetivo, setObjetivo] = useState(null);
  const [goalTitle, setGoalTitle] = useState("");
  const [goalAmount, setGoalAmount] = useState("");
  const [budgetChoice, setBudgetChoice] = useState(null); // "si" | "no"
  const [budgetAmount, setBudgetAmount] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const needsGoal = objetivo === "ahorrar" || objetivo === "ambas";

  const validateStep0 = () => {
    if (!objetivo) {
      setError("Debes seleccionar una opción");
      return false;
    }
    if (needsGoal) {
      if (!goalTitle.trim()) {
        setError("Indica el nombre de tu objetivo");
        return false;
      }
      if (!goalAmount || parseAmount(goalAmount) <= 0) {
        setError("Indica un monto válido para tu objetivo");
        return false;
      }
    }
    setError("");
    return true;
  };

  const validateStep1 = () => {
    if (!budgetChoice) {
      setError("Debes seleccionar una opción");
      return false;
    }
    if (budgetChoice === "si") {
      if (!budgetAmount || parseAmount(budgetAmount) <= 0) {
        setError("Indica un monto válido para tu presupuesto");
        return false;
      }
    }
    setError("");
    return true;
  };

  const handleNext = () => {
    if (step === 0) {
      if (validateStep0()) setStep(1);
    } else {
      if (validateStep1()) handleFinish();
    }
  };

  const handleBack = () => {
    setError("");
    setStep(0);
  };

  const handleFinish = async () => {
    setSaving(true);
    try {
      const updateData = { onboarded: true };
      if (budgetChoice === "si" && budgetAmount) {
        updateData.monthly_budget = parseAmount(budgetAmount);
      }
      await updateUser(updateData);

      if (needsGoal && goalTitle.trim() && parseAmount(goalAmount) > 0) {
        await api.goals.create({
          title: goalTitle.trim(),
          target_amount: parseAmount(goalAmount),
          current_amount: 0,
          color: "#22c55e",
        });
      }
      onComplete();
    } catch (e) {
      setError(describirError(e));
      setSaving(false);
    }
  };

  const formatCLP = (v) => "$" + parseAmount(v).toLocaleString("es-CL");

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
        className="bg-[#f5f7fa] rounded-3xl shadow-2xl w-full max-w-lg overflow-hidden"
      >
        {/* Progress header */}
        <div className="px-8 pt-7 pb-4">
          <div className="flex items-center gap-2 mb-1">
            <LogoMark className="w-7 h-7" />
            <span className="text-xl font-bold font-heading text-slate-800 tracking-tighter">Blynn</span>
          </div>
          <div className="flex items-center gap-1.5 mt-3">
            {[0, 1].map((i) => (
              <div
                key={i}
                className={`h-1.5 rounded-full transition-all duration-300 ${i === step ? "w-10 bg-sky-500" : i < step ? "w-6 bg-sky-300" : "w-6 bg-slate-200"}`}
              />
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-2">Paso {step + 1} de 2</p>
        </div>

        <div className="px-8 pb-7">
          <AnimatePresence mode="wait">
            {step === 0 ? (
              <motion.div
                key="step0"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.25 }}
              >
                <h2 className="text-2xl font-bold font-heading text-slate-800 mb-1">¿Cuál es tu objetivo?</h2>
                <p className="text-sm text-slate-400 mb-5">Esto nos ayuda a personalizar tu experiencia.</p>

                <div className="grid grid-cols-2 gap-3">
                  {OBJETIVOS.map((opt) => {
                    const selected = objetivo === opt.id;
                    const Icon = opt.icon;
                    return (
                      <button
                        key={opt.id}
                        onClick={() => { setObjetivo(opt.id); setError(""); }}
                        className={`relative flex flex-col items-center gap-2 p-4 rounded-2xl border-2 transition-all duration-200 ${
                          selected
                            ? "border-sky-500 bg-sky-50 shadow-sm"
                            : "border-slate-200 hover:border-sky-300 hover:bg-slate-50"
                        }`}
                      >
                        {selected && (
                          <span className="absolute top-2.5 right-2.5 w-5 h-5 rounded-full bg-sky-500 flex items-center justify-center">
                            <Check className="w-3 h-3 text-white" />
                          </span>
                        )}
                        <span className={`w-11 h-11 rounded-xl flex items-center justify-center transition-colors ${selected ? "bg-sky-100 text-sky-600" : "bg-slate-100 text-slate-500"}`}>
                          <Icon className="w-5 h-5" />
                        </span>
                        <span className={`text-sm font-medium ${selected ? "text-sky-700" : "text-slate-600"}`}>{opt.label}</span>
                      </button>
                    );
                  })}
                </div>

                <AnimatePresence>
                  {needsGoal && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.3, ease: "easeInOut" }}
                      className="overflow-hidden"
                    >
                      <div className="mt-4 p-4 rounded-2xl bg-slate-50 border border-slate-200">
                        <div className="flex items-center gap-2 mb-3">
                          <Target className="w-4 h-4 text-sky-500" />
                          <span className="text-sm font-semibold text-slate-700">Cuéntanos sobre tu meta</span>
                        </div>
                        <div className="space-y-3">
                          <div className="space-y-1.5">
                            <label className="text-xs font-medium text-slate-500">Nombre del objetivo</label>
                            <input
                              value={goalTitle}
                              onChange={(e) => setGoalTitle(e.target.value)}
                              placeholder="Ej: Viaje a Europa"
                              className="w-full h-10 rounded-xl border border-slate-200 bg-[#f5f7fa] px-3 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 focus:border-sky-400 transition-all"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="text-xs font-medium text-slate-500">Monto a ahorrar</label>
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-400 font-medium">$</span>
                              <input
                                inputMode="decimal"
                                value={sanitizeAmount(goalAmount)}
                                onChange={(e) => setGoalAmount(sanitizeAmount(e.target.value))}
                                placeholder="1.000.000"
                                className="w-full h-10 rounded-xl border border-slate-200 bg-[#f5f7fa] pl-7 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 focus:border-sky-400 transition-all"
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ) : (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.25 }}
              >
                <h2 className="text-2xl font-bold font-heading text-slate-800 mb-1">¿Quieres establecer un presupuesto mensual?</h2>
                <p className="text-sm text-slate-400 mb-5">Define cuánto quieres gastar cada mes.</p>

                <div className="grid grid-cols-2 gap-3">
                  {[
                    { id: "si", label: "Sí", icon: Wallet },
                    { id: "no", label: "No, más tarde", icon: HelpCircle },
                  ].map((opt) => {
                    const selected = budgetChoice === opt.id;
                    const Icon = opt.icon;
                    return (
                      <button
                        key={opt.id}
                        onClick={() => { setBudgetChoice(opt.id); setError(""); }}
                        className={`relative flex flex-col items-center gap-2 p-4 rounded-2xl border-2 transition-all duration-200 ${
                          selected
                            ? "border-emerald-500 bg-emerald-50 shadow-sm"
                            : "border-slate-200 hover:border-emerald-300 hover:bg-slate-50"
                        }`}
                      >
                        {selected && (
                          <span className="absolute top-2.5 right-2.5 w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center">
                            <Check className="w-3 h-3 text-white" />
                          </span>
                        )}
                        <span className={`w-11 h-11 rounded-xl flex items-center justify-center transition-colors ${selected ? "bg-emerald-100 text-emerald-600" : "bg-slate-100 text-slate-500"}`}>
                          <Icon className="w-5 h-5" />
                        </span>
                        <span className={`text-sm font-medium ${selected ? "text-emerald-700" : "text-slate-600"}`}>{opt.label}</span>
                      </button>
                    );
                  })}
                </div>

                <AnimatePresence>
                  {budgetChoice === "si" && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.3, ease: "easeInOut" }}
                      className="overflow-hidden"
                    >
                      <div className="mt-4 p-4 rounded-2xl bg-slate-50 border border-slate-200">
                        <div className="flex items-center gap-2 mb-3">
                          <Wallet className="w-4 h-4 text-emerald-500" />
                          <span className="text-sm font-semibold text-slate-700">Tu presupuesto mensual</span>
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-xs font-medium text-slate-500">Monto disponible para gastar</label>
                          <div className="relative">
                            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-400 font-medium">$</span>
                            <input
                              inputMode="decimal"
                              value={sanitizeAmount(budgetAmount)}
                              onChange={(e) => setBudgetAmount(sanitizeAmount(e.target.value))}
                              placeholder="300.000"
                              className="w-full h-10 rounded-xl border border-slate-200 bg-[#f5f7fa] pl-7 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400 transition-all"
                            />
                          </div>
                          {parseAmount(budgetAmount) > 0 && (
                            <p className="text-xs text-emerald-600 font-medium pt-1">
                              {formatCLP(budgetAmount)} disponibles para gastar cada mes
                            </p>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}
          </AnimatePresence>

          {error && (
            <p className="text-sm text-red-500 mt-4 font-medium">{error}</p>
          )}

          {/* Navigation */}
          <div className="flex items-center justify-between mt-6">
            {step > 0 ? (
              <button
                onClick={handleBack}
                disabled={saving}
                className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-slate-500 hover:bg-slate-100 font-medium text-sm transition-colors disabled:opacity-50"
              >
                <ChevronLeft className="w-4 h-4" /> Atrás
              </button>
            ) : <div />}

            <button
              onClick={handleNext}
              disabled={saving}
              className="flex items-center gap-1.5 px-6 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-600 text-white font-semibold text-sm shadow-md shadow-sky-500/20 transition-all disabled:opacity-50"
            >
              {saving ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Guardando...</>
              ) : step === 0 ? (
                <>Continuar <ChevronRight className="w-4 h-4" /></>
              ) : (
                <>Finalizar <Check className="w-4 h-4" /></>
              )}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}