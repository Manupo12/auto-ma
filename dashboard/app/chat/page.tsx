"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2 } from "lucide-react";
import type { ChatMessage } from "@/lib/hermes";

export default function ChatPage() {
  const [mensajes, setMensajes] = useState<ChatMessage[]>([
    {
      rol: "asistente",
      contenido: "¡Hola Sandra! Soy Tomy. Puedes chatear conmigo para buscar pacientes, revisar formatos, o corregir documentos. ¿En qué te ayudo?",
      timestamp: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [enviando, setEnviando] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes]);

  const enviar = async () => {
    if (!input.trim() || enviando) return;
    const mensaje = input.trim();
    setInput("");
    setEnviando(true);

    // Agregar mensaje del usuario
    const userMsg: ChatMessage = {
      rol: "usuario",
      contenido: mensaje,
      timestamp: new Date().toISOString(),
    };
    setMensajes((prev) => [...prev, userMsg]);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensaje, paciente_cc: undefined }),
      });

      let respuesta: string;
      if (res.ok) {
        const data = await res.json();
        respuesta = data.contenido ?? data.respuesta ?? JSON.stringify(data);
      } else {
        respuesta = "❌ El servidor no está disponible en este momento. Intenta de nuevo.";
      }

      const assistantMsg: ChatMessage = {
        rol: "asistente",
        contenido: respuesta,
        timestamp: new Date().toISOString(),
      };
      setMensajes((prev) => [...prev, assistantMsg]);
    } catch {
      setMensajes((prev) => [
        ...prev,
        { rol: "asistente", contenido: "❌ Error al conectar con el asistente. Intenta de nuevo.", timestamp: new Date().toISOString() },
      ]);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] animate-fadeIn">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-slate-800">Chat con Tomy</h1>
        <p className="text-slate-500 mt-1">Corrige documentos, busca pacientes, genera formatos</p>
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
                <p className={`text-xs mt-1 ${msg.rol === "usuario" ? "text-blue-200" : "text-slate-400"}`}>
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
