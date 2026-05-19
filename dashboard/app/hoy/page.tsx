"use client";

import { useEffect, useState } from "react";
import { EstadoVisual } from "@/components/EstadoVisual";
import { BotonGigante } from "@/components/BotonGigante";
import { Mic, Calendar, User } from "lucide-react";

interface Cita {
  hora: string;
  paciente: string;
  cc?: string;
  procesado?: boolean;
}

interface TaskActiva {
  task_id: string;
  paciente_cc: string;
  estado: string;
  paso_actual: number;
}

export default function HoyPage() {
  const [citas, setCitas] = useState<Cita[]>([]);
  const [tasksActivas, setTasksActivas] = useState<TaskActiva[]>([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [rAgenda, rTasks] = await Promise.all([
          fetch("http://localhost:8000/api/agenda"),
          fetch("http://localhost:8000/api/tasks/activas"),
        ]);
        const agenda = rAgenda.ok ? await rAgenda.json() : {citas:[]};
        const tasks = rTasks.ok ? await rTasks.json() : {tasks:[]};
        setCitas(agenda.citas || []);
        setTasksActivas(tasks.tasks || []);
      } finally { setCargando(false); }
    };
    fetchAll();
    const intervalo = setInterval(fetchAll, 5000);
    return () => clearInterval(intervalo);
  }, []);

  return (
    <div className="space-y-8 max-w-5xl mx-auto p-6">
      <header>
        <h1 className="text-4xl font-bold text-slate-800 mb-2">Mi día, Sandra</h1>
        <p className="text-lg text-slate-500">
          {new Date().toLocaleDateString("es-CO", {weekday: "long", day: "numeric", month: "long"})}
        </p>
      </header>

      <section>
        <BotonGigante
          label="Subir audio de una consulta"
          sublabel="Toma 10-20 min en procesarse"
          icon={Mic}
          href="/subir-audio"
          color="azul"
        />
      </section>

      {tasksActivas.length > 0 && (
        <section>
          <h2 className="text-2xl font-semibold mb-4">⏳ Procesando ahora</h2>
          <div className="space-y-3">
            {tasksActivas.map(t => (
              <div key={t.task_id} className="bg-blue-50 border-2 border-blue-200 p-5 rounded-xl">
                <p className="text-lg font-medium">CC {t.paciente_cc}</p>
                <p className="text-base text-blue-700">Paso {t.paso_actual}/9: {t.estado}</p>
                <a href={`/paciente/${t.paciente_cc}`} className="text-blue-600 underline mt-2 inline-block">
                  Ver progreso →
                </a>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
          <Calendar size={28} /> Citas de hoy
        </h2>
        {cargando ? (
          <p className="text-slate-500">Cargando agenda...</p>
        ) : citas.length === 0 ? (
          <EstadoVisual estado="warn" titulo="No tengo agenda cargada" detalle="¿Querés revisar tu Gmail?" />
        ) : (
          <div className="space-y-3">
            {citas.map((c, i) => (
              <a key={i} href={c.cc ? `/paciente/${c.cc}` : "#"} className="flex items-center gap-4 p-5 bg-white border-2 border-slate-200 rounded-xl hover:border-blue-400 transition-colors">
                <div className="bg-blue-100 text-blue-700 px-4 py-2 rounded-lg text-xl font-bold">{c.hora}</div>
                <div className="flex-1">
                  <p className="text-xl font-medium">{c.paciente}</p>
                  {c.cc && <p className="text-sm text-slate-500">CC {c.cc}</p>}
                </div>
                {c.procesado && <span className="text-green-600 text-lg">✅ Listo</span>}
              </a>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
