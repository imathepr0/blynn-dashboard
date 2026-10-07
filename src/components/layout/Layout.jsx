import React, { useState, useEffect } from "react";
import { Outlet, useLocation, Link, useNavigate } from "react-router-dom";
import { LayoutDashboard, BarChart3, Receipt, Tags, FileText, Target, Settings, Plus, User, Info, HelpCircle, LogOut, Download, TrendingUp, AlertTriangle, RefreshCw, Wallet } from "lucide-react";
import NewExpenseDialog from "@/components/layout/NewExpenseDialog";
import IncomeDialog from "@/components/layout/IncomeDialog";
import OnboardingModal from "@/components/OnboardingModal";
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu";
import NotificationCenter from "@/components/layout/NotificationCenter";
import { api, alCambiar } from "@/api";
import { useAuth } from "@/lib/AuthContext";
import LogoMark from "@/components/LogoMark";
import { formatCLP, dateStrLocal, dateParts, isSameMonth } from "@/lib/format";
import { excedenteDelMes, contributionAmount, isContributionDue, approveContribution, skipContribution, autoContribute, undoContribution, AUTO_CONFIDENCE_LIMIT } from "@/lib/goalEngine";

const NAV = [
  { label: "Resumen", path: "/", icon: LayoutDashboard },
  { label: "Estadísticas", path: "/estadisticas", icon: BarChart3 },
  { label: "Gastos", path: "/gastos", icon: Receipt },
  { label: "Ingresos", path: "/ingresos", icon: TrendingUp },
  { label: "Categorías", path: "/categorias", icon: Tags },
  { label: "Boletas", path: "/boletas", icon: FileText },
  { label: "Metas", path: "/metas", icon: Target },
];

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [incomeDialogOpen, setIncomeDialogOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [pendingContributions, setPendingContributions] = useState([]);
  const [monthTotal, setMonthTotal] = useState(0);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const { user, logout } = useAuth();
  const userName = user?.full_name || "";
  const expanded = hovered || menuOpen;

  useEffect(() => {
    if (!user?.onboarded) setShowOnboarding(true);

    const loadData = async () => {
      try {
        const [expenses, categoriesInit, incomes] = await Promise.all([
          api.expenses.list({ sort: "-date", limit: 300 }),
          api.categories.list(),
          api.incomes.list({ sort: "-date", limit: 50 }),
        ]);
        let categories = categoriesInit;
        if (categories.length === 0) {
          // Idempotente: si otra pestaña las crea a la vez, no se duplican.
          categories = await api.categories.ensureDefaults();
        }

        const now = new Date();
        const monthExpenses = expenses.filter((e) => isSameMonth(e.date, now));
        setMonthTotal(monthExpenses.reduce((s, e) => s + (e.amount || 0), 0));

        // Recurring check
        const recurring = expenses.filter((e) => e.is_recurring && e.recurring_active);
        if (recurring.length > 0) {
          const toCreate = [];
          for (const r of recurring) {
            const original = dateParts(r.date);
            if (isSameMonth(r.date, now)) continue;
            const cloneExists = expenses.some(
              (e) => !e.is_recurring && e.merchant === r.merchant && e.amount === r.amount && e.category === r.category &&
              isSameMonth(e.date, now)
            );
            if (!cloneExists) {
              const day = Math.min(original.d, 28);
              const cloneDate = new Date(now.getFullYear(), now.getMonth(), day);
              toCreate.push({
                merchant: r.merchant, description: r.description, amount: r.amount, category: r.category,
                date: dateStrLocal(cloneDate), payment_method: r.payment_method, color: r.color,
                is_recurring: false, recurring_active: false,
              });
            }
          }
          if (toCreate.length > 0) await api.expenses.bulkCreate(toCreate);
        }

        // Notificaciones informativas
        const byCat = {};
        monthExpenses.forEach((e) => { byCat[e.category] = (byCat[e.category] || 0) + (e.amount || 0); });
        const notifs = [];
        categories.forEach((c) => {
          const spent = byCat[c.name] || 0;
          if (c.budget && spent >= c.budget * 0.8) {
            notifs.push({
              id: `cat-${c.id}-${spent >= c.budget ? "over" : "near"}`,
              icon: AlertTriangle,
              color: spent >= c.budget ? "#ef4444" : "#f59e0b",
              title: spent >= c.budget ? `Presupuesto superado: ${c.name}` : `Cerca del límite: ${c.name}`,
              desc: `$${spent.toLocaleString("es-CL")} de $${(c.budget || 0).toLocaleString("es-CL")}`,
            });
          }
        });
        const activeRecurring = expenses.filter((e) => e.is_recurring && e.recurring_active);
        if (activeRecurring.length > 0) {
          notifs.push({ id: "recurring", icon: RefreshCw, color: "#38bdf8", title: `${activeRecurring.length} cobro(s) recurrente(s) activo(s)`, desc: "Se generarán automáticamente cada mes" });
        }
        const monthIncome = incomes
          .filter((i) => isSameMonth(i.date, now))
          .reduce((s, i) => s + (i.amount || 0), 0);
        if (monthIncome > 0) {
          notifs.push({ id: "income-month", icon: TrendingUp, color: "#22c55e", title: `Ingresos del mes: $${monthIncome.toLocaleString("es-CL")}`, desc: "Ver detalles en Ingresos" });
        }
        if (incomes.length === 0) {
          notifs.push({
            id: "recomendacion-ingresos",
            icon: Wallet,
            color: "#38bdf8",
            title: "Registra tus ingresos",
            desc: "Te recomendamos agregar tu sueldo o ingresos del mes",
            action: { label: "Agregar ingreso", onClick: () => setIncomeDialogOpen(true) },
          });
        }

        // Metas: aportes automáticos vencidos
        const todayStr = dateStrLocal(new Date());
        const goals = await api.goals.list();
        const excedente = excedenteDelMes(incomes, expenses);
        const pending = [];
        for (const g of goals) {
          if (!isContributionDue(g, todayStr)) continue;
          const amount = contributionAmount(g, excedente);
          if ((g.auto_approved_count || 0) >= AUTO_CONFIDENCE_LIMIT) {
            if (amount > 0) {
              const created = await autoContribute(g, amount);
              const notif = {
                id: `auto-${g.id}-${created.id}`,
                icon: TrendingUp,
                color: "#22c55e",
                title: `Aporte automático: ${g.title}`,
                desc: `${formatCLP(amount)} sumados a tu meta`,
                action: { label: "Deshacer", onClick: async () => { await undoContribution(g.id, created); setNotifications((l) => l.filter((n) => n.id !== notif.id)); } },
              };
              notifs.push(notif);
            } else {
              await skipContribution(g);
              notifs.push({ id: `sin-excedente-${g.id}`, icon: AlertTriangle, color: "#f59e0b", title: "Sin excedente este mes", desc: `No hubo dinero sobrante para aportar a «${g.title}»` });
            }
          } else {
            pending.push({ goal: g, amount });
          }
        }
        setNotifications(notifs);
        setPendingContributions(pending);
      } catch {}
    };

    loadData();
  }, []);

  useEffect(() => {
    const refreshMonthTotal = async () => {
      try {
        const expenses = await api.expenses.list({ sort: "-date", limit: 300 });
        const now = new Date();
        const total = expenses
          .filter((e) => isSameMonth(e.date, now))
          .reduce((s, e) => s + (e.amount || 0), 0);
        setMonthTotal(total);
      } catch {}
    };
    // Antes era el tiempo real de la plataforma anterior; ahora la capa de API avisa al modificar gastos.
    return alCambiar("expenses", refreshMonthTotal);
  }, []);

  const approvePending = async (p) => {
    await approveContribution(p.goal, p.amount);
    setPendingContributions((l) => l.filter((x) => x.goal.id !== p.goal.id));
  };
  const rejectPending = async (p) => {
    await skipContribution(p.goal);
    setPendingContributions((l) => l.filter((x) => x.goal.id !== p.goal.id));
  };

  const today = new Date();
  const dateStr = today.toLocaleDateString("es-CL", { weekday: "long", day: "numeric", month: "long" });
  const greeting = `Hola${userName ? ", " + userName.split(" ")[0] : ""}`;

  return (
    <div className="min-h-screen bg-background bg-dots">
      {/* Floating sidebar */}
      <aside
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        className={`fixed left-4 top-4 bottom-4 z-30 flex flex-col rounded-3xl bg-slate-900 shadow-2xl transition-all duration-300 overflow-hidden ${expanded ? "w-64 px-4" : "w-[76px] px-3"}`}
      >
        <div className={`flex items-center justify-center mt-6 mb-4 ${expanded ? "gap-1" : ""}`}>
          <LogoMark className="w-10 h-10" />
          <span className={`text-3xl font-bold font-heading text-white leading-none tracking-tighter transition-all duration-200 overflow-hidden ${expanded ? "opacity-100 w-auto" : "opacity-0 w-0"}`}>
            lynn
          </span>
        </div>

        <button
          onClick={() => setDialogOpen(true)}
          className={`group relative flex items-center justify-center gap-2 overflow-hidden text-white font-semibold rounded-2xl shadow-lg shadow-sky-500/20 transition-all duration-300 active:scale-[0.98] shrink-0 mt-10 mb-2 h-12 ${expanded ? "w-full" : "w-12 mx-auto"}`}
          style={{ background: "linear-gradient(120deg, #2563eb, #10b981, #2563eb)", backgroundSize: "200% 200%", animation: "gradient-oscillate 4s ease-in-out infinite" }}
          onMouseEnter={(e) => { e.currentTarget.style.animationDuration = "8s"; }}
          onMouseLeave={(e) => { e.currentTarget.style.animationDuration = "4s"; }}
        >
          <span className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" style={{ background: "radial-gradient(circle at 50% 50%, rgba(255,255,255,0.2), transparent 70%)" }} />
          <Plus className="w-5 h-5 shrink-0 relative z-10 transition-transform duration-300 group-hover:rotate-90" />
          <span className={`whitespace-nowrap overflow-hidden transition-all duration-200 relative z-10 ${expanded ? "opacity-100 w-auto" : "opacity-0 w-0"}`}>Nueva boleta</span>
        </button>

        <nav className="flex flex-col gap-1 flex-1 justify-center">
          {NAV.map((item) => {
            const active = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                title={item.label}
                className={`group relative flex items-center rounded-xl font-medium transition-colors duration-300 h-11 ${expanded ? "gap-3 px-4" : "justify-center px-0"} ${
                  active ? "bg-sky-500/15 text-sky-400" : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                {active && <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full bg-sky-400" />}
                <Icon className={`w-5 h-5 shrink-0 transition-transform duration-300 group-hover:scale-110 ${active ? "text-sky-400" : ""}`} />
                <span className={`whitespace-nowrap overflow-hidden transition-opacity duration-200 ${expanded ? "opacity-100 w-auto" : "opacity-0 w-0"}`}>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <DropdownMenu onOpenChange={setMenuOpen}>
          <DropdownMenuTrigger asChild>
            <div className={`flex items-center h-14 border-t border-slate-800 mb-2 cursor-pointer ${expanded ? "gap-3 px-2" : "justify-center"}`}>
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-sky-500 to-emerald-500 flex items-center justify-center text-white shrink-0 hover:scale-110 hover:ring-2 hover:ring-sky-400/50 transition-all duration-300">
                <User className="w-5 h-5" />
              </div>
              <div className={`overflow-hidden transition-all duration-200 ${expanded ? "opacity-100 w-auto" : "opacity-0 w-0"}`}>
                <div className="text-sm font-semibold text-white leading-tight">{userName || "Usuario"}</div>
                <div className="text-xs text-slate-500">Cuenta</div>
              </div>
            </div>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align={expanded ? "end" : "center"} className="w-52 mb-2 bg-slate-800 border-slate-700 text-slate-200">
            <DropdownMenuItem onSelect={() => navigate("/exportar-datos")} className="hover:bg-white/5 hover:text-white cursor-pointer gap-2 focus:bg-white/5 focus:text-white">
              <Download className="w-4 h-4" /> Exportar datos
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => navigate("/ajustes")} className="hover:bg-white/5 hover:text-white cursor-pointer gap-2 focus:bg-white/5 focus:text-white">
              <Settings className="w-4 h-4" /> Configuración
            </DropdownMenuItem>
            <DropdownMenuItem className="hover:bg-white/5 hover:text-white cursor-pointer gap-2 focus:bg-white/5 focus:text-white">
              <Info className="w-4 h-4" /> Más información
            </DropdownMenuItem>
            <DropdownMenuItem className="hover:bg-white/5 hover:text-white cursor-pointer gap-2 focus:bg-white/5 focus:text-white">
              <HelpCircle className="w-4 h-4" /> Obtener ayuda
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-slate-700" />
            <DropdownMenuItem className="hover:bg-red-500/10 hover:text-red-400 cursor-pointer gap-2 focus:bg-red-500/10 focus:text-red-400" onClick={logout}>
              <LogOut className="w-4 h-4" /> Cerrar sesión
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </aside>

      {/* Main content */}
      <div className="ml-[96px] mr-4 mb-4 mt-3 flex flex-col min-h-[calc(100vh-28px)]">
        <header className="flex items-center justify-between px-8 py-5 mb-4 rounded-2xl bg-[#f5f7fa] shadow-md pl-56">
          <div>
            <h2 className="text-xl font-semibold font-heading text-slate-700">{greeting}</h2>
            <p className="text-sm text-slate-400 capitalize">{dateStr}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-4 py-2 rounded-full bg-slate-100">
              <span className="text-sm text-slate-400">Gastos del mes</span>
              <span className="font-bold font-heading tabular-nums text-slate-700">{formatCLP(monthTotal)}</span>
            </div>
            <NotificationCenter
              notifications={notifications}
              onDismiss={(id) => setNotifications((l) => l.filter((n) => n.id !== id))}
              pending={pendingContributions}
              onApprove={approvePending}
              onReject={rejectPending}
            />
          </div>
        </header>

        <main className="flex-1 px-8 py-6 overflow-y-auto">
          <div className="max-w-6xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>

      <NewExpenseDialog open={dialogOpen} onOpenChange={setDialogOpen} />
      <IncomeDialog open={incomeDialogOpen} onOpenChange={setIncomeDialogOpen} />
      {showOnboarding && (
        <OnboardingModal onComplete={() => setShowOnboarding(false)} />
      )}
    </div>
  );
}