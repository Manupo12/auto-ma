import { CheckCircle, Circle, Loader2 } from "lucide-react";

const PASOS = [
  "Pendiente",
  "Transcribiendo audio",
  "Buscando en portales",
  "Leyendo notas",
  "Leyendo formatos subidos",
  "Cruzando información",
  "Generando documentos",
  "Verificando calidad",
  "Generando PDFs",
  "Notificando",
];

export function TimelinePaciente({ pasoActual, estado }: { pasoActual: number; estado: string }) {
  return (
    <div className="space-y-2">
      {PASOS.slice(1).map((paso, idx) => {
        const num = idx + 1;
        const completo = num < pasoActual;
        const actual = num === pasoActual;
        const Icon = completo ? CheckCircle : actual ? Loader2 : Circle;
        return (
          <div key={num} className={`flex items-center gap-3 ${completo ? "text-green-600" : actual ? "text-blue-600" : "text-slate-400"}`}>
            <Icon size={22} className={actual ? "animate-spin" : ""} />
            <span className={`text-base ${actual ? "font-semibold" : ""}`}>
              {num}. {paso}
            </span>
          </div>
        );
      })}
    </div>
  );
}
