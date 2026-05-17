"use client";

import { useState, useEffect } from "react";
import { Users, FileText, Shield, HardDrive, AlertTriangle, Clock, ArrowRight, CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";
import { ConfianzaBadge } from "@/components/ConfianzaBadge";
import { ReconciliacionAlert } from "@/components/ReconciliacionAlert";

interface Stats {
  total_pacientes: number;
  total_formatos: number;
  backup_fecha: string;
}

export default function HomePage() {
  const [mostrarReconciliacion, setMostrarReconciliacion] = useState(true);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loadingStats, setLoadingStats] = useState(true);

  useEffect(() => {
    fetch("/api/stats")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (data) setStats(data); })
      .catch(() => {})
      .finally(() => setLoadingStats(false));
  }, []);

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div>
        <h1 className="text-2xl lg:text-3xl font-bold text-slate-800">
          Bienvenida, Sandra
        </h1>
        <p className="text-slate-500 mt-1">
          RILO SAS · Rehabilitación Integral Laboral y Ocupacional
        </p>
      </div>

      {/* Reconciliación Alert */}
      {mostrarReconciliacion && (
        <ReconciliacionAlert
          data={{
            medifolios: "503463870",
            positiva: "503463870",
            coinciden: true,
            alerta: "",
          }}
        />
      )}

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          titulo="Pacientes Activos"
          valor={loadingStats ? null : stats ? String(stats.total_pacientes) : "—"}
          subtitulo="En storage/data"
          icono={Users}
          color="bg-blue-500"
          href="/pacientes"
        />
        <StatCard
          titulo="Formatos Generados"
          valor={loadingStats ? null : stats ? String(stats.total_formatos) : "—"}
          subtitulo="DOCX en storage/docs"
          icono={FileText}
          color="bg-green-500"
          href="/formatos"
        />
        <StatCard
          titulo="Confianza Sistema"
          valor="OK"
          subtitulo={<ConfianzaBadge confianza={95} size="sm" />}
          icono={Shield}
          color="bg-purple-500"
          href="/pacientes"
        />
        <StatCard
          titulo="Último Documento"
          valor="OK"
          subtitulo={
            loadingStats
              ? "Cargando..."
              : stats?.backup_fecha
              ? `Generado: ${stats.backup_fecha}`
              : "Sin documentos aún"
          }
          icono={HardDrive}
          color="bg-teal-500"
          href="/formatos"
        />
      </div>

      {/* Quick actions */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
        <h2 className="text-lg font-semibold text-slate-800 mb-4">Acciones Rápidas</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <QuickAction
            href="/pacientes"
            label="Buscar Paciente"
            sub="Por cédula o nombre"
            color="blue"
            icon={Users}
          />
          <QuickAction
            href="/subir-audio"
            label="Subir Audio"
            sub="Transcribir con Deepgram"
            color="purple"
            icon={ArrowRight}
          />
          <QuickAction
            href="/chat"
            label="Chat con Tomy"
            sub="Corregir documentos"
            color="green"
            icon={ArrowRight}
          />
          <QuickAction
            href="/formatos"
            label="Generar Formatos"
            sub="7 formatos ARL Positiva"
            color="amber"
            icon={FileText}
          />
        </div>
      </div>

      {/* Sistema Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Estado del Sistema */}
        <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
          <h3 className="font-semibold text-slate-800 mb-3">Estado del Sistema</h3>
          <div className="space-y-2">
            <StatusRow label="Medifolios" status="conectado" />
            <StatusRow label="ARL Positiva" status="conectado" />
            <StatusRow label="Deepgram (Audio)" status="conectado" confianza={95} />
            <StatusRow label="PDF/A Archivo" status="activo" />
            <StatusRow label="Backup Mensual" status="programado" sub="Próximo: 1 Jun 2026" />
            <StatusRow label="Huella Portales" status="ok" sub="Sin cambios detectados" />
          </div>
        </div>

        {/* Actividad Reciente */}
        <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
          <h3 className="font-semibold text-slate-800 mb-3">Actividad Reciente</h3>
          <div className="space-y-3">
            <ActividadItem
              icono={CheckCircle2}
              color="text-green-500"
              texto="Reconciliación de siniestro OK — 503463870"
              tiempo="Hoy 10:30"
            />
            <ActividadItem
              icono={FileText}
              color="text-blue-500"
              texto="Formato 7 generado — Valoración Desempeño"
              tiempo="Ayer 15:20"
            />
            <ActividadItem
              icono={AlertTriangle}
              color="text-amber-500"
              texto="Corrección aplicada — siniestro.fecha_evento"
              tiempo="15/05/2026"
            />
            <ActividadItem
              icono={HardDrive}
              color="text-teal-500"
              texto="PDF/A generado para documento aprobado"
              tiempo="15/05/2026"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ titulo, valor, subtitulo, icono: Icon, color, href }: {
  titulo: string; valor: string | null; subtitulo: React.ReactNode;
  icono: any; color: string; href: string;
}) {
  return (
    <Link href={href} className="bg-white rounded-xl p-5 shadow-sm border border-slate-200 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-500">{titulo}</p>
          {valor === null ? (
            <Loader2 size={20} className="animate-spin text-slate-400 mt-1" />
          ) : (
            <p className="text-2xl font-bold text-slate-800 mt-1">{valor}</p>
          )}
          <div className="mt-1 text-xs text-slate-500">{subtitulo}</div>
        </div>
        <div className={`${color} p-2.5 rounded-lg`}>
          <Icon size={20} className="text-white" />
        </div>
      </div>
    </Link>
  );
}

function QuickAction({ href, label, sub, color, icon: Icon }: any) {
  const colors: Record<string, string> = {
    blue: "bg-blue-50 hover:bg-blue-100 text-blue-700",
    purple: "bg-purple-50 hover:bg-purple-100 text-purple-700",
    green: "bg-green-50 hover:bg-green-100 text-green-700",
    amber: "bg-amber-50 hover:bg-amber-100 text-amber-700",
  };
  return (
    <Link href={href} className={`flex items-center gap-3 p-3 rounded-lg transition-colors ${colors[color]}`}>
      <Icon size={18} />
      <div>
        <p className="font-medium text-sm">{label}</p>
        <p className="text-xs opacity-70">{sub}</p>
      </div>
    </Link>
  );
}

function StatusRow({ label, status, sub, confianza }: { label: string; status: string; sub?: string; confianza?: number }) {
  const dots: Record<string, string> = {
    conectado: "bg-green-500",
    activo: "bg-green-500",
    programado: "bg-blue-500",
    ok: "bg-green-500",
    error: "bg-red-500",
  };
  return (
    <div className="flex items-center justify-between py-1.5">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${dots[status] || "bg-slate-400"}`} />
        <span className="text-sm text-slate-700">{label}</span>
        {confianza && <ConfianzaBadge confianza={confianza} size="sm" />}
      </div>
      <div className="text-right">
        <span className="text-xs text-slate-500 capitalize">{status}</span>
        {sub && <p className="text-xs text-slate-400">{sub}</p>}
      </div>
    </div>
  );
}

function ActividadItem({ icono: Icon, color, texto, tiempo }: any) {
  return (
    <div className="flex items-start gap-2">
      <Icon size={14} className={`${color} mt-0.5 flex-shrink-0`} />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-700 truncate">{texto}</p>
        <p className="text-xs text-slate-400">{tiempo}</p>
      </div>
    </div>
  );
}
