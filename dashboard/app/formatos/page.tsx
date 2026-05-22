"use client";

import { useState, useEffect, useCallback } from "react";
import {
  FileText, Download, History, FileArchive, CheckCircle,
  Clock, Eye, Loader2, RefreshCw, AlertCircle,
} from "lucide-react";
import { ConfianzaBadge } from "@/components/ConfianzaBadge";
import { ReconciliacionAlert } from "@/components/ReconciliacionAlert";

// Catálogo fijo de los 7 formatos
const CATALOGO = [
  { id: "1", nombre: "Análisis de Exigencias / Homologación", descripcion: "Visita al puesto de trabajo", fuente: "Positiva + Audio" },
  { id: "2", nombre: "Carta de Medidas Preventivas", descripcion: "Medidas para el trabajador", fuente: "Positiva + Audio" },
  { id: "3", nombre: "Carta de Recomendaciones / Reincorporación", descripcion: "Reintegro laboral", fuente: "Positiva + Medifolios" },
  { id: "4", nombre: "Cierre de Caso", descripcion: "Certificado de rehabilitación", fuente: "Positiva + Medifolios + Audio" },
  { id: "5", nombre: "Citación de Empresas", descripcion: "Notificar visita a empresa", fuente: "Positiva" },
  { id: "6", nombre: "Prueba de Trabajo", descripcion: "Evaluación en sitio", fuente: "Audio + Positiva" },
  { id: "7", nombre: "Valoración del Desempeño Ocupacional", descripcion: "Valoración final", fuente: "Positiva + Medifolios + Audio" },
];

interface FormatoAPI {
  id: string;
  nombre: string;
  estado: string;
  fecha_generacion?: string;
  archivo_docx?: string;
}

type EstadoFiltro = "todos" | "pendiente" | "generado" | "revisado" | "aprobado";

export default function FormatosPage() {
  const [filtro, setFiltro] = useState<EstadoFiltro>("todos");
  const [cc, setCc] = useState("");
  const [ccInput, setCcInput] = useState("");
  const [formatoExpandido, setFormatoExpandido] = useState<string | null>(null);
  const [formatosAPI, setFormatosAPI] = useState<FormatoAPI[]>([]);
  const [cargando, setCargando] = useState(false);
  const [generando, setGenerando] = useState(false);
  const [error, setError] = useState("");
  const [mensajeGeneracion, setMensajeGeneracion] = useState("");

  const cargarFormatos = useCallback(async (cedula: string) => {
    if (!cedula.trim()) return;
    setCargando(true);
    setError("");
    try {
      const res = await fetch(`/api/pacientes/${cedula.trim()}/formatos`);
      if (res.ok) {
        setFormatosAPI(await res.json());
      } else if (res.status === 404) {
        setFormatosAPI([]);
      } else {
        setError("Error al cargar formatos. ¿Está el backend corriendo?");
      }
    } catch {
      setError("No se pudo conectar con el servidor en localhost:8000.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargarFormatos(cc);
  }, [cc, cargarFormatos]);

  const buscar = () => {
    setCc(ccInput.trim());
  };

  const generarTodos = async () => {
    if (!cc.trim()) return;
    setGenerando(true);
    setMensajeGeneracion("");
    setError("");
    try {
      const res = await fetch(`/api/pacientes/${cc.trim()}/generar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setMensajeGeneracion(data.mensaje ?? "Formatos generados.");
        await cargarFormatos(cc);
      } else {
        setError(data.detail ?? data.mensaje ?? "Error al generar formatos.");
      }
    } catch {
      setError("No se pudo conectar con el servidor.");
    } finally {
      setGenerando(false);
    }
  };

  // Merge catálogo con datos reales de la API
  const apiMap = new Map<string, FormatoAPI>(formatosAPI.map((f) => [f.id, f]));
  const formatosMerged = CATALOGO.map((cat) => {
    const api = apiMap.get(cat.id);
    return {
      ...cat,
      estado: api?.estado ?? "pendiente",
      fecha_generacion: api?.fecha_generacion ?? null,
      archivo_docx: api?.archivo_docx ?? null,
    };
  });

  const formatosFiltrados = formatosMerged.filter(
    (f) => filtro === "todos" || f.estado === filtro
  );

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Formatos Clínicos</h1>
          <p className="text-slate-500 mt-1">7 formatos oficiales ARL Positiva · PDF/A para archivo legal</p>
        </div>
        <button
          onClick={generarTodos}
          disabled={generando || !cc.trim()}
          className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 transition-colors text-sm font-medium"
        >
          {generando ? <Loader2 size={18} className="animate-spin" /> : <FileText size={18} />}
          {generando ? "Generando..." : "Generar Todos"}
        </button>
      </div>

      {mensajeGeneracion && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-xl text-green-800 text-sm flex items-center gap-2">
          <CheckCircle size={16} /> {mensajeGeneracion}
        </div>
      )}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm flex items-center gap-2">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {/* Reconciliación */}
      {cc && formatosAPI.length > 0 && (
        <ReconciliacionAlert data={{ medifolios: "", positiva: "", coinciden: true, alerta: "" }} />
      )}

      {/* Paciente + Filtro */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2 bg-white rounded-lg border border-slate-200 px-3 py-2 text-sm">
          <span className="text-slate-500">CC:</span>
          <input
            type="text"
            value={ccInput}
            onChange={(e) => setCcInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && buscar()}
            className="w-32 px-2 py-0.5 border rounded text-sm outline-none focus:ring-1 focus:ring-blue-400"
          />
          <button
            onClick={buscar}
            disabled={cargando}
            className="p-1 text-slate-400 hover:text-blue-600 disabled:opacity-50"
            title="Recargar formatos"
          >
            {cargando ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          </button>
        </div>

        {(["todos", "pendiente", "generado", "revisado", "aprobado"] as EstadoFiltro[]).map((f) => (
          <button
            key={f}
            onClick={() => setFiltro(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filtro === f ? "bg-slate-800 text-white" : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}
          >
            {f === "todos" ? "Todos" : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Lista de formatos */}
      <div className="space-y-3">
        {formatosFiltrados.length === 0 && !cargando && (
          <div className="text-center py-8 text-slate-400 text-sm">
            No hay formatos con estado &quot;{filtro}&quot; para este paciente.
          </div>
        )}
        {formatosFiltrados.map((formato) => {
          const expandido = formatoExpandido === formato.id;
          const aprobado = formato.estado === "aprobado";
          const generado = formato.estado === "generado";
          const nombreArchivo = formato.archivo_docx ? formato.archivo_docx.split("/").pop() : null;

          return (
            <div
              key={formato.id}
              className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-md transition-shadow"
            >
              <div className="p-5">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4 flex-1">
                    <div className={`p-2.5 rounded-lg ${aprobado ? "bg-green-100" : generado ? "bg-blue-100" : "bg-slate-100"}`}>
                      <FileText
                        size={22}
                        className={aprobado ? "text-green-600" : generado ? "text-blue-600" : "text-slate-400"}
                      />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-semibold text-slate-800">
                          Formato {formato.id}: {formato.nombre}
                        </h3>
                        {aprobado && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs">
                            <CheckCircle size={12} /> Aprobado
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-500 mt-0.5">{formato.descripcion}</p>
                      <div className="flex items-center gap-3 mt-2 flex-wrap">
                        <span className="text-xs text-slate-400">Fuente: {formato.fuente}</span>
                        <EstadoBadge estado={formato.estado} />
                        {formato.fecha_generacion && (
                          <span className="text-xs text-slate-400 flex items-center gap-1">
                            <Clock size={11} /> {formato.fecha_generacion}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 flex-shrink-0">
                    {nombreArchivo && (
                      <a
                        href={`/api/download/${encodeURIComponent(nombreArchivo)}`}
                        download
                        className="p-2 text-slate-400 hover:text-green-600 rounded-lg transition-colors"
                        title="Descargar DOCX"
                      >
                        <Download size={18} />
                      </a>
                    )}
                    {!nombreArchivo && (
                      <button
                        disabled
                        className="p-2 text-slate-200 rounded-lg cursor-not-allowed"
                        title="No generado aún"
                      >
                        <Download size={18} />
                      </button>
                    )}
                    <button
                      onClick={() => setFormatoExpandido(expandido ? null : formato.id)}
                      className="p-2 text-slate-400 hover:text-amber-600 rounded-lg transition-colors"
                      title="Historial"
                    >
                      <History size={18} />
                    </button>
                  </div>
                </div>

                {expandido && (
                  <div className="mt-4 pt-4 border-t border-slate-100 space-y-2">
                    <h4 className="text-sm font-semibold text-slate-700">Archivo DOCX</h4>
                    {formato.archivo_docx ? (
                      <div className="text-xs text-slate-500 font-mono bg-slate-50 rounded px-3 py-2 break-all">
                        {formato.archivo_docx}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400">Aún no se ha generado este formato.</p>
                    )}
                    <p className="text-xs text-slate-400 mt-1">
                      Haz click en &quot;Generar Todos&quot; para crear los formatos disponibles para CC {cc}.
                    </p>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function EstadoBadge({ estado }: { estado: string }) {
  const colors: Record<string, string> = {
    pendiente: "bg-slate-100 text-slate-600",
    generado: "bg-blue-100 text-blue-700",
    revisado: "bg-amber-100 text-amber-700",
    rechazado: "bg-red-100 text-red-700",
    aprobado: "bg-green-100 text-green-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[estado] ?? colors.pendiente}`}>
      {estado}
    </span>
  );
}
