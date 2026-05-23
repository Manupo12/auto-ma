"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User, Loader2, Trash2, FileText, Mic, Paperclip, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ChatMessage {
  rol: "usuario" | "asistente";
  contenido: string;
  timestamp: string;
  archivo?: string;
  taskId?: string;
  pacienteCC?: string;
  formatos?: { archivo?: string; formato?: string }[];
  acciones?: string[];
}

const STORAGE_KEY = "rilo-chat-messages";
const MAX_MESSAGES = 50;
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const ESTADOS_PENSANDO = [
  "Revisando el estado del sistema...",
  "Leyendo tus archivos...",
  "Cruzando datos entre formatos...",
  "Tomy esta razonando...",
  "Verificando informacion clinica...",
];

const PASOS_LABELS: Record<number, string> = {
  1: "Transcribiendo audio con Deepgram...",
  2: "Buscando datos del paciente...",
  3: "Leyendo tus notas...",
  4: "Leyendo formatos de referencia...",
  5: "Sintetizando (IA razonando, puede tardar 5+ min)...",
  6: "Verificando datos en portales (Medifolios + Positiva)...",
  7: "Generando los 7 formatos...",
  8: "Verificando calidad...",
  9: "Convirtiendo a PDF...",
  10: "Enviando notificacion por Telegram...",
};

function loadMessages(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return (JSON.parse(raw) as ChatMessage[]).slice(-MAX_MESSAGES);
    }
  } catch {}
  return [];
}

function saveMessages(msgs: ChatMessage[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(msgs.slice(-MAX_MESSAGES)));
  } catch {}
}

export default function ChatPage() {
  const [mensajes, setMensajes] = useState<ChatMessage[]>([{
    rol: "asistente",
    contenido: "Hola Sandra! Soy Tomy. Podes chatear conmigo para buscar pacientes, revisar formatos, o corregir documentos. Tambien podes **adjuntar un audio** de consulta para que procese todo automaticamente. En que te ayudo?",
    timestamp: new Date().toISOString(),
  }]);
  const [input, setInput] = useState("");
  const [enviando, setEnviando] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLInputElement>(null);

  const [pacienteCc, setPacienteCc] = useState("");
  const [pacientesHistorial, setPacientesHistorial] = useState<{cc: string; mensajes: number; ultimo: string}[]>([]);
  const [loaded, setLoaded] = useState(false);

  // Cargar mensajes guardados solo en cliente
  useEffect(() => {
    const saved = loadMessages();
    if (saved.length > 0) {
      setMensajes(saved);
    }
    setLoaded(true);
  }, []);

  const [ccAudio, setCcAudio] = useState("");
  const [mostrarCcAudio, setMostrarCcAudio] = useState(false);
  const [pendingAudioFile, setPendingAudioFile] = useState<File | null>(null);

  const [estadoIdx, setEstadoIdx] = useState(0);
  const [showFilePicker, setShowFilePicker] = useState(false);
  const [fpCc, setFpCc] = useState("");
  const [fpArchivos, setFpArchivos] = useState<{ nombre: string; tamano_kb: number }[]>([]);
  const [fpLoading, setFpLoading] = useState(false);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    saveMessages(mensajes);
  }, [mensajes]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes]);

  useEffect(() => {
    if (!enviando && mensajes[mensajes.length - 1]?.contenido === "") return;
    if (!enviando) return;
    const t = setInterval(() => setEstadoIdx((i) => (i + 1) % ESTADOS_PENSANDO.length), 8000);
    return () => clearInterval(t);
  }, [enviando, mensajes]);

  // Cargar lista de pacientes con historial
  useEffect(() => {
    fetch(`${API}/api/chat/historial`)
      .then(r => r.json())
      .then(d => { if (d.ok) setPacientesHistorial(d.pacientes || []); })
      .catch(() => {});
  }, []);

  // Guardar conversacion cuando hay mensajes con CC
  useEffect(() => {
    if (mensajes.length <= 1) return;
    const cc = pacienteCc || mensajes.find(m => m.pacienteCC)?.pacienteCC;
    if (!cc) return;
    const timer = setTimeout(() => {
      fetch(`${API}/api/chat/historial`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paciente_cc: cc, mensajes })
      }).catch(() => {});
    }, 2000);
    return () => clearTimeout(timer);
  }, [mensajes, pacienteCc]);

  // Cargar conversacion al seleccionar CC
  const cargarHistorialPaciente = async (cc: string) => {
    setPacienteCc(cc);
    try {
      const r = await fetch(`${API}/api/chat/historial/${cc}`);
      const d = await r.json();
      if (d.ok && d.mensajes?.length > 0) {
        setMensajes(d.mensajes);
      } else {
        setMensajes([{
          rol: "asistente",
          contenido: `Hola Sandra! Cargue el historial de CC ${cc}. Tenes ${d.mensajes?.length || 0} mensajes guardados. En que te ayudo con este paciente?`,
          timestamp: new Date().toISOString(),
        }]);
      }
    } catch {
      setMensajes([{ rol: "asistente", contenido: `No pude cargar el historial de CC ${cc}.`, timestamp: new Date().toISOString() }]);
    }
  };

  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const iniciarPollingTarea = useCallback((taskId: string, cc: string) => {
    let erroresConsecutivos = 0;
    const ESTADOS_FINALES = ["listo", "listo_con_advertencias", "listo_incompleto", "listo_sin_notificacion", "cancelado"];

    const poll = async () => {
      try {
        const res = await fetch(`${API}/api/tasks/${taskId}`);
        const data = await res.json();
        const task = data.task;
        erroresConsecutivos = 0;

        if (ESTADOS_FINALES.includes(task.estado) || task.estado === "listo") {
          clearInterval(timer!);
          const formatos = task.resultado?.formatos_generados || [];
          const verificacion = task.resultado?.verificacion;
          const discrepancias = task.resultado?.discrepancias || [];

          let msg = `**Listo, Sandra!** Genere ${formatos.length} formatos para CC ${cc}:\n\n`;
          for (const f of formatos) {
            const nombre = f.archivo?.split("/").pop() || f.formato;
            msg += `- [${nombre}](/api/download/${encodeURIComponent(nombre)})\n`;
          }

          if (verificacion) {
            msg += `\n---\n**Verificacion de portales:**\n`;
            msg += `- Confirmados: ${verificacion.confirmados || 0}\n`;
            msg += `- Completados con portal: ${verificacion.completados_portal || 0}\n`;
            if (verificacion.discrepancias > 0) {
              msg += `- **ATENCION: ${verificacion.discrepancias} discrepancia(s)**\n`;
              for (const d of discrepancias) {
                if (d.estado === "discrepancia") {
                  msg += `  - ${d.campo}: \"${d.sintesis}\" pero portal dice \"${d.portal}\"\n`;
                }
              }
            }
            if (verificacion.faltantes > 0) {
              msg += `- Datos faltantes: ${verificacion.faltantes} - completalos manualmente\n`;
            }
          }

          msg += `\nQueres que revise algo o corrijamos algun dato?`;
          setMensajes((prev) => [...prev, {
            rol: "asistente",
            contenido: msg,
            timestamp: new Date().toISOString(),
            formatos: formatos,
          }]);
        } else if (task.estado?.startsWith("error")) {
          clearInterval(timer!);
          setMensajes((prev) => [...prev, {
            rol: "asistente",
            contenido: `Hubo un problema en el paso ${task.paso_actual}/10: ${(task.error || "error desconocido").slice(0, 200)}. Intentamos de nuevo?`,
            timestamp: new Date().toISOString(),
          }]);
        } else if (task.estado === "esperando_datos") {
          clearInterval(timer!);
          setMensajes((prev) => [...prev, {
            rol: "asistente",
            contenido: `Procese el audio pero faltan datos: ${(task.resultado?.campos_faltantes || []).join(", ")}`,
            timestamp: new Date().toISOString(),
          }]);
        } else {
          const pasoLabel = PASOS_LABELS[task.paso_actual] || task.estado;
          setMensajes((prev) => {
            const nuevo = [...prev];
            for (let i = nuevo.length - 1; i >= 0; i--) {
              if ((nuevo[i] as ChatMessage).taskId === taskId) {
                const marker = nuevo[i].contenido.lastIndexOf("\n\n*Progreso:*");
                const base = marker >= 0 ? nuevo[i].contenido.slice(0, marker) : nuevo[i].contenido;
                nuevo[i] = { ...nuevo[i], contenido: base + `\n\n*Progreso:* Paso ${task.paso_actual}/10 - ${pasoLabel}` };
                break;
              }
            }
            return nuevo;
          });

          // P-1: intervalo adaptativo
          const delay = task.paso_actual <= 4 ? 3000 : 10000;
          clearInterval(timer!);
          timer = setInterval(poll, delay);
        }
      } catch {
        erroresConsecutivos++;
        if (erroresConsecutivos >= 3) {
          clearInterval(timer!);
          setMensajes((prev) => [...prev, {
            rol: "asistente",
            contenido: "No puedo contactar al servidor. Revisa que el backend este corriendo en localhost:8000.",
            timestamp: new Date().toISOString(),
          }]);
        }
      }
    };

    let timer: ReturnType<typeof setInterval> | null = setInterval(poll, 3000);
  }, []);

  const handleAudioChat = async (file: File) => {
    if (!ccAudio.trim()) {
      setPendingAudioFile(file);
      setMostrarCcAudio(true);
      return;
    }
    setEnviando(true);

    const userMsg: ChatMessage = {
      rol: "usuario",
      contenido: `Audio subido: ${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB) — CC ${ccAudio}`,
      timestamp: new Date().toISOString(),
    };
    setMensajes((prev) => [...prev, userMsg]);

    const form = new FormData();
    form.append("audio", file);
    form.append("paciente_cc", ccAudio.trim());

    try {
      const res = await fetch(`${API}/api/chat/audio`, { method: "POST", body: form });
      const data = await res.json();

      if (data.ok) {
        const tomyMsg: ChatMessage = {
          rol: "asistente",
          contenido: data.mensaje_tomy,
          timestamp: new Date().toISOString(),
          taskId: data.task_id,
          pacienteCC: data.paciente_cc,
        };
        setMensajes((prev) => [...prev, tomyMsg]);
        iniciarPollingTarea(data.task_id, data.paciente_cc);
      } else {
        throw new Error(data.detail || "Error al procesar audio");
      }
    } catch (e) {
      setMensajes((prev) => [...prev, {
        rol: "asistente",
        contenido: `No pude procesar el audio: ${e instanceof Error ? e.message : "error desconocido"}`,
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setEnviando(false);
    }
  };

  const enviar = async () => {
    if (!input.trim() || enviando) return;
    const mensaje = input.trim();
    setInput("");
    setEnviando(true);

    const userMsg: ChatMessage = {
      rol: "usuario",
      contenido: mensaje,
      timestamp: new Date().toISOString(),
    };
    const historialConUser = [...mensajes, userMsg];
    const assistantPlaceholder: ChatMessage = {
      rol: "asistente",
      contenido: "",
      timestamp: new Date().toISOString(),
    };
    setMensajes([...historialConUser, assistantPlaceholder]);

    try {
      const res = await fetch(`${API}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensaje, historial: historialConUser.slice(-10) }),
        signal: AbortSignal.timeout(300000),
      });

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let acumulado = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const chunk of decoder.decode(value, { stream: true }).split("\n")) {
          const line = chunk.trim();
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.tipo === "delta") {
              acumulado += data.contenido;
              setMensajes((prev) => {
                const nuevo = [...prev];
                nuevo[nuevo.length - 1] = { ...nuevo[nuevo.length - 1], contenido: acumulado };
                return nuevo;
              });
            } else if (data.tipo === "fin") {
              setMensajes((prev) => {
                const nuevo = [...prev];
                nuevo[nuevo.length - 1] = {
                  ...nuevo[nuevo.length - 1],
                  contenido: acumulado || "Sin respuesta.",
                  archivo: data.archivo,
                };
                return nuevo;
              });
            } else if (data.tipo === "error") {
              setMensajes((prev) => {
                const nuevo = [...prev];
                nuevo[nuevo.length - 1] = {
                  ...nuevo[nuevo.length - 1],
                  contenido: `Error: ${data.contenido || "error desconocido"}`,
                };
                return nuevo;
              });
            }
          } catch {}
        }
      }
    } catch {
      setMensajes((prev) => {
        const n = [...prev];
        n[n.length - 1] = {
          ...n[n.length - 1],
          contenido: n[n.length - 1].contenido || "Error de conexion con el servidor. Asegurate de que el backend este corriendo.",
        };
        return n;
      });
    } finally {
      setEnviando(false);
    }
  };

  const limpiarChat = () => {
    localStorage.removeItem(STORAGE_KEY);
    if (pollingRef.current) clearInterval(pollingRef.current);
    setMensajes([{
      rol: "asistente",
      contenido: "Chat limpio! En que te ayudo, Sandra?",
      timestamp: new Date().toISOString(),
    }]);
  };

  const buscarArchivos = async () => {
    if (!fpCc.trim()) return;
    setFpLoading(true);
    try {
      const r = await fetch(`${API}/api/archivos/paciente/${fpCc.trim()}`);
      const d = await r.json();
      setFpArchivos(d.archivos || []);
    } finally {
      setFpLoading(false);
    }
  };

  const seleccionarArchivo = (nombre: string) => {
    setInput((prev) => prev + (prev ? " " : "") + `/api/download/${encodeURIComponent(nombre)}`);
    setShowFilePicker(false);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] animate-fadeIn">
      <div className="mb-4 flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Chat con Tomy</h1>
          <p className="text-slate-500 mt-1">Corrige documentos, busca pacientes, subi audios</p>
        </div>
        <div className="flex items-center gap-2">
          {pacientesHistorial.length > 0 && (
            <select
              value={pacienteCc}
              onChange={(e) => { if (e.target.value) cargarHistorialPaciente(e.target.value); }}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
            >
              <option value="">Historial por paciente</option>
              {pacientesHistorial.map(p => (
                <option key={p.cc} value={p.cc}>CC {p.cc} ({p.mensajes} msgs)</option>
              ))}
            </select>
          )}
          {pacienteCc && (
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">CC {pacienteCc}</span>
          )}
          {pacienteCc && (
            <button
              onClick={async () => {
                await fetch(`${API}/api/chat/historial/${pacienteCc}`, { method: "DELETE" });
                setMensajes([{ rol: "asistente", contenido: `Chat limpio para CC ${pacienteCc}.`, timestamp: new Date().toISOString() }]);
                setPacientesHistorial(prev => prev.filter(p => p.cc !== pacienteCc));
              }}
              className="flex items-center gap-1 px-3 py-2 text-sm text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              title="Eliminar historial de este paciente"
            >
              <Trash2 size={14} /> Borrar chat
            </button>
          )}
          <button
            onClick={limpiarChat}
            className="flex items-center gap-1 px-3 py-2 text-sm text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
            title="Limpiar conversacion"
          >
            <Trash2 size={14} /> Limpiar
          </button>
        </div>
      </div>

      <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {mensajes.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.rol === "usuario" ? "justify-end" : ""}`}>
              {msg.rol === "asistente" && (
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                  <Bot size={16} className="text-white" />
                </div>
              )}
              <div
                className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm ${
                  msg.rol === "usuario"
                    ? "bg-blue-600 text-white rounded-br-md"
                    : "bg-slate-100 text-slate-800 rounded-bl-md"
                }`}
                suppressHydrationWarning
              >
                {msg.rol === "asistente" ? (
                  loaded ? (
                    <div className="prose prose-sm max-w-none prose-slate">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.contenido}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.contenido}</p>
                  )
                ) : (
                  <p className="whitespace-pre-wrap">{msg.contenido}</p>
                )}
                {msg.formatos && msg.formatos.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {msg.formatos.map((f, fi) => (
                      <a
                        key={fi}
                        href={f.archivo ? `/api/download/${encodeURIComponent(f.archivo.split("/").pop() || "")}` : "#"}
                        download
                        className="text-xs text-blue-600 hover:underline block"
                      >
                        <FileText size={10} className="inline mr-1" />
                        {f.formato || f.archivo?.split("/").pop()}
                      </a>
                    ))}
                  </div>
                )}
                {msg.archivo && !msg.formatos && (
                  <p className="text-xs mt-1 text-blue-500 flex items-center gap-1">
                    <FileText size={10} /> {msg.archivo}
                  </p>
                )}
                <p className={`text-xs mt-1 ${msg.rol === "usuario" ? "text-blue-200" : "text-slate-400"}`} suppressHydrationWarning>
                  {new Date(msg.timestamp).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
              {msg.rol === "usuario" && (
                <div className="w-8 h-8 rounded-full bg-slate-300 flex items-center justify-center flex-shrink-0">
                  <User size={16} className="text-slate-600" />
                </div>
              )}
            </div>
          ))}
          {enviando && mensajes[mensajes.length - 1]?.contenido === "" && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
                <Bot size={16} className="text-white" />
              </div>
              <div className="bg-slate-100 px-4 py-3 rounded-2xl rounded-bl-md flex items-center gap-2">
                <Loader2 size={16} className="animate-spin text-blue-500" />
                <span className="text-sm text-slate-600">{ESTADOS_PENSANDO[estadoIdx]}</span>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="p-4 border-t border-slate-200">
          <div className="flex gap-2 items-end">
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowFilePicker((o) => !o)}
                className="p-3 text-slate-400 hover:text-blue-600 rounded-xl hover:bg-slate-50 transition-colors"
                title="Adjuntar archivo"
              >
                <Paperclip size={20} />
              </button>
              {showFilePicker && (
                <div className="absolute bottom-12 left-0 w-80 bg-white border rounded-xl shadow-xl z-50 p-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <input
                      value={fpCc}
                      onChange={(e) => setFpCc(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && buscarArchivos()}
                      placeholder="CC del paciente"
                      className="flex-1 border rounded-lg px-2 py-1 text-sm"
                    />
                    <button onClick={buscarArchivos} className="px-2 py-1 bg-blue-600 text-white rounded-lg text-sm">
                      Buscar
                    </button>
                    <button onClick={() => setShowFilePicker(false)}>
                      <X size={14} />
                    </button>
                  </div>
                  {fpLoading ? (
                    <Loader2 size={16} className="animate-spin mx-auto" />
                  ) : fpArchivos.length === 0 ? (
                    <p className="text-slate-400 text-xs text-center py-2">Sin resultados</p>
                  ) : (
                    <div className="max-h-48 overflow-y-auto space-y-1">
                      {fpArchivos.map((a) => (
                        <button
                          key={a.nombre}
                          onClick={() => seleccionarArchivo(a.nombre)}
                          className="w-full text-left flex items-center gap-2 px-2 py-1.5 rounded hover:bg-slate-50 text-sm"
                        >
                          <FileText size={12} className="text-blue-500 flex-shrink-0" />
                          <span className="flex-1 truncate">{a.nombre}</span>
                          <span className="text-slate-400 text-xs">{a.tamano_kb}KB</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            <input
              type="file"
              accept="audio/*,.m4a"
              className="hidden"
              ref={audioRef}
              onChange={(e) => e.target.files?.[0] && handleAudioChat(e.target.files[0])}
            />
            <button
              onClick={() => audioRef.current?.click()}
              disabled={enviando}
              className="p-3 text-slate-400 hover:text-purple-600 rounded-xl hover:bg-purple-50 transition-colors"
              title="Subir audio de una consulta"
            >
              <Mic size={20} />
            </button>

            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && enviar()}
              placeholder="Escribe tu mensaje..."
              className="flex-1 px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
              disabled={enviando}
            />
            <button
              onClick={enviar}
              disabled={enviando || !input.trim()}
              className="px-4 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <Send size={20} />
            </button>
          </div>
        </div>
      </div>

      {mostrarCcAudio && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center">
          <div className="bg-white rounded-2xl p-6 w-80 shadow-2xl space-y-4">
            <h2 className="font-bold text-lg">De que paciente es este audio?</h2>
            <input
              type="text"
              value={ccAudio}
              onChange={(e) => setCcAudio(e.target.value)}
              placeholder="Cedula del paciente"
              className="w-full border-2 border-slate-300 rounded-xl p-3 text-lg focus:border-blue-500 outline-none"
            />
            <div className="flex gap-3">
              <button
                onClick={() => { setMostrarCcAudio(false); setPendingAudioFile(null); }}
                className="flex-1 py-2 border border-slate-300 rounded-xl text-slate-600"
              >
                Cancelar
              </button>
              <button
                onClick={() => { setMostrarCcAudio(false); if (pendingAudioFile) handleAudioChat(pendingAudioFile); }}
                disabled={!ccAudio.trim()}
                className="flex-1 py-2 bg-blue-600 text-white rounded-xl disabled:opacity-50"
              >
                Continuar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
