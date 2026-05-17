"use client";

import { useState } from "react";
import {
  Upload, Mic, FileAudio, Loader2, Clock,
  User, UserCheck, ArrowRight, AlertCircle,
} from "lucide-react";
import { ConfianzaBadge, SemaforoIcon } from "@/components/ConfianzaBadge";

interface SegmentoAudio {
  texto: string;
  inicio: string;
  hablante: string;
  confianza: number;
}

interface CampoExtraido {
  campo: string;
  valor: string;
  confianza: number;
  fuente: string;
}

const CAMPO_LABELS: Record<string, string> = {
  metodologia: "Metodología",
  proceso_productivo: "Proceso productivo / Funciones",
  apreciacion_trabajador: "Apreciación del trabajador",
  estandares_productividad: "Estándares de productividad",
  concepto_desempeno: "Concepto de desempeño",
};

export default function SubirAudioPage() {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [cc, setCc] = useState("");
  const [subiendo, setSubiendo] = useState(false);
  const [completado, setCompletado] = useState(false);
  const [segmentos, setSegmentos] = useState<SegmentoAudio[]>([]);
  const [camposExtraidos, setCamposExtraidos] = useState<CampoExtraido[]>([]);
  const [confianzaGlobal, setConfianzaGlobal] = useState(0);
  const [duracion, setDuracion] = useState(0);
  const [error, setError] = useState("");

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && (file.type.startsWith("audio/") || file.name.endsWith(".m4a"))) {
      setArchivo(file);
      setCompletado(false);
      setError("");
    }
  };

  const subir = async () => {
    if (!archivo || !cc.trim()) return;
    setSubiendo(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("audio", archivo);
      formData.append("paciente_cc", cc.trim());

      const res = await fetch("/api/upload-audio", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? body.error ?? `Error ${res.status}`);
      }

      const data = await res.json();

      // Segmentos (frases agrupadas por hablante)
      if (data.segmentos?.length > 0) {
        setSegmentos(
          data.segmentos.map((s: { texto: string; inicio: number; hablante: number }) => ({
            texto: s.texto,
            inicio: new Date(s.inicio * 1000).toISOString().substring(14, 19),
            hablante: s.hablante === 0 ? "Sandra (Speaker 0)" : "Paciente (Speaker 1)",
            confianza: Math.round((data.confianza ?? 0.9) * 100),
          }))
        );
      }

      // Campos extraídos del texto transcrito
      const campos: CampoExtraido[] = [];
      const de = data.datos_extraidos ?? {};
      const confBase = Math.round((data.confianza ?? 0.85) * 100);

      for (const [key, label] of Object.entries(CAMPO_LABELS)) {
        const val = de[key];
        if (val && typeof val === "string" && val.trim()) {
          campos.push({ campo: label, valor: val.trim(), confianza: confBase, fuente: "audio" });
        }
      }
      // Materiales como lista
      if (Array.isArray(de.materiales) && de.materiales.length > 0) {
        campos.push({
          campo: "Materiales / Herramientas",
          valor: de.materiales.map((m: { nombre: string }) => m.nombre).join(", "),
          confianza: confBase,
          fuente: "audio",
        });
      }
      // Peligros como lista
      if (Array.isArray(de.peligros) && de.peligros.length > 0) {
        campos.push({
          campo: "Peligros identificados",
          valor: de.peligros.map((p: { nombre: string }) => p.nombre).join(", "),
          confianza: confBase,
          fuente: "audio",
        });
      }
      // Recomendaciones
      const rec = de.recomendaciones ?? {};
      if (rec.trabajador) {
        campos.push({ campo: "Recomendaciones trabajador", valor: rec.trabajador, confianza: confBase, fuente: "audio" });
      }
      if (rec.empresa) {
        campos.push({ campo: "Recomendaciones empresa", valor: rec.empresa, confianza: confBase, fuente: "audio" });
      }

      setCamposExtraidos(campos);
      setConfianzaGlobal(confBase);
      setDuracion(Math.round(data.duracion ?? 0));
      setCompletado(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido.");
    } finally {
      setSubiendo(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Subir Audio de Cita</h1>
        <p className="text-slate-500 mt-1">
          Graba la consulta con tu iPhone. Deepgram transcribe, identifica quién habla (Sandra vs paciente),
          y extrae los datos para los formatos con nivel de confianza.
        </p>
      </div>

      {/* Paciente */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <label className="block text-sm font-medium text-slate-700 mb-2">Cédula del Paciente</label>
        <input
          type="text"
          value={cc}
          onChange={(e) => setCc(e.target.value)}
          placeholder="Ej: 1193143688"
          className="w-full px-4 py-2.5 rounded-xl border border-slate-300 focus:ring-2 focus:ring-blue-500 outline-none"
        />
      </div>

      {/* Upload */}
      <div className="bg-white rounded-xl border-2 border-dashed border-slate-300 p-8 text-center hover:border-purple-400 transition-colors">
        <input
          type="file"
          accept="audio/*,.m4a,.mp3,.wav"
          onChange={handleFile}
          className="hidden"
          id="audio-upload"
        />
        <label htmlFor="audio-upload" className="cursor-pointer">
          {archivo ? (
            <div className="space-y-3">
              <FileAudio size={48} className="mx-auto text-purple-500" />
              <p className="font-medium text-slate-800">{archivo.name}</p>
              <p className="text-sm text-slate-500">{(archivo.size / 1024 / 1024).toFixed(1)} MB</p>
            </div>
          ) : (
            <div className="space-y-3">
              <Upload size={48} className="mx-auto text-slate-400" />
              <p className="font-medium text-slate-600">Arrastra el audio o haz click</p>
              <p className="text-sm text-slate-400">M4A, MP3, WAV — Máx 50 MB</p>
            </div>
          )}
        </label>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm flex items-center gap-2">
          <AlertCircle size={16} className="flex-shrink-0" />
          {error}
        </div>
      )}

      <button
        onClick={subir}
        disabled={!archivo || !cc.trim() || subiendo}
        className="w-full flex items-center justify-center gap-2 px-6 py-3.5 bg-purple-600 text-white rounded-xl hover:bg-purple-700 disabled:opacity-50 font-medium transition-colors"
      >
        {subiendo ? (
          <><Loader2 size={20} className="animate-spin" /> Transcribiendo con Deepgram (nova-2)...</>
        ) : (
          <><Mic size={20} /> Transcribir Audio</>
        )}
      </button>

      {/* Resultados */}
      {completado && (
        <div className="space-y-4">
          {/* Resumen */}
          <div className="flex items-center gap-4 p-3 bg-slate-50 rounded-xl text-sm text-slate-600 flex-wrap">
            <span>Duración: <strong>{Math.floor(duracion / 60)}:{String(duracion % 60).padStart(2, "0")} min</strong></span>
            <span>Confianza global: <ConfianzaBadge confianza={confianzaGlobal} size="sm" /></span>
            <span>{segmentos.length} segmentos · {camposExtraidos.length} campos extraídos</span>
          </div>

          {/* Transcripción por hablante */}
          {segmentos.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="p-4 bg-slate-50 border-b flex items-center justify-between">
                <h3 className="font-semibold text-slate-800">Transcripción · Speaker Diarization</h3>
                <div className="flex items-center gap-4 text-xs">
                  <span className="flex items-center gap-1"><UserCheck size={14} className="text-blue-500" /> Sandra</span>
                  <span className="flex items-center gap-1"><User size={14} className="text-purple-500" /> Paciente</span>
                </div>
              </div>
              <div className="divide-y max-h-80 overflow-y-auto">
                {segmentos.map((seg, i) => (
                  <div
                    key={i}
                    className={`p-3 flex gap-3 ${seg.hablante.includes("Paciente") ? "bg-purple-50/50" : "bg-white"}`}
                  >
                    <div className="flex-shrink-0 mt-0.5">
                      {seg.hablante.includes("Paciente") ? (
                        <User size={16} className="text-purple-500" />
                      ) : (
                        <UserCheck size={16} className="text-blue-500" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-xs font-medium text-slate-500">{seg.hablante}</span>
                        <span className="text-xs text-slate-400 flex items-center gap-0.5">
                          <Clock size={10} /> {seg.inicio}
                        </span>
                      </div>
                      <p className="text-sm text-slate-700">{seg.texto}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Campos extraídos */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="p-4 bg-slate-50 border-b">
              <h3 className="font-semibold text-slate-800">Datos Extraídos para Formatos</h3>
              <p className="text-xs text-slate-500 mt-0.5">Campos detectados automáticamente en la transcripción</p>
            </div>
            {camposExtraidos.length === 0 ? (
              <div className="p-6 text-center text-slate-400 text-sm">
                No se detectaron campos clínicos en la transcripción.<br />
                El audio puede ser demasiado corto o el texto no contiene palabras clave clínicas.
              </div>
            ) : (
              <div className="divide-y">
                {camposExtraidos.map((campo, i) => (
                  <div key={i} className="p-3 flex items-start gap-3 hover:bg-slate-50">
                    <SemaforoIcon confianza={campo.confianza} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium text-slate-700">{campo.campo}</span>
                        <ConfianzaBadge confianza={campo.confianza} fuente={campo.fuente} size="sm" />
                      </div>
                      <p className="text-sm text-slate-600 mt-0.5 line-clamp-3">{campo.valor}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <button className="flex items-center gap-2 text-blue-600 hover:text-blue-800 font-medium text-sm">
            <ArrowRight size={16} />
            Confirmar datos y generar formatos
          </button>
        </div>
      )}
    </div>
  );
}
