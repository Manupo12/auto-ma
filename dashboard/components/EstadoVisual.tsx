import { CheckCircle, AlertCircle, Clock, XCircle, Loader2 } from "lucide-react";

type Estado = "ok" | "progreso" | "warn" | "error";

interface Props {
  estado: Estado;
  titulo: string;
  detalle?: string;
}

export function EstadoVisual({ estado, titulo, detalle }: Props) {
  const config = {
    ok: { Icon: CheckCircle, color: "text-green-600", bg: "bg-green-50 border-green-200" },
    progreso: { Icon: Loader2, color: "text-blue-600 animate-spin", bg: "bg-blue-50 border-blue-200" },
    warn: { Icon: AlertCircle, color: "text-amber-600", bg: "bg-amber-50 border-amber-200" },
    error: { Icon: XCircle, color: "text-red-600", bg: "bg-red-50 border-red-200" },
  }[estado];

  return (
    <div className={`flex items-start gap-4 p-5 rounded-xl border-2 ${config.bg}`}>
      <config.Icon size={36} className={config.color} />
      <div>
        <p className="text-xl font-semibold text-slate-800">{titulo}</p>
        {detalle && <p className="text-base text-slate-600 mt-1">{detalle}</p>}
      </div>
    </div>
  );
}
