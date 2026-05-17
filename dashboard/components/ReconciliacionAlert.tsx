"use client";

import { CheckCircle2, AlertTriangle, Info, ShieldAlert } from "lucide-react";

interface Reconciliacion {
  medifolios: string;
  positiva: string;
  coinciden: boolean;
  alerta: string;
}

export function ReconciliacionAlert({ data }: { data?: Reconciliacion }) {
  if (!data) return null;

  const tieneDatos = data.medifolios || data.positiva;
  if (!tieneDatos) {
    return (
      <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm">
        <ShieldAlert size={16} className="text-red-500 flex-shrink-0" />
        <div>
          <p className="font-medium text-red-800">Siniestro no encontrado</p>
          <p className="text-red-600">{data.alerta}</p>
        </div>
      </div>
    );
  }

  if (data.coinciden && data.medifolios && data.positiva) {
    return (
      <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg text-sm">
        <CheckCircle2 size={16} className="text-green-500 flex-shrink-0" />
        <div>
          <p className="font-medium text-green-800">Siniestro reconciliado ✅</p>
          <p className="text-green-600">
            Medifolios: {data.medifolios} · Positiva: {data.positiva}
          </p>
        </div>
      </div>
    );
  }

  if (!data.coinciden) {
    return (
      <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm">
        <AlertTriangle size={16} className="text-red-500 flex-shrink-0" />
        <div>
          <p className="font-medium text-red-800">⚠️ Discrepancia de siniestro</p>
          <p className="text-red-600">Medifolios: {data.medifolios || "—"}</p>
          <p className="text-red-600">Positiva: {data.positiva || "—"}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm">
      <Info size={16} className="text-blue-500 flex-shrink-0" />
      <p className="text-blue-700">{data.alerta}</p>
    </div>
  );
}
