"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Calendar, User, FileText, MessageCircle, Folder, Mic } from "lucide-react";

const items = [
  { href: "/hoy", label: "Mi día", icon: Calendar },
  { href: "/pacientes", label: "Pacientes", icon: User },
  { href: "/formatos", label: "Documentos", icon: FileText },
  { href: "/subir-audio", label: "Subir audio", icon: Mic },
  { href: "/chat", label: "Hablar con Tomy", icon: MessageCircle },
  { href: "/archivos", label: "Mis archivos", icon: Folder },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <nav className="w-64 bg-white border-r border-slate-200 p-4 space-y-1">
      <div className="mb-6 p-3">
        <p className="text-2xl font-bold text-slate-800">RILO SAS</p>
        <p className="text-sm text-slate-500">Asistente Tomy</p>
      </div>
      {items.map(({ href, label, icon: Icon }) => {
        const active = pathname?.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-4 px-4 py-3 rounded-xl text-lg transition-colors ${
              active
                ? "bg-blue-600 text-white"
                : "text-slate-700 hover:bg-slate-100"
            }`}
          >
            <Icon size={26} />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
