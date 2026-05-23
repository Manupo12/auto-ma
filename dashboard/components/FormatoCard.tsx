import { useState } from "react";
import { FileText, Download, CheckCircle, AlertCircle, Edit3 } from "lucide-react";

interface Props {
  nombre: string;
  archivoDocx?: string;
  archivoPdf?: string;
  qaOk?: boolean;
  qaWarnings?: string[];
  onAprobar?: () => void;
  onCorregir?: () => void;
}

export function FormatoCard({ nombre, archivoDocx, archivoPdf, qaOk, qaWarnings, onAprobar, onCorregir }: Props) {
  const [aprobado, setAprobado] = useState(false);

  return (
    <div className={`p-6 bg-white border-2 rounded-2xl shadow-sm ${aprobado ? "border-green-400 bg-green-50" : qaOk === false ? "border-amber-400" : "border-slate-200"}`}>
      <div className="flex items-start gap-4">
        <FileText size={36} className={aprobado ? "text-green-600" : "text-blue-600"} />
        <div className="flex-1">
          <h3 className="text-xl font-semibold text-slate-800">{nombre}</h3>
          {qaWarnings && qaWarnings.length > 0 && (
            <p className="text-sm text-amber-600 mt-1 flex items-center gap-1">
              <AlertCircle size={14} /> {qaWarnings.length} advertencia(s)
            </p>
          )}
          {aprobado && (
            <p className="text-sm text-green-600 mt-1 flex items-center gap-1">
              <CheckCircle size={14} /> Aprobado
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {archivoDocx && (
            <a href={`/api/download/${encodeURIComponent(archivoDocx.split("/").pop() || "")}`} download
               className="p-3 bg-slate-100 hover:bg-slate-200 rounded-lg" title="Descargar DOCX">
              <Download size={20} />
            </a>
          )}
        </div>
      </div>

      {!aprobado && (
        <div className="flex gap-3 mt-4">
          <button onClick={() => { setAprobado(true); onAprobar?.(); }}
                  className="flex-1 px-6 py-3 bg-green-600 hover:bg-green-700 text-white rounded-xl text-lg font-semibold flex items-center justify-center gap-2">
            <CheckCircle size={20} /> Aprobar
          </button>
          <button onClick={onCorregir}
                  className="flex-1 px-6 py-3 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-lg font-semibold flex items-center justify-center gap-2">
            <Edit3 size={20} /> Corregir
          </button>
        </div>
      )}
    </div>
  );
}
