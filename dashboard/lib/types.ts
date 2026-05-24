export type { Paciente, FormatoInfo } from "./api";

export interface TareaWorkflow {
  task_id: string;
  paciente_cc: string;
  audio_path?: string;
  estado: string;
  paso_actual: number;
  iniciado_en?: string;
  terminado_en?: string;
  error?: string;
  resultado?: Record<string, unknown>;
}
