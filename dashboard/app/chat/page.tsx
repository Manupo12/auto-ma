"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2, Trash2, FileText } from "lucide-react";
import type { ChatMessage } from "@/lib/hermes";

const STORAGE_KEY = "rilo-chat-messages";
const MAX_MESSAGES = 50; // Keep last 50 messages in localStorage

function loadMessages(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const msgs = JSON.parse(raw) as ChatMessage[];
      return msgs.slice(-MAX_MESSAGES);
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
  const [mensajes, setMensajes] = useState<ChatMessage[]>(() => {
    const saved = loadMessages();
    if (saved.length > 0) return saved;
    // Default welcome message
    const welcome: ChatMessage = {
      rol: "asistente",
      contenido:
        "¡Hola Sandra! Soy Tomy. Puedes chatear conmigo para buscar pacientes, revisar formatos, o corregir documentos. ¿En qué te ayudo?",
      timestamp: new Date().toISOString(),
    };
    return [welcome];
  });
  const [input, setInput] = useState("");
  const [enviando, setEnviando] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Save to localStorage on every change
  useEffect(() => {
    saveMessages(mensajes);
  }, [mensajes]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes]);

  const enviar = async () => {
    if (!input.trim() || enviando) return;
    const mensaje = input.trim();
    setInput("");
    setEnviando(true);
    const t0 = Date.now();

    // Agregar mensaje del usuario
    const userMsg: ChatMessage = {
      rol: "usuario",
      contenido: mensaje,
      timestamp: new Date().toISOString(),
    };
    const updatedMensajes = [...mensajes, userMsg];
    setMensajes(updatedMensajes);

    try {
      const res = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mensaje,
          paciente_cc: undefined,
          historial: updatedMensajes.slice(-10),
        }),
        // No timeout infinito — si tarda >45s, el navegador aborta
        signal: AbortSignal.timeout(180000),
      });

      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      let respuesta: string;
      let archivo_encontrado: string | null = null;
      let workspaceOk: boolean | null = null;

      if (res.ok) {
        const data = await res.json();
        respuesta = data.contenido ?? data.respuesta ?? "";
        archivo_encontrado = data.archivo ?? null;
        workspaceOk = data.workspace_accesible ?? null;
        
        // Si respuesta vacía, mostrar mensaje de diagnóstico
        if (!respuesta || respuesta.trim() === "") {
          respuesta = "🤔 Tomy no pudo generar una respuesta (respuesta vacía).\n\n"
            + (workspaceOk === false 
              ? "⚠️ Tu carpeta de trabajo no es accesible. Revisá WORKSPACE_DIR en .env"
              : "💡 Intentá ser más específico o probá con otro mensaje.");
        }
        
        // Agregar info de debug sutil
        if (workspaceOk === false) {
          respuesta += "\n\n⚠️ No veo tu carpeta de trabajo.";
        }
      } else {
        const errorText = await res.text().catch(() => "");
        respuesta = `❌ Error del servidor (HTTP ${res.status}). ${errorText.slice(0, 200)}`;
      }

      const assistantMsg: ChatMessage = {
        rol: "asistente",
        contenido: respuesta,
        timestamp: new Date().toISOString(),
        archivo: archivo_encontrado || undefined,
      };
      setMensajes((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      let errorMsg = "❌ No se pudo conectar con el servidor.";
      
      if (err instanceof DOMException && err.name === "AbortError") {
        errorMsg = `⏰ La solicitud tardó más de 50 segundos y fue cancelada. El servidor puede estar sobrecargado.`;
      } else if (err instanceof TypeError && err.message.includes("fetch")) {
        errorMsg = "❌ No se pudo conectar con el backend. ¿Está corriendo en http://localhost:8000?";
      } else if (err instanceof Error) {
        errorMsg = `❌ Error: ${err.message.slice(0, 200)}`;
      }
      
      setMensajes((prev) => [
        ...prev,
        {
          rol: "asistente",
          contenido: errorMsg,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setEnviando(false);
    }
  };

  const limpiarChat = () => {
    localStorage.removeItem(STORAGE_KEY);
    setMensajes([
      {
        rol: "asistente",
        contenido:
          "¡Chat limpio! ¿En qué te ayudo, Sandra?",
        timestamp: new Date().toISOString(),
      },
    ]);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] animate-fadeIn">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Chat con Tomy</h1>
          <p className="text-slate-500 mt-1">
            Corrige documentos, busca pacientes, genera formatos
          </p>
        </div>
        <button
          onClick={limpiarChat}
          className="flex items-center gap-1 px-3 py-2 text-sm text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
          title="Limpiar conversación"
        >
          <Trash2 size={14} />
          Limpiar
        </button>
      </div>

      {/* Chat area */}
      <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {mensajes.map((msg, i) => (
            <div
              key={i}
              className={`flex gap-3 ${msg.rol === "usuario" ? "justify-end" : ""}`}
            >
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
              >
                <p className="whitespace-pre-wrap">{msg.contenido}</p>
                {msg.archivo && (
                  <p className="text-xs mt-1 text-blue-500 flex items-center gap-1">
                    <FileText size={10} />
                    {msg.archivo}
                  </p>
                )}
                <p
                  className={`text-xs mt-1 ${
                    msg.rol === "usuario" ? "text-blue-200" : "text-slate-400"
                  }`}
                >
                  {new Date(msg.timestamp).toLocaleTimeString("es-CO", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              </div>
              {msg.rol === "usuario" && (
                <div className="w-8 h-8 rounded-full bg-slate-300 flex items-center justify-center flex-shrink-0">
                  <User size={16} className="text-slate-600" />
                </div>
              )}
            </div>
          ))}
          {enviando && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
                <Bot size={16} className="text-white" />
              </div>
              <div className="bg-slate-100 px-4 py-3 rounded-2xl rounded-bl-md">
                <Loader2 size={18} className="animate-spin text-slate-400" />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-slate-200">
          <div className="flex gap-2">
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
    </div>
  );
}
