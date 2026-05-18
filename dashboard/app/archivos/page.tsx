"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import MobileMenu from "@/components/MobileMenu";

interface ArchivoItem {
  nombre: string;
  tipo: "carpeta" | "archivo";
  icono: string;
  tamano: number;
  modificado: string;
  contenido?: number;
}

export default function ArchivosPage() {
  const [archivos, setArchivos] = useState<ArchivoItem[]>([]);
  const [path, setPath] = useState("");
  const [agenda, setAgenda] = useState<any>(null);
  const [cargando, setCargando] = useState(true);
  const [syncMsg, setSyncMsg] = useState("");

  useEffect(() => {
    cargarArchivos();
    cargarAgenda();
  }, []);

  const cargarArchivos = async (subpath?: string) => {
    try {
      const url = subpath
        ? `http://localhost:8000/api/archivos?path=${encodeURIComponent(subpath)}`
        : "http://localhost:8000/api/archivos";
      const resp = await fetch(url);
      const data = await resp.json();
      if (data.ok) {
        setArchivos(data.archivos || []);
        setPath(data.path || "");
      }
    } catch (e) {
      console.error("Error cargando archivos:", e);
    }
    setCargando(false);
  };

  const cargarAgenda = async () => {
    try {
      const resp = await fetch("http://localhost:8000/api/agenda");
      const data = await resp.json();
      if (data.ok && data.citas?.length > 0) {
        setAgenda(data);
      }
    } catch (e) {
      // Silencioso si no hay agenda
    }
  };

  const forzarSync = async () => {
    setSyncMsg("⏳ Sincronizando...");
    try {
      const resp = await fetch("http://localhost:8000/api/archivos/sync", {
        method: "POST",
      });
      const data = await resp.json();
      if (data.ok) {
        setSyncMsg("✅ Sincronizado con GitHub");
        cargarArchivos();
      } else {
        setSyncMsg("❌ " + (data.error || "Error"));
      }
    } catch (e) {
      setSyncMsg("❌ Error de conexión");
    }
    setTimeout(() => setSyncMsg(""), 5000);
  };

  const forzarCheckAgenda = async () => {
    setSyncMsg("⏳ Revisando agenda...");
    try {
      const resp = await fetch("http://localhost:8000/api/agenda/check", {
        method: "POST",
      });
      const data = await resp.json();
      if (data.ok) {
        setSyncMsg(
          `✅ ${data.total || 0} citas encontradas para ${data.fecha || "mañana"}`
        );
        cargarAgenda();
      } else {
        setSyncMsg("❌ " + (data.mensaje || "Error"));
      }
    } catch (e) {
      setSyncMsg("❌ Error de conexión");
    }
    setTimeout(() => setSyncMsg(""), 5000);
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
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const formatearFecha = (fecha: string) => {
    try {
      const d = new Date(fecha);
      return d.toLocaleString("es-CO", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return fecha;
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a1a] text-white font-mono">
      <Sidebar />
      <MobileMenu />
      <div className="lg:ml-64 p-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
          <div>
            <h1 className="text-2xl font-bold text-purple-400">
              📁 Archivos de Trabajo
            </h1>
            <p className="text-gray-500 text-sm mt-1">
              {path ? (
                <span
                  className="cursor-pointer hover:text-purple-400"
                  onClick={volver}
                >
                  ← {path}
                </span>
              ) : (
                "Carpeta principal de Sandra"
              )}
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={forzarCheckAgenda}
              className="px-4 py-2 bg-blue-600/20 border border-blue-500/30 rounded-lg 
                         text-blue-400 text-sm hover:bg-blue-600/30 transition-all"
            >
              📅 Revisar Agenda
            </button>
            <button
              onClick={forzarSync}
              className="px-4 py-2 bg-purple-600/20 border border-purple-500/30 rounded-lg 
                         text-purple-400 text-sm hover:bg-purple-600/30 transition-all"
            >
              🔄 Sincronizar
            </button>
          </div>
        </div>

        {/* Sync status */}
        {syncMsg && (
          <div className="mb-4 px-4 py-3 bg-gray-800/50 border border-gray-700 rounded-lg text-sm text-gray-300">
            {syncMsg}
          </div>
        )}

        {/* Agenda info */}
        {agenda && (
          <div className="mb-6 p-4 bg-blue-900/20 border border-blue-800/30 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">📅</span>
              <span className="font-semibold text-blue-300">
                Próxima Agenda: {agenda.fecha}
              </span>
              <span className="bg-blue-600/30 text-blue-300 text-xs px-2 py-0.5 rounded-full">
                {agenda.total} citas
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {agenda.citas?.slice(0, 6).map((c: any, i: number) => (
                <div
                  key={i}
                  className="text-xs text-gray-400 bg-gray-900/30 px-2 py-1 rounded flex items-center gap-2"
                >
                  {c.es_nueva && (
                    <span className="text-green-400 font-bold text-[10px] bg-green-900/50 px-1 rounded">
                      NUEVO
                    </span>
                  )}
                  ⏰ {c.hora} — {c.paciente}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Archivos */}
        {cargando ? (
          <div className="text-center py-12 text-gray-500">
            <span className="animate-pulse">Cargando archivos...</span>
          </div>
        ) : archivos.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <p className="text-4xl mb-3">📭</p>
            <p>
              No hay archivos aquí.
              {!path && " La carpeta de trabajo aún no se ha configurado."}
            </p>
            {!path && (
              <p className="text-sm mt-2 text-gray-600">
                Configura WORKSPACE_DIR en .env o crea ~/rilo-workspace
              </p>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {path && (
              <button
                onClick={volver}
                className="p-4 bg-gray-800/30 border border-gray-700/30 rounded-lg 
                           hover:bg-gray-800/50 transition-all text-left flex items-center gap-3"
              >
                <span className="text-2xl">⬆️</span>
                <span className="text-gray-400 text-sm">Volver atrás</span>
              </button>
            )}
            {archivos.map((item, i) => (
              <button
                key={i}
                onClick={() =>
                  item.tipo === "carpeta" ? abrirCarpeta(item.nombre) : null
                }
                className={`p-4 rounded-lg border transition-all text-left
                  ${
                    item.tipo === "carpeta"
                      ? "bg-gray-800/20 border-yellow-700/20 hover:bg-gray-800/40 hover:border-yellow-600/40 cursor-pointer"
                      : "bg-gray-800/10 border-gray-700/10 cursor-default"
                  }`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{item.icono}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-gray-200 truncate font-medium">
                      {item.nombre}
                    </p>
                    <p className="text-[10px] text-gray-600">
                      {item.tipo === "carpeta"
                        ? `${item.contenido || 0} archivos`
                        : formatearTamano(item.tamano)}
                      {" · "}
                      {formatearFecha(item.modificado)}
                    </p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
