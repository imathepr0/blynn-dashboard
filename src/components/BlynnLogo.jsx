import React from "react";
import LogoMark from "@/components/LogoMark";

export default function BlynnLogo({ className = "" }) {
  return (
    <div className={`flex items-center gap-1 select-none ${className}`}>
      <LogoMark className="w-10 h-10" />
      <span className="text-2xl font-bold text-emerald-500 leading-none tracking-tight">
        lynn
      </span>
    </div>
  );
}
