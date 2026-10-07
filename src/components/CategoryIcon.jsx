import React from "react";
import { ShoppingBag, Car, Ticket, Heart, Home, Package, Shirt, KeyRound, GraduationCap, Film, ArrowLeftRight, Smartphone } from "lucide-react";
import { colorForCategory } from "@/lib/format";

const CATEGORY_ICONS = {
  "Alimentación": ShoppingBag,
  "Transporte": Car,
  "Suscripciones": Ticket,
  "Salud": Heart,
  "Hogar": Home,
  "Ropa": Shirt,
  "Arriendo": KeyRound,
  "Educación": GraduationCap,
  "Entretenimiento": Film,
  "Transferencias": ArrowLeftRight,
  "Tecnología": Smartphone,
  "Otros": Package,
};

export function getCategoryIcon(name) {
  return CATEGORY_ICONS[name] || Package;
}

export function hexToRgba(hex, alpha = 1) {
  const h = (hex || "").replace("#", "");
  if (h.length !== 6) return `rgba(148, 163, 184, ${alpha})`;
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export const COLOR_PALETTE = [
  "#3b82f6", "#22c55e", "#f97316", "#a78bfa",
  "#ec4899", "#14b8a6", "#eab308", "#ef4444",
];

export function randomColor() {
  return COLOR_PALETTE[Math.floor(Math.random() * COLOR_PALETTE.length)];
}

export default function CategoryIcon({ category, color, size = "md", className = "" }) {
  const Icon = getCategoryIcon(category);
  const iconColor = color || colorForCategory(category);
  const sizeClasses = size === "sm" ? "w-8 h-8" : "w-10 h-10";
  const iconSize = size === "sm" ? "w-4 h-4" : "w-5 h-5";

  return (
    <span
      className={`${sizeClasses} rounded-xl shrink-0 flex items-center justify-center border transition-transform group-hover:scale-110 ${className}`}
      style={{
        background: hexToRgba(iconColor, 0.12),
        borderColor: hexToRgba(iconColor, 0.3),
        color: iconColor,
      }}
    >
      <Icon className={iconSize} />
    </span>
  );
}