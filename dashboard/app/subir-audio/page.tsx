"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Upload, Mic, Loader2 } from "lucide-react";
import { BotonGigante } from "@/components/BotonGigante";
import { EstadoVisual } from "@/components/EstadoVisual";

export default function SubirAudioPage() {
  const router = useRouter();
  const [archivo, setArchivo] = useState<File | null>(null);
  const [cc, setCc] = useState("");
  const [subiendo, setSubiendo] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const handleFile = (file: File | null) => {
    if (!file) return;
    setArchivo(file);
    setError("");
  };

  const subir = async () => {
    if (!archivo || !cc.trim()) {
      setError("Necesito el audio y la cédula del paciente.");
      return;
    }
    setSubiendo(true);
    setError("");
    try {
      const form = new FormData();
      form.append("audio", archivo);
      form.append("paciente_cc", cc.trim());

      const resp = await fetch(`${API}/api/procesar-paciente`, {
        method: "POST",
        body: form,
      });
      if (!resp.ok) throw new Error(`Error ${resp.status}`);
      const data = await resp.json();
      router.push(`/paciente/${cc.trim()}`);
    } catch (e) {
      setError(`No pude subir el audio. ${e instanceof Error ? e.message : ""}`);
      setSubiendo(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-8">
      <header>
        <h1 className="text-4xl font-bold">Subir audio de una consulta</h1>
        <p className="text-lg text-slate-600 mt-2">
          Voy a transcribir, organizar y generar los documentos. Toma 10-20 minutos.
          Te aviso por Telegram cuando esté listo.
        </p>
      </header>

      <section>
        <label className="block text-xl font-semibold mb-3">
          1. ¿De qué paciente es este audio?
        </label>
        <input
          type="text"
          value={cc}
          onChange={(e) => setCc(e.target.value)}
          placeholder="Escribe la cédula"
          className="w-full p-5 text-2xl border-2 border-slate-300 rounded-xl focus:border-blue-500 outline-none"
        />
      </section>

      <section>
        <label className="block text-xl font-semibold mb-3">
          2. Carga el audio de la consulta
        </label>
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); handleFile(e.dataTransfer.files?.[0] || null); }}
          onClick={() => inputRef.current?.click()}
          className="border-4 border-dashed border-slate-300 hover:border-blue-400 rounded-3xl p-16 text-center cursor-pointer transition-colors"
        >
          <input
            ref={inputRef}
            type="file"
            accept="audio/*,.m4a,.mp3,.wav"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0] || null)}
          />
          {archivo ? (
            <div className="space-y-4">
              <Mic size={80} className="text-green-600 mx-auto" />
              <p className="text-2xl font-semibold">{archivo.name}</p>
              <p className="text-lg text-slate-500">
                {(archivo.size / 1024 / 1024).toFixed(1)} MB · Listo para procesar
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <Upload size={80} className="text-slate-400 mx-auto" />
              <p className="text-2xl font-semibold text-slate-700">
                Arrastra el audio aquí o haz click
              </p>
              <p className="text-lg text-slate-500">M4A, MP3, WAV — sin límite de tamaño</p>
            </div>
          )}
        </div>
      </section>

      {error && <EstadoVisual estado="error" titulo="Algo salió mal" detalle={error} />}

      <BotonGigante
        label="Procesar paciente"
        sublabel="Tomy hace todo el resto"
        icon={Mic}
        color="verde"
        onClick={subir}
        disabled={!archivo || !cc.trim()}
        loading={subiendo}
      />
    </div>
  );
}
