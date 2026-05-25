"use client";
import { useState, FormEvent } from "react";
import { login } from "@/lib/auth";

export default function LoginPage() {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setCargando(true);
    try {
      const ok = await login(pin);
      if (ok) {
        window.location.href = "/hoy";
      } else {
        setError("PIN incorrecto");
      }
    } catch {
      setError("Error de conexion");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <form onSubmit={handleSubmit} className="bg-white p-8 rounded-lg shadow-md w-full max-w-sm">
        <h1 className="text-2xl font-bold text-center mb-6 text-slate-800">RILO SAS</h1>
        <p className="text-sm text-slate-500 text-center mb-6">Ingresa tu PIN de acceso</p>
        <input
          type="password"
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={6}
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
          placeholder="PIN"
          className="w-full border border-slate-300 rounded px-4 py-2 text-center text-2xl tracking-widest mb-4 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          autoFocus
          disabled={cargando}
        />
        {error && <p className="text-red-600 text-sm text-center mb-4">{error}</p>}
        <button
          type="submit"
          disabled={cargando || pin.length < 4}
          className="w-full bg-indigo-600 text-white py-2 rounded font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {cargando ? "Verificando..." : "Entrar"}
        </button>
      </form>
    </div>
  );
}
