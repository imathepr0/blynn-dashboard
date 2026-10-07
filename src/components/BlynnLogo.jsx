import React from "react";

export default function BlynnLogo({ className = "" }) {
  return (
    <div className={`flex items-center gap-1 select-none ${className}`}>
      <span
        className="text-3xl font-extrabold leading-none"
        style={{
          background: "linear-gradient(135deg, #2563eb 0%, #22c55e 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}
      >
        B
      </span>
      <span className="text-2xl font-bold text-emerald-500 leading-none tracking-tight">
        lynn
      </span>
    </div>
  );
}