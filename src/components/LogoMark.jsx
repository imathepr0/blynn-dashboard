import React, { useId } from "react";

// Marca "B" de Blynn, dibujada en SVG (antes era una imagen alojada en los
// servidores de la plataforma anterior, que deja de existir al migrar). Para usar el logo
// original: guardar la imagen en public/logo.png y reemplazar este SVG por
// <img src="/logo.png" ... /> aquí; lo usan el menú, el acceso y la bienvenida.
export default function LogoMark({ className = "w-10 h-10" }) {
  const id = useId();
  return (
    <svg viewBox="0 0 64 64" className={`${className} shrink-0`} role="img" aria-label="Blynn">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2563eb" />
          <stop offset="1" stopColor="#22c55e" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill={`url(#${id})`} />
      <text x="32" y="46" fontSize="42" fontWeight="700" fontFamily="Arial, sans-serif" textAnchor="middle" fill="#fff">
        B
      </text>
    </svg>
  );
}
