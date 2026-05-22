"use client";

import { useState, useEffect } from "react";
import { Menu, X } from "lucide-react";
import { Sidebar } from "./Sidebar";

export function MobileMenu() {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  if (!mounted) return null;

  return (
    <>
      <button
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-white rounded-lg shadow"
        onClick={() => setOpen(!open)}
        aria-label={open ? "Cerrar menú" : "Abrir menú"}
      >
        {open ? <X size={24} /> : <Menu size={24} />}
      </button>

      <aside
        className={`
          lg:hidden fixed inset-y-0 left-0 z-40
          w-64 bg-slate-800 text-white transform transition-transform
          ${open ? "translate-x-0" : "-translate-x-full"}
        `}
      >
        <Sidebar onNavigate={() => setOpen(false)} />
      </aside>

      {open && (
        <div
          className="lg:hidden fixed inset-0 z-30 bg-black/50"
          onClick={() => setOpen(false)}
        />
      )}
    </>
  );
}
