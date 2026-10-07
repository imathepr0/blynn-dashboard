import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/api";
import { useAuth } from "@/lib/AuthContext";
import { mostrarError } from "@/lib/errores";
import { User, LogOut, Loader2, CheckCircle2, Wallet, Trash2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/ui/numeric-input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader, AlertDialogFooter, AlertDialogTitle, AlertDialogDescription, AlertDialogAction, AlertDialogCancel } from "@/components/ui/alert-dialog";
import OnboardingModal from "@/components/OnboardingModal";
import { formatCLP, parseAmount } from "@/lib/format";

export default function Ajustes() {
  const { user, updateUser, replaceUser, logout } = useAuth();
  const [name, setName] = useState(user?.full_name || "");
  const email = user?.email || "";
  const [notifications, setNotifications] = useState(user?.preferences?.notifications ?? true);
  const [monthlyBudget, setMonthlyBudget] = useState(user?.monthly_budget ? String(user.monthly_budget) : "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [savingBudget, setSavingBudget] = useState(false);
  const [savedBudget, setSavedBudget] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const navigate = useNavigate();

  const handleReset = async () => {
    if (!user) return;
    setResetting(true);
    try {
      // Una sola operación en el servidor: borra los datos, recrea las categorías
      // por defecto y reinicia la encuesta; si algo falla, no se pierde nada.
      replaceUser(await api.me.reset());
      setMonthlyBudget("");
      setShowOnboarding(true);
    } catch (e) {
      mostrarError(e, "No se pudo reiniciar la cuenta");
    } finally {
      setResetting(false);
    }
  };

  const saveProfile = async () => {
    setSaving(true);
    try {
      await updateUser({ full_name: name, preferences: { notifications } });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      mostrarError(e, "No se pudo guardar el perfil");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-bold font-heading text-slate-700 mb-6">Configuración</h1>

      {/* Account info */}
      <div className="bg-[#f5f7fa] rounded-3xl p-7 shadow-sm mb-5">
        <div className="flex items-center gap-4 mb-6 pb-6 border-b border-slate-100">
          {/* No hay foto de perfil: todos los usuarios usan el mismo avatar. */}
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center text-white">
            <User className="w-7 h-7" aria-hidden="true" />
          </div>
          <div>
            <div className="text-lg font-bold font-heading text-slate-800">{user?.full_name || "Usuario"}</div>
            <div className="text-slate-400">{user?.email || "demo@blynn.cl"}</div>
          </div>
        </div>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-slate-600">Moneda</span>
            <span className="font-semibold text-slate-800">Peso chileno (CLP)</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-600">Idioma</span>
            <span className="font-semibold text-slate-800">Español</span>
          </div>
        </div>
        <Button onClick={logout} variant="outline" className="w-full mt-8 rounded-xl gap-2 text-red-500 border-red-200 hover:bg-red-50 hover:text-red-600">
          <LogOut className="w-4 h-4" /> Cerrar sesión
        </Button>
      </div>

      {/* Monthly budget */}
      <div className="bg-[#f5f7fa] rounded-3xl p-7 shadow-sm mb-5">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-11 h-11 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-500">
            <Wallet className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold font-heading text-slate-700">Presupuesto mensual</h2>
            <p className="text-sm text-slate-400">Cuánto quieres gastar cada mes</p>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label>Monto mensual disponible</Label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-medium">$</span>
            <NumericInput
              value={monthlyBudget}
              onChange={(v) => setMonthlyBudget(v)}
              placeholder="300.000"
              className="pl-7"
            />
          </div>
          <p className="text-xs text-slate-400">
            {parseAmount(monthlyBudget) > 0
              ? `Tienes ${formatCLP(monthlyBudget)} disponibles para gastar cada mes`
              : "Si lo dejas vacío, se usará la suma de los presupuestos por categoría"}
          </p>
        </div>
        <Button
          onClick={async () => {
            setSavingBudget(true);
            try {
              await updateUser({ monthly_budget: parseAmount(monthlyBudget) });
              setSavedBudget(true);
              setTimeout(() => setSavedBudget(false), 3000);
            } catch (e) {
              mostrarError(e, "No se pudo guardar el presupuesto");
            } finally {
              setSavingBudget(false);
            }
          }}
          disabled={savingBudget}
          className="w-full mt-5 bg-emerald-500 hover:bg-emerald-600 rounded-xl h-11"
        >
          {savingBudget ? "Guardando..." : savedBudget ? (
            <span className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4" /> ¡Guardado!</span>
          ) : "Guardar presupuesto"}
        </Button>
      </div>

      {/* Profile settings */}
      <div className="bg-[#f5f7fa] rounded-3xl p-7 shadow-sm">
        <h2 className="text-lg font-semibold font-heading text-slate-700 mb-5">Datos de perfil</h2>

        <div className="flex items-center gap-4 mb-6">
          <div className="relative">
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-sky-500 to-emerald-500 flex items-center justify-center text-white">
              <User className="w-9 h-9" aria-hidden="true" />
            </div>
          </div>
          <div>
            <div className="font-semibold text-slate-800">{name || "Usuario"}</div>
            <div className="text-sm text-slate-400">{email}</div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Nombre</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Tu nombre" />
          </div>

          <div className="space-y-1.5">
            <Label>Correo electrónico</Label>
            <Input value={email} disabled />
            <p className="text-xs text-slate-400">El correo no se puede modificar</p>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-slate-100">
            <div>
              <div className="font-medium text-slate-700">Notificaciones</div>
              <div className="text-sm text-slate-400">Recibir alertas de gastos y presupuestos</div>
            </div>
            <Switch checked={notifications} onCheckedChange={setNotifications} />
          </div>
        </div>

        <Button onClick={saveProfile} disabled={saving} className="w-full mt-6 bg-emerald-500 hover:bg-emerald-600 rounded-xl h-11">
          {saving ? "Guardando..." : saved ? (
            <span className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4" /> ¡Guardado!</span>
          ) : "Guardar cambios"}
        </Button>
      </div>

      {/* Danger zone */}
      <div className="mt-5 bg-[#f5f7fa] rounded-3xl p-7 shadow-sm border border-red-100">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-11 h-11 rounded-xl bg-red-50 flex items-center justify-center text-red-500">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold font-heading text-slate-700">Zona de peligro</h2>
            <p className="text-sm text-slate-400">Reinicia tu cuenta desde cero</p>
          </div>
        </div>
        <p className="text-sm text-slate-500 mb-5">
          Se eliminarán permanentemente todos tus gastos, ingresos, metas y categorías.
          Después podrás volver a configurar tu presupuesto y tu meta con la encuesta inicial.
        </p>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="outline" disabled={resetting} className="w-full rounded-xl h-11 gap-2 text-red-500 border-red-200 hover:bg-red-50 hover:text-red-600">
              {resetting ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Eliminando datos...</>
              ) : (
                <><Trash2 className="w-4 h-4" /> Eliminar todos los datos</>
              )}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>¿Seguro que quieres eliminar todo?</AlertDialogTitle>
              <AlertDialogDescription>
                Esta acción no se puede deshacer. Se borrarán todos tus gastos, ingresos, metas y categorías, y tu cuenta volverá a su estado inicial.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction onClick={handleReset} className="bg-red-500 hover:bg-red-600">
                Sí, eliminar todo
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      {showOnboarding && (
        <OnboardingModal onComplete={() => { setShowOnboarding(false); navigate("/"); }} />
      )}
    </div>
  );
}