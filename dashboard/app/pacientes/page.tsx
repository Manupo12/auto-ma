"use client";

import { useState } from "react";
import { Search, User, Phone, Mail, MapPin, FileText, Loader2 } from "lucide-react";
import type { Paciente, FormatoInfo } from "@/lib/api";

export default function PacientesPage() {
  const [cc, setCc] = useState("");
  const [buscando, setBuscando] = useState(false);
  const [paciente, setPaciente] = useState<Paciente | null>(null);
  const [formatos, setFormatos] = useState<FormatoInfo[]>([]);
  const [error, setError] = useState("");

  const buscar = async () => {
    if (!cc.trim()) return;
    setBuscando(true);
    setError("");
    setPaciente(null);
    setFormatos([]);
    try {
      const [resPac, resFmt] = await Promise.all([
        fetch(`/api/pacientes/${cc.trim()}`),
        fetch(`/api/pacientes/${cc.trim()}/formatos`),
      ]);

      if (resPac.status === 404) {
        setError("Paciente no encontrado. Verifica la cédula.");
        return;
      }
      if (!resPac.ok) {
        setError("Error al conectar con el servidor. ¿Está el backend corriendo?");
        return;
      }

      const pacData = await resPac.json();
      setPaciente(pacData);

      if (resFmt.ok) {
        const fmtData = await resFmt.json();
        setFormatos(fmtData);
      }
    } catch {
      setError("No se pudo conectar con el servidor en el servidor.");
    } finally {
      setBuscando(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Pacientes</h1>
        <p className="text-slate-500 mt-1">Busca un paciente por número de documento</p>
      </div>

      {/* Search */}
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={cc}
            onChange={(e) => setCc(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && buscar()}
            placeholder="Número de cédula..."
            className="w-full pl-10 pr-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
          />
        </div>
        <button
          onClick={buscar}
          disabled={buscando}
          className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
        >
          {buscando ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
          Buscar
        </button>
      </div>

      {error && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-sm">
          {error}
        </div>
      )}

      {/* Patient card */}
      {paciente && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="p-6 bg-gradient-to-r from-blue-600 to-blue-700 text-white">
            <h2 className="text-xl font-bold">{paciente.nombre}</h2>
            <p className="text-blue-200">CC {paciente.documento} • {paciente.edad} años</p>
            {paciente.estado_caso && (
              <span className="inline-block mt-2 px-3 py-1 bg-white/20 rounded-full text-sm">
                {paciente.estado_caso}
              </span>
            )}
          </div>
          
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            <InfoRow icon={Phone} label="Teléfono" value={paciente.telefono} />
            <InfoRow icon={Mail} label="Email" value={paciente.email} />
            <InfoRow icon={MapPin} label="Dirección" value={paciente.direccion} />
            <InfoRow icon={User} label="EPS" value={paciente.eps_ips} />
            <InfoRow icon={User} label="AFP" value={paciente.afp} />
            <InfoRow icon={User} label="Empresa" value={paciente.empresa} />
            <InfoRow icon={FileText} label="Siniestro" value={paciente.siniestro} />
          </div>
        </div>
      )}

      {/* Formatos del paciente */}
      {formatos.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">Formatos del Paciente</h2>
          <div className="space-y-3">
            {formatos.map((f) => (
              <div
                key={f.id}
                className="flex items-center justify-between p-3 bg-slate-50 rounded-lg"
              >
                <div>
                  <p className="font-medium text-slate-800">Formato {f.id}: {f.nombre}</p>
                  {f.fecha_generacion && (
                    <p className="text-xs text-slate-500">Generado: {f.fecha_generacion}</p>
                  )}
                </div>
                <EstadoBadge estado={f.estado} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function InfoRow({ icon: Icon, label, value }: { icon: any; label: string; value?: string }) {
  return (
    <div className="flex items-center gap-3">
      <Icon size={16} className="text-slate-400 flex-shrink-0" />
      <div>
        <p className="text-xs text-slate-500">{label}</p>
        <p className="text-sm font-medium text-slate-800">{value || "—"}</p>
      </div>
    </div>
  );
}

function EstadoBadge({ estado }: { estado: string }) {
  const colors: Record<string, string> = {
    pendiente: "bg-slate-100 text-slate-700",
    generado: "bg-blue-100 text-blue-700",
    revisado: "bg-amber-100 text-amber-700",
    aprobado: "bg-green-100 text-green-700",
    rechazado: "bg-red-100 text-red-700",
  };
  return (
    <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${colors[estado] || colors.pendiente}`}>
      {estado}
    </span>
  );
}
