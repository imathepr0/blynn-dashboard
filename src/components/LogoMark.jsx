import React from "react";

// El archivo vive en public para que la marca siempre se cargue desde este sitio.
export default function LogoMark({ className = "w-10 h-10" }) {
  return (
    <img
      src="/logo-blynn.png"
      className={`${className} shrink-0 object-contain`}
      alt="Logo de Blynn"
      draggable="false"
    />
  );
}
