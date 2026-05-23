"use client";

import { useState, useEffect, useCallback } from "react";
import {
  FileText, Download, Loader2, AlertCircle, CheckCircle,
  Search, Trash2, User, Filter, ChevronDown, ChevronRight,
} from "lucide-react";

interface PacienteInfo {
  documento: string;
  nombre: string;
  empresa?: string;
  siniestro?: string;
}

interface FormatoInfo {
  id: string;
  nombre: string;
  estado: string;
  fecha_generacion?: string;
  archivo_docx?: string;
}

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const NOMBRES_FORMATOS: Record<string, string> = {
  "1": "Analisis de Exigencias",
  "2": "Carta de Medidas Preventivas",
  "3": "Carta de Recomendaciones",
  "4": "Cierre de Caso",
  "5": "Citacion de Empresas",
  "6": "Prueba de Trabajo",
  "7": "VOI - Valoracion Ocupacional",
};

const COLORES_ESTADO: Record<string, string> = {
  generado: "bg-blue-100 text-blue-700",
  revisado: "bg-amber-100 text-amber-700",
  aprobado: "bg-green-100 text-green-700",
};

export default function FormatosPage() {
  const [pacientes, setPacientes] = useState<PacienteInfo[]>([]);
  const [pacienteSeleccionado, setPacienteSeleccionado] = useState("");
  const [formatos, setFormatos] = useState<FormatoInfo[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [filtroFormato, setFiltroFormato] = useState("");
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());
  const [eliminando, setEliminando] = useState(false);
  const [showDelete, setShowDelete] = useState<string | null>(null);

  const cargarPacientes = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/pacientes`);
      if (r.ok) setPacientes(await r.json());
    } catch {}
  }, []);

  const cargarFormatos = useCallback(async (cc: string) => {
    if (!cc) { setFormatos([]); return; }
    setCargando(true);
    setError("");
    try {
      const r = await fetch(`${API}/api/pacientes/${cc}/formatos`);
      if (r.ok) setFormatos(await r.json());
      else if (r.status === 404) setFormatos([]);
      else setError("Error al cargar formatos");
    } catch {
      setError("No se pudo conectar con el backend");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => { cargarPacientes(); }, [cargarPacientes]);

  const seleccionarPaciente = (cc: string) => {
    setPacienteSeleccionado(cc);
    cargarFormatos(cc);
    setFiltroFormato("");
  };

  const eliminarPaciente = async (cc: string) => {
    setEliminando(true);
    try {
      await fetch(`${API}/api/pacientes/${cc}`, { method: "DELETE" });
      setPacientes(p => p.filter(pa => pa.documento !== cc));
      setPacienteSeleccionado("");
      setFormatos([]);
      setShowDelete(null);
    } catch {
      setError("No se pudo eliminar el paciente");
    } finally {
      setEliminando(false);
    }
  };

  const formatosFiltrados = filtroFormato
    ? formatos.filter(f => f.id === filtroFormato || f.nombre?.toLowerCase().includes(filtroFormato.toLowerCase()))
    : formatos;

  const pacienteActual = pacientes.find(p => p.documento === pacienteSeleccionado);

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Documentos</h1>
          <p className="text-slate-500 mt-1">Formatos organizados por paciente</p>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm flex items-center gap-2">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Lista de pacientes - izquierda */}
        <div className="lg:col-span-1 bg-white rounded-xl border border-slate-200 p-4">
          <h2 className="font-semibold text-slate-700 mb-3 flex items-center gap-2">
            <User size={18} /> Pacientes ({pacientes.length})
          </h2>
          <div className="space-y-1 max-h-[60vh] overflow-y-auto">
            {pacientes.map(p => (
              <button
                key={p.documento}
                onClick={() => seleccionarPaciente(p.documento)}
                className={`w-full text-left p-3 rounded-lg transition-colors ${
                  pacienteSeleccionado === p.documento
                    ? "bg-blue-600 text-white"
                    : "hover:bg-slate-50 text-slate-700"
                }`}
              >
                <p className="font-medium text-sm">{p.nombre || `CC ${p.documento}`}</p>
                <p className={`text-xs mt-0.5 ${pacienteSeleccionado === p.documento ? "text-blue-200" : "text-slate-400"}`}>
                  CC {p.documento}
                  {p.siniestro ? ` · Siniestro ${p.siniestro}` : ""}
                </p>
              </button>
            ))}
            {pacientes.length === 0 && (
              <p className="text-sm text-slate-400 text-center py-4">Sin pacientes cargados</p>
            )}
          </div>
        </div>

        {/* Formatos - derecha */}
        <div className="lg:col-span-3">
          {!pacienteSeleccionado ? (
            <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
              <FileText size={48} className="text-slate-300 mx-auto mb-4" />
              <p className="text-lg text-slate-500">Selecciona un paciente para ver sus documentos</p>
            </div>
          ) : (
            <>
              {/* Cabecera paciente */}
              <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex items-center justify-between flex-wrap gap-3">
                <div>
                  <h2 className="text-xl font-bold text-slate-800">
                    {pacienteActual?.nombre || `CC ${pacienteSeleccionado}`}
                  </h2>
                  <p className="text-sm text-slate-500">
                    CC {pacienteSeleccionado}
                    {pacienteActual?.empresa ? ` · ${pacienteActual.empresa}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {/* Filtro formato */}
                  <select
                    value={filtroFormato}
                    onChange={(e) => setFiltroFormato(e.target.value)}
                    className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  >
                    <option value="">Todos los formatos ({formatos.length})</option>
                    {Object.entries(NOMBRES_FORMATOS).map(([id, nombre]) => (
                      <option key={id} value={id}>{id}. {nombre}</option>
                    ))}
                  </select>

                  {/* Boton eliminar */}
                  <button
                    onClick={() => setShowDelete(pacienteSeleccionado)}
                    className="flex items-center gap-1 px-3 py-2 text-sm text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 size={16} /> Eliminar
                  </button>
                </div>
              </div>

              {/* Lista de formatos */}
              {cargando ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 size={32} className="animate-spin text-blue-500" />
                </div>
              ) : formatosFiltrados.length === 0 ? (
                <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
                  <FileText size={48} className="text-slate-300 mx-auto mb-4" />
                  <p className="text-lg text-slate-500">
                    {filtroFormato ? "No hay formatos de ese tipo" : "Sin formatos generados"}
                  </p>
                  <p className="text-sm text-slate-400 mt-2">
                    Subi un audio desde el chat para generar formatos
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {formatosFiltrados.map((f, i) => {
                    const nombreArchivo = f.archivo_docx ? f.archivo_docx.split("/").pop() : null;
                    return (
                      <div key={i} className="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md transition-shadow">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span className="text-lg font-bold text-slate-400">#{f.id}</span>
                            <div>
                              <h3 className="font-semibold text-slate-800">{f.nombre}</h3>
                              <div className="flex items-center gap-2 mt-1">
                                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${COLORES_ESTADO[f.estado] || "bg-slate-100 text-slate-600"}`}>
                                  {f.estado}
                                </span>
                                {f.fecha_generacion && (
                                  <span className="text-xs text-slate-400">{f.fecha_generacion}</span>
                                )}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {nombreArchivo ? (
                              <a
                                href={`${API}/api/download/${encodeURIComponent(nombreArchivo)}`}
                                download
                                className="flex items-center gap-1 px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
                              >
                                <Download size={14} /> DOCX
                              </a>
                            ) : (
                              <span className="px-3 py-2 bg-slate-100 text-slate-400 rounded-lg text-sm">
                                Pendiente
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Modal confirmacion eliminar */}
      {showDelete && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center">
          <div className="bg-white rounded-2xl p-6 w-96 shadow-2xl space-y-4">
            <div className="text-center">
              <Trash2 size={40} className="text-red-500 mx-auto mb-2" />
              <h2 className="font-bold text-lg">Eliminar paciente?</h2>
              <p className="text-slate-500 text-sm mt-1">
                Esto borrara CC {showDelete}: todos los formatos, PDFs, datos e historial de chat.
                <br /><strong>Esta accion no se puede deshacer.</strong>
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setShowDelete(null)}
                className="flex-1 py-2 border border-slate-300 rounded-xl text-slate-600"
              >
                Cancelar
              </button>
              <button
                onClick={() => eliminarPaciente(showDelete)}
                disabled={eliminando}
                className="flex-1 py-2 bg-red-600 text-white rounded-xl hover:bg-red-700 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {eliminando ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                {eliminando ? "Eliminando..." : "Eliminar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
