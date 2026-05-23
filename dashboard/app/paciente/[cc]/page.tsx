"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2, AlertCircle, Clock, CheckCircle, FileText } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const PASOS_LABELS: Record<number, string> = {
  1: "Transcribiendo audio...",
  2: "Buscando datos del paciente...",
  3: "Leyendo notas clinicas...",
  4: "Leyendo formatos de referencia...",
  5: "Sintetizando con IA...",
  6: "Verificando en portales...",
  7: "Generando formatos...",
  8: "Verificando calidad...",
  9: "Convirtiendo a PDF...",
  10: "Notificando...",
};

interface TaskActiva {
  task_id: string;
  estado: string;
  paso_actual: number;
  error?: string;
  resultado?: any;
}

export default function PacientePage() {
  const { cc } = useParams<{ cc: string }>();
  const [paciente, setPaciente] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [taskActiva, setTaskActiva] = useState<TaskActiva | null>(null);
  const [formatos, setFormatos] = useState<any[]>([]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;

    const cargar = async () => {
      try {
        const [rP, rT, rF] = await Promise.all([
          fetch(`${API}/api/pacientes/${cc}`),
          fetch(`${API}/api/tasks/paciente/${cc}`),
          fetch(`${API}/api/pacientes/${cc}/formatos`),
        ]);

        if (rP.ok) setPaciente(await rP.json());
        else if (rP.status === 404) setError("");
        else setError("Error al cargar datos del paciente");

        if (rT.ok) {
          const data = await rT.json();
          const tasks = data.tasks || [];
          const activa = tasks.find((t: any) =>
            !["listo", "cancelado"].includes(t.estado) && !t.estado?.startsWith("error_")
          );
          setTaskActiva(activa || null);
        }

        if (rF.ok) setFormatos(await rF.json());
      } catch {
        setError("No se pudo conectar con el backend");
      } finally {
        setLoading(false);
      }
    };

    cargar();
    interval = setInterval(cargar, 5000);
    return () => clearInterval(interval);
  }, [cc]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={40} className="animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto p-6 animate-fadeIn">
      {/* Cabecera */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">
            {paciente?.nombre || `Paciente CC ${cc}`}
          </h1>
          <p className="text-slate-500 mt-1">
            CC {cc}
            {paciente?.empresa ? ` · ${paciente.empresa}` : ""}
            {paciente?.siniestro ? ` · Siniestro ${paciente.siniestro}` : ""}
          </p>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm flex items-center gap-2">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {/* Tarea en progreso */}
      {taskActiva && (
        <div className="bg-blue-50 border-2 border-blue-200 p-6 rounded-2xl">
          <div className="flex items-center gap-3 mb-4">
            <Clock size={24} className="text-blue-600 animate-pulse" />
            <div>
              <h2 className="text-xl font-bold text-slate-800">Procesando...</h2>
              <p className="text-blue-700">{PASOS_LABELS[taskActiva.paso_actual] || taskActiva.estado}</p>
            </div>
            <span className="ml-auto text-lg font-bold text-blue-600">Paso {taskActiva.paso_actual}/10</span>
          </div>
          <div className="w-full bg-blue-200 rounded-full h-3">
            <div
              className="bg-blue-600 h-3 rounded-full transition-all duration-1000"
              style={{ width: `${Math.round((taskActiva.paso_actual / 10) * 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Sin datos */}
      {!paciente && !taskActiva && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-8 text-center">
          <FileText size={48} className="text-slate-300 mx-auto mb-4" />
          <p className="text-lg text-slate-600">No hay datos para CC {cc}</p>
          <p className="text-slate-400 mt-2">
            {taskActiva
              ? "El paciente esta siendo procesado. Los datos estaran disponibles pronto."
              : "Procesa un audio desde el chat para generar los datos y formatos."}
          </p>
        </div>
      )}

      {/* Datos del paciente */}
      {paciente && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="text-lg font-bold text-slate-700 mb-4">Datos del paciente</h2>
          <div className="grid grid-cols-2 gap-3 text-sm">
            {paciente.nombre && <div><span className="text-slate-400">Nombre:</span> <span className="font-medium">{paciente.nombre}</span></div>}
            {paciente.documento && <div><span className="text-slate-400">CC:</span> <span className="font-medium">{paciente.documento}</span></div>}
            {paciente.telefono && <div><span className="text-slate-400">Telefono:</span> <span className="font-medium">{paciente.telefono}</span></div>}
            {paciente.direccion && <div><span className="text-slate-400">Direccion:</span> <span className="font-medium">{paciente.direccion}</span></div>}
            {paciente.empresa && <div><span className="text-slate-400">Empresa:</span> <span className="font-medium">{paciente.empresa}</span></div>}
            {paciente.siniestro && <div><span className="text-slate-400">Siniestro:</span> <span className="font-medium">{paciente.siniestro}</span></div>}
            {paciente.estado_caso && <div><span className="text-slate-400">Estado:</span> <span className="font-medium">{paciente.estado_caso}</span></div>}
          </div>
        </div>
      )}

      {/* Formatos */}
      {formatos.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="text-lg font-bold text-slate-700 mb-4">Formatos generados ({formatos.length})</h2>
          <div className="space-y-2">
            {formatos.map((f: any, i: number) => {
              const nombreArchivo = f.archivo_docx ? f.archivo_docx.split("/").pop() : null;
              return (
                <div key={i} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                  <div>
                    <p className="font-medium text-slate-700">{f.nombre}</p>
                    <p className="text-xs text-slate-400">{f.fecha_generacion} · {f.estado}</p>
                  </div>
                  {nombreArchivo && (
                    <a
                      href={`${API}/api/download/${encodeURIComponent(nombreArchivo)}`}
                      download
                      className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
                    >
                      Descargar
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
