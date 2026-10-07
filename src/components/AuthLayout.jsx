import React from "react";
import LogoMark from "@/components/LogoMark";

export default function AuthLayout({ title, subtitle, footer, children }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 bg-dots px-4">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div className="flex items-center gap-1 mb-5">
            <LogoMark className="w-10 h-10" />
            <span className="text-3xl font-bold font-heading text-slate-700 leading-none tracking-tighter">lynn</span>
          </div>
          <h1 className="text-2xl font-bold font-heading text-slate-700">{title}</h1>
          {subtitle && <p className="text-slate-400 mt-2 text-center">{subtitle}</p>}
        </div>
        <div className="bg-white rounded-3xl shadow-lg border border-slate-100 p-8">
          {children}
        </div>
        {footer && <p className="text-center text-sm text-slate-400 mt-6">{footer}</p>}
      </div>
    </div>
  );
}
