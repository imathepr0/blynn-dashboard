import React from "react";

export default function StatCard({ label, value, delta, deltaLabel, positive }) {
  return (
    <div className="flex-1 text-center px-6 py-2 group">
      <div className="text-slate-500 font-medium mb-2">{label}</div>
      <div className="text-3xl font-bold text-slate-800 mb-2 transition-transform duration-200 group-hover:scale-105">
        {value}
      </div>
      <div className="text-sm text-slate-400">
        <span className={positive ? "text-emerald-500 font-semibold" : "text-emerald-500 font-semibold"}>{delta}</span>{" "}
        {deltaLabel}
      </div>
    </div>
  );
}