"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { EstadoVisual } from "@/components/EstadoVisual";
import { TimelinePaciente } from "@/components/TimelinePaciente";
import { FormatoCard } from "@/components/FormatoCard";

export default function PacientePage() {
  const { cc } = useParams<{cc: string}>();
  const [paciente, setPaciente] = useState<any>(null);
  const [tasks, setTasks] = useState<any[]>([]);
  const [taskActiva, setTaskActiva] = useState<any>(null);
  const [correccion, setCorreccion] = useState("");
  const [enviandoCorreccion, setEnviandoCorreccion] = useState(false);

  useEffect(() => {
    const cargar = async () => {
      const [rP, rT] = await Promise.all([
        fetch(`http://localhost:8000/api/pacientes/${cc}`),
        fetch(`http://localhost:8000/api/tasks/paciente/${cc}`),
      ]);
      if (rP.ok) setPaciente(await rP.json());
      if (rT.ok) {
        const data = await rT.json();
        setTasks(data.tasks || []);
        const activa = (data.tasks || []).find((t: any) =>
          !["listo", "cancelado"].includes(t.estado) && !t.estado.startsWith("error_")
        );
        setTaskActiva(activa);
      }
    };
    cargar();
    const interval = setInterval(cargar, 3000);
    return () => clearInterval(interval);
  }, [cc]);

  const enviarCorreccion = async () => {
    if (!correccion.trim()) return;
    setEnviandoCorreccion(true);
    try {
      const resp = await fetch(`http://localhost:8000/api/corregir-paciente/${cc}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensaje: correccion }),
      });
      const data = await resp.json();
      if (data.ok) {
        alert(`✅ Corregí "${data.campo_corregido}". Se regeneraron ${data.formatos_regenerados?.length || 0} formatos.`);
        setCorreccion("");
      } else {
        alert(`No entendí. ${data.mensaje || ""}`);
      }
    } finally {
      setEnviandoCorreccion(false);
    }
  };

  if (!paciente) return <div className="p-8 text-xl">Cargando paciente...</div>;

  const ultimaTask = tasks[0];
  const formatos = ultimaTask?.resultado?.formatos_generados || [];

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-8">
      <header className="bg-gradient-to-r from-blue-600 to-blue-700 text-white p-6 rounded-2xl">
        <h1 className="text-3xl font-bold">{paciente.nombre || `CC ${cc}`}</h1>
        <p className="text-blue-100 text-lg mt-1">CC {cc} · {paciente.edad || "?"} años</p>
        {paciente.empresa && <p className="text-blue-100">Empresa: {paciente.empresa}</p>}
      </header>

      {taskActiva && (
        <section className="bg-blue-50 border-2 border-blue-200 p-6 rounded-2xl">
          <h2 className="text-2xl font-semibold mb-4">⏳ Tomy está trabajando…</h2>
          <TimelinePaciente pasoActual={taskActiva.paso_actual} estado={taskActiva.estado} />
        </section>
      )}

      {formatos.length > 0 && (
        <section>
          <h2 className="text-2xl font-semibold mb-4">Documentos generados</h2>
          <div className="space-y-4">
            {formatos.map((f: any, i: number) => (
              <FormatoCard
                key={i}
                nombre={f.formato}
                archivoDocx={f.archivo}
                qaOk={f.qa_ok}
                qaWarnings={f.qa_warnings}
                onCorregir={() => {
                  const el = document.getElementById("correccion-input");
                  el?.scrollIntoView({ behavior: "smooth" });
                  el?.focus();
                }}
              />
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-2xl font-semibold mb-4">Corregir algo</h2>
        <p className="text-base text-slate-600 mb-2">
          Decime qué corregir, por ejemplo: &quot;el siniestro es 503476658&quot; o &quot;la empresa se llama Acme S.A.S.&quot;
        </p>
        <textarea
          id="correccion-input"
          value={correccion}
          onChange={(e) => setCorreccion(e.target.value)}
          className="w-full p-4 border-2 border-slate-300 rounded-xl text-lg"
          rows={3}
          placeholder="Escribe la corrección aquí…"
        />
        <button
          onClick={enviarCorreccion}
          disabled={enviandoCorreccion || !correccion.trim()}
          className="mt-3 px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-lg font-semibold disabled:opacity-50"
        >
          {enviandoCorreccion ? "Aplicando..." : "Aplicar corrección"}
        </button>
      </section>
    </div>
  );
}
