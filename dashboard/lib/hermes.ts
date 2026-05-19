/**
 * Cliente API para conectar el dashboard con Hermes Agent.
 * Todas las llamadas al backend pasan por aquí.
 */

const HERMES_API = process.env.NEXT_PUBLIC_HERMES_API || "http://localhost:8000/api";

export interface Paciente {
  documento: string;
  nombre: string;
  fecha_nacimiento?: string;
  edad?: string;
  telefono?: string;
  direccion?: string;
  email?: string;
  eps_ips?: string;
  afp?: string;
  empresa?: string;
  siniestro?: string;
  estado_caso?: string;
  ultima_actualizacion?: string;
}

export interface FormatoInfo {
  id: string;
  nombre: string;
  estado: "pendiente" | "generado" | "revisado" | "aprobado" | "rechazado";
  fecha_generacion?: string;
  archivo_docx?: string;
  archivo_pdf?: string;
}

export interface ChatMessage {
  rol: "usuario" | "asistente";
  contenido: string;
  timestamp: string;
  archivo?: string;  // Nombre del archivo del workspace que Tomy encontró
}

// ── Pacientes ──────────────────────────────────────────────

export async function listarPacientes(): Promise<Paciente[]> {
  const res = await fetch(`${HERMES_API}/pacientes`);
  if (!res.ok) throw new Error("Error al listar pacientes");
  return res.json();
}

export async function buscarPaciente(cc: string): Promise<Paciente | null> {
  const res = await fetch(`${HERMES_API}/pacientes/${cc}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Error al buscar paciente");
  return res.json();
}

// ── Formatos ───────────────────────────────────────────────

export async function listarFormatos(cc: string): Promise<FormatoInfo[]> {
  const res = await fetch(`${HERMES_API}/pacientes/${cc}/formatos`);
  if (!res.ok) throw new Error("Error al listar formatos");
  return res.json();
}

export async function generarFormatos(cc: string, estado?: string): Promise<{ ok: boolean; mensaje: string }> {
  const res = await fetch(`${HERMES_API}/pacientes/${cc}/generar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ estado_caso: estado }),
  });
  return res.json();
}

export async function corregirFormato(cc: string, formato: string, correccion: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${HERMES_API}/pacientes/${cc}/formatos/${formato}/corregir`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mensaje: correccion }),
  });
  return res.json();
}

// ── Chat ───────────────────────────────────────────────────

export async function enviarMensaje(mensaje: string, cc?: string): Promise<ChatMessage> {
  const res = await fetch(`${HERMES_API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mensaje, paciente_cc: cc }),
  });
  if (!res.ok) throw new Error("Error al enviar mensaje");
  return res.json();
}

// ── Audio ──────────────────────────────────────────────────

export async function subirAudio(file: File, cc: string): Promise<{ ok: boolean; transcripcion?: string }> {
  const formData = new FormData();
  formData.append("audio", file);
  formData.append("paciente_cc", cc);
  
  const res = await fetch(`${HERMES_API}/upload-audio`, {
    method: "POST",
    body: formData,
  });
  return res.json();
}
