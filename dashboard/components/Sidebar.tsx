"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Users, FileText, MessageCircle,
  Upload, Settings, Activity, Stethoscope, FolderOpen
} from "lucide-react";
import clsx from "clsx";

const menuItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/pacientes", label: "Pacientes", icon: Users },
  { href: "/formatos", label: "Formatos", icon: FileText },
  { href: "/chat", label: "Chat con Tomy", icon: MessageCircle },
  { href: "/archivos", label: "Archivos", icon: FolderOpen },
  { href: "/subir-audio", label: "Subir Audio", icon: Upload },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="p-6 border-b border-slate-700">
        <div className="flex items-center gap-3">
          <Stethoscope size={28} className="text-blue-400" />
          <div>
            <h1 className="text-lg font-bold">RILO SAS</h1>
            <p className="text-xs text-slate-400">Rehabilitación Integral</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors",
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-slate-300 hover:bg-slate-700 hover:text-white"
              )}
            >
              <Icon size={20} />
              <span>{item.label}</span>
              {item.href === "/formatos" && (
                <span className="ml-auto bg-amber-500 text-xs px-1.5 py-0.5 rounded-full">7</span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-slate-700 text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-green-400" />
          <span>Sistema conectado</span>
        </div>
        <p className="mt-1">v0.1.0 — RILO Dashboard</p>
      </div>
    </div>
  );
}
