"use client";

import { useState, useEffect } from "react";
import {
  Folder, FileText, File, RefreshCw, Calendar, Loader2,
  ChevronLeft, AlertCircle, CheckCircle, Clock, ArrowRight,
} from "lucide-react";

interface ArchivoItem {
  nombre: string;
  tipo: "carpeta" | "archivo";
  icono: string;
  tamano: number;
  modificado: string;
  contenido?: number;
}

interface Cita {
  hora: string;
  paciente: string;
  es_nueva?: boolean;
}

interface AgendaData {
  fecha: string;
  total: number;
  citas: Cita[];
}

export default function ArchivosPage() {
  const [archivos, setArchivos] = useState<ArchivoItem[]>([]);
  const [path, setPath] = useState("");
  const [agenda, setAgenda] = useState<AgendaData | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [syncMsg, setSyncMsg] = useState("");
  const [syncOk, setSyncOk] = useState<boolean | null>(null);

  useEffect(() => {
    cargarArchivos();
    cargarAgenda();
  }, []);

  const cargarArchivos = async (subpath?: string) => {
    setCargando(true);
    setError("");
    try {
      const url = subpath
        ? `/api/archivos?path=${encodeURIComponent(subpath)}`
        : "/api/archivos";
      const resp = await fetch(url);
      const data = await resp.json();
      if (data.ok) {
        setArchivos(data.archivos || []);
        setPath(data.path || "");
      } else {
        setError(data.detail || "Error al cargar archivos");
      }
    } catch {
      setError("No se pudo cargar archivos. Revisa que el servidor este corriendo.");
    } finally {
      setCargando(false);
    }
  };

  const cargarAgenda = async () => {
    try {
      const resp = await fetch("/api/agenda");
      const data = await resp.json();
      if (data.ok && data.citas?.length > 0) {
        setAgenda(data as AgendaData);
      }
    } catch {
      // silencioso
    }
  };

  const mostrarMensaje = (msg: string, ok: boolean) => {
    setSyncMsg(msg);
    setSyncOk(ok);
    setTimeout(() => { setSyncMsg(""); setSyncOk(null); }, 5000);
  };

  const forzarSync = async () => {
    mostrarMensaje("Sincronizando...", true);
    try {
      const resp = await fetch("/api/archivos/sync", { method: "POST" });
      const data = await resp.json();
      if (data.ok) {
        mostrarMensaje("Sincronizado con GitHub", true);
        cargarArchivos(path || undefined);
      } else {
        mostrarMensaje(data.error || "Error al sincronizar", false);
      }
    } catch {
      mostrarMensaje("Error de conexión", false);
    }
  };

  const forzarCheckAgenda = async () => {
    mostrarMensaje("Revisando agenda...", true);
    try {
      const resp = await fetch("/api/agenda/check", { method: "POST" });
      const data = await resp.json();
      if (data.ok) {
        mostrarMensaje(
          `${data.total || 0} citas encontradas para ${data.fecha || "mañana"}`,
          true
        );
        cargarAgenda();
      } else {
        mostrarMensaje(data.mensaje || "Error al revisar agenda", false);
      }
    } catch {
      mostrarMensaje("Error de conexión", false);
    }
  };

  const abrirCarpeta = (nombre: string) => {
    const nuevoPath = path ? `${path}/${nombre}` : nombre;
    cargarArchivos(nuevoPath);
  };

  const volver = () => {
    if (!path) return;
    const partes = path.split("/");
    partes.pop();
    const nuevoPath = partes.join("/");
    cargarArchivos(nuevoPath || undefined);
  };

  const formatearTamano = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatearFecha = (fecha: string) => {
    try {
      return new Date(fecha).toLocaleString("es-CO", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return fecha;
    }
  };

  const iconoArchivo = (item: ArchivoItem) => {
    if (item.tipo === "carpeta") return <Folder size={20} className="text-amber-500 flex-shrink-0" />;
    if (item.nombre.endsWith(".docx") || item.nombre.endsWith(".doc"))
      return <FileText size={20} className="text-blue-500 flex-shrink-0" />;
    return <File size={20} className="text-slate-400 flex-shrink-0" />;
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Archivos de Trabajo</h1>
          <p className="text-slate-500 mt-1">
            Carpeta de trabajo de Sandra · Documentos y expedientes
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={forzarCheckAgenda}
            className="flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-slate-600 hover:bg-slate-50 text-sm font-medium transition-colors"
          >
            <Calendar size={16} />
            Revisar Agenda
          </button>
          <button
            onClick={forzarSync}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 text-sm font-medium transition-colors"
          >
            <RefreshCw size={16} />
            Sincronizar
          </button>
        </div>
      </div>

      {syncMsg && (
        <div className={`p-3 rounded-xl text-sm flex items-center gap-2 border ${
          syncOk === false
            ? "bg-red-50 border-red-200 text-red-800"
            : "bg-green-50 border-green-200 text-green-800"
        }`}>
          {syncOk === false ? <AlertCircle size={16} /> : <CheckCircle size={16} />}
          {syncMsg}
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm flex items-center gap-2">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {agenda && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Calendar size={16} className="text-blue-600" />
            <span className="font-semibold text-blue-800 text-sm">
              Agenda: {agenda.fecha}
            </span>
            <span className="bg-blue-600 text-white text-xs px-2 py-0.5 rounded-full">
              {agenda.total} citas
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {agenda.citas?.slice(0, 6).map((c, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-blue-700 bg-white/70 px-2 py-1.5 rounded-lg">
                {c.es_nueva && (
                  <span className="text-green-700 font-bold text-[10px] bg-green-100 px-1 rounded">
                    NUEVO
                  </span>
                )}
                <Clock size={11} className="flex-shrink-0" />
                <span>{c.hora} — {c.paciente}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="p-4 bg-slate-50 border-b flex items-center gap-2">
          {path ? (
            <button
              onClick={volver}
              className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-blue-600 transition-colors"
            >
              <ChevronLeft size={16} />
              <span className="font-mono text-xs">{path}</span>
            </button>
          ) : (
            <span className="text-sm text-slate-600 font-medium">Carpeta raíz</span>
          )}
          {cargando && <Loader2 size={14} className="animate-spin text-slate-400 ml-auto" />}
        </div>

        {cargando ? (
          <div className="py-16 text-center text-slate-400 text-sm">
            <Loader2 size={24} className="animate-spin mx-auto mb-3" />
            Cargando archivos...
          </div>
        ) : archivos.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm space-y-2">
            <Folder size={40} className="mx-auto text-slate-300" />
            <p>No hay archivos aquí.</p>
            {!path && (
              <p className="text-xs text-slate-400">
                Configura <code className="bg-slate-100 px-1 rounded">WORKSPACE_DIR</code> en .env
                o crea <code className="bg-slate-100 px-1 rounded">~/rilo-workspace</code>
              </p>
            )}
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {archivos.map((item, i) => (
              <div
                key={i}
                onClick={() => item.tipo === "carpeta" ? abrirCarpeta(item.nombre) : undefined}
                className={`flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors ${
                  item.tipo === "carpeta" ? "cursor-pointer" : "cursor-default"
                }`}
              >
                {iconoArchivo(item)}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-700 truncate">{item.nombre}</p>
                  <p className="text-xs text-slate-400">
                    {item.tipo === "carpeta"
                      ? `${item.contenido ?? 0} archivos`
                      : formatearTamano(item.tamano)}
                    {" · "}
                    {formatearFecha(item.modificado)}
                  </p>
                </div>
                {item.tipo === "carpeta" && (
                  <ArrowRight size={14} className="text-slate-300 flex-shrink-0" />
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
