import React from "react";
import { Button } from "@/components/ui/button";
import { WifiOff } from "lucide-react";

// Pantalla para cuando no se puede hablar con el servidor al iniciar la app.
// La sesión NO se cierra: al reintentar se continúa donde se estaba.
export default function ErrorDeConexion({ mensaje, onReintentar }) {
  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-slate-50">
      <div className="max-w-md w-full text-center space-y-4">
        <div className="mx-auto w-14 h-14 rounded-full bg-amber-50 flex items-center justify-center">
          <WifiOff className="w-7 h-7 text-amber-500" aria-hidden="true" />
        </div>
        <h1 className="text-2xl font-bold font-heading text-slate-700">No pudimos conectar</h1>
        <p className="text-slate-500">{mensaje}</p>
        <Button onClick={onReintentar} className="bg-emerald-500 hover:bg-emerald-600">
          Reintentar
        </Button>
      </div>
    </div>
  );
}
