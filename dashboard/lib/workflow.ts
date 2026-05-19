const API = "http://localhost:8000";

interface TaskResult {
  task_id: string;
  estado: string;
  paso_actual?: number;
  formatos_generados?: Array<{formato: string; archivo: string}>;
  error?: string;
}

export async function procesarPaciente(
  audio: File,
  paciente_cc: string
): Promise<{ task_id: string }> {
  const form = new FormData();
  form.append("audio", audio);
  form.append("paciente_cc", paciente_cc);

  const resp = await fetch(`${API}/api/procesar-paciente`, {
    method: "POST",
    body: form,
  });
  if (!resp.ok) throw new Error(`Error ${resp.status}`);
  return resp.json();
}

export async function obtenerTask(task_id: string): Promise<TaskResult> {
  const resp = await fetch(`${API}/api/tasks/${task_id}`);
  if (!resp.ok) throw new Error(`Error ${resp.status}`);
  const data = await resp.json();
  return data.task;
}

export async function obtenerTasksActivas(): Promise<TaskResult[]> {
  const resp = await fetch(`${API}/api/tasks/activas`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.tasks || [];
}

export async function obtenerTasksPaciente(cc: string): Promise<TaskResult[]> {
  const resp = await fetch(`${API}/api/tasks/paciente/${cc}`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.tasks || [];
}

export async function corregirPaciente(
  cc: string,
  mensaje: string
): Promise<{ ok: boolean; campo_corregido?: string }> {
  const resp = await fetch(`${API}/api/corregir-paciente/${cc}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mensaje }),
  });
  return resp.json();
}

export async function obtenerAgenda(): Promise<{
  citas: Array<{ hora: string; paciente: string; cc?: string }>;
}> {
  const resp = await fetch(`${API}/api/agenda`);
  if (!resp.ok) return { citas: [] };
  return resp.json();
}
