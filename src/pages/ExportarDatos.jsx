import React, { useEffect, useState } from "react";
import { api } from "@/api";
import { FileText, FileSpreadsheet, Loader2 } from "lucide-react";
import { formatCLP } from "@/lib/format";
import { jsPDF } from "jspdf";

export default function ExportarDatos() {
  const [expenses, setExpenses] = useState([]);
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.expenses.list({ sort: "-date", limit: 500 }),
      api.goals.list({ sort: "-created_date", limit: 100 }),
    ]).then(([e, g]) => {
      setExpenses(e);
      setGoals(g);
      setLoading(false);
    });
  }, []);

  const exportCSV = () => {
    let csv = "Tipo,Comercio/Categoría,Monto,Fecha,Descripción\n";
    expenses.forEach((e) => {
      csv += `Gasto,"${(e.merchant || "").replace(/"/g, '""')}",${e.amount || 0},${e.date || ""},"${(e.description || "").replace(/"/g, '""').replace(/\n/g, " ")}"\n`;
    });
    csv += "\nTipo,Meta,Monto Objetivo,Monto Actual,Fecha Límite\n";
    goals.forEach((g) => {
      csv += `Meta,"${(g.title || "").replace(/"/g, '""')}",${g.target_amount || 0},${g.current_amount || 0},${g.deadline || ""}\n`;
    });

    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `blynn-export-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportPDF = () => {
    const doc = new jsPDF();

    doc.setFontSize(20);
    doc.text("Blynn - Exportar Datos", 14, 22);
    doc.setFontSize(10);
    doc.setTextColor(100);
    doc.text(`Fecha: ${new Date().toLocaleDateString("es-CL")}`, 14, 30);

    doc.setTextColor(0);
    doc.setFontSize(14);
    doc.text("Gastos", 14, 42);

    doc.setFontSize(8);
    let y = 50;
    doc.text("Fecha", 14, y);
    doc.text("Comercio", 50, y);
    doc.text("Categoría", 100, y);
    doc.text("Monto", 160, y);
    y += 5;
    doc.setDrawColor(200);
    doc.line(14, y - 2, 196, y - 2);

    expenses.slice(0, 40).forEach((e) => {
      y += 7;
      if (y > 270) { doc.addPage(); y = 20; }
      doc.text(e.date || "", 14, y);
      doc.text((e.merchant || "").substring(0, 25), 50, y);
      doc.text((e.category || "").substring(0, 20), 100, y);
      doc.text(formatCLP(e.amount), 160, y);
    });

    doc.addPage();
    doc.setFontSize(14);
    doc.text("Metas", 14, 22);
    doc.setFontSize(8);
    y = 30;
    doc.text("Título", 14, y);
    doc.text("Objetivo", 80, y);
    doc.text("Actual", 130, y);
    doc.text("Fecha límite", 170, y);
    y += 5;
    doc.line(14, y - 2, 196, y - 2);

    goals.forEach((g) => {
      y += 7;
      if (y > 270) { doc.addPage(); y = 20; }
      doc.text((g.title || "").substring(0, 30), 14, y);
      doc.text(formatCLP(g.target_amount), 80, y);
      doc.text(formatCLP(g.current_amount), 130, y);
      doc.text(g.deadline || "", 170, y);
    });

    doc.save(`blynn-export-${new Date().toISOString().slice(0, 10)}.pdf`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 text-sky-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-bold font-heading text-slate-700 mb-6">Exportar Datos</h1>

      <div className="bg-white rounded-3xl p-8 shadow-sm space-y-6">
        <p className="text-slate-500">
          Exporta tu historial de gastos y metas en formato PDF o CSV para análisis externo.
        </p>

        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={exportPDF}
            className="flex flex-col items-center gap-3 p-6 rounded-2xl border border-slate-200 hover:border-red-400 hover:bg-red-50/50 transition-all duration-200 group"
          >
            <span className="w-12 h-12 rounded-xl bg-red-100 group-hover:bg-red-500 group-hover:text-white flex items-center justify-center text-red-500 transition-all duration-200">
              <FileText className="w-6 h-6" />
            </span>
            <div className="font-semibold text-slate-800">Exportar PDF</div>
            <div className="text-sm text-slate-400">{expenses.length} gastos · {goals.length} metas</div>
          </button>

          <button
            onClick={exportCSV}
            className="flex flex-col items-center gap-3 p-6 rounded-2xl border border-slate-200 hover:border-emerald-400 hover:bg-emerald-50/50 transition-all duration-200 group"
          >
            <span className="w-12 h-12 rounded-xl bg-green-100 group-hover:bg-emerald-500 group-hover:text-white flex items-center justify-center text-emerald-500 transition-all duration-200">
              <FileSpreadsheet className="w-6 h-6" />
            </span>
            <div className="font-semibold text-slate-800">Exportar CSV</div>
            <div className="text-sm text-slate-400">{expenses.length} gastos · {goals.length} metas</div>
          </button>
        </div>
      </div>
    </div>
  );
}