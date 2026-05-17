"use client";

import { Shield, AlertTriangle, HelpCircle } from "lucide-react";

interface Props {
  confianza: number; // 0-100
  fuente?: string;   // "medifolios", "positiva", "audio", "manual_sandra"
  size?: "sm" | "md";
}

const COLORES = {
  verde: { bg: "bg-green-100", text: "text-green-700", icon: Shield },
  amarillo: { bg: "bg-amber-100", text: "text-amber-700", icon: AlertTriangle },
  rojo: { bg: "bg-red-100", text: "text-red-700", icon: HelpCircle },
};

const FUENTE_LABELS: Record<string, string> = {
  medifolios: "Medifolios",
  positiva: "ARL Positiva",
  audio: "Audio (Deepgram)",
  manual_sandra: "Manual (Sandra)",
};

export function ConfianzaBadge({ confianza, fuente, size = "sm" }: Props) {
  const color = confianza >= 80 ? "verde" : confianza >= 50 ? "amarillo" : "rojo";
  const palette = COLORES[color];
  const Icon = palette.icon;

  return (
    <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full ${palette.bg} ${palette.text} ${size === "sm" ? "text-xs" : "text-sm"}`}>
      <Icon size={size === "sm" ? 12 : 14} />
      <span className="font-medium">{confianza}%</span>
      {fuente && <span className="opacity-70">· {FUENTE_LABELS[fuente] || fuente}</span>}
    </div>
  );
}

export function SemaforoIcon({ confianza, size = 16 }: { confianza: number; size?: number }) {
  const color = confianza >= 80 ? "text-green-500" : confianza >= 50 ? "text-amber-500" : "text-red-500";
  const Icon = confianza >= 80 ? Shield : confianza >= 50 ? AlertTriangle : HelpCircle;
  return <Icon size={size} className={color} />;
}
