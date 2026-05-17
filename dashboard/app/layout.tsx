import type { Metadata } from "next";
import "./globals.css";
import { MobileMenu } from "@/components/MobileMenu";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "RILO SAS — Dashboard",
  description: "Sistema de documentación clínica para fisioterapia ocupacional",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen bg-slate-50">
        <div className="flex min-h-screen">
          {/* Desktop sidebar */}
          <aside className="hidden lg:flex w-64 bg-slate-800 text-white flex-col">
            <Sidebar />
          </aside>

          {/* Mobile sidebar + hamburger (client component) */}
          <MobileMenu />

          {/* Main content */}
          <main className="flex-1 p-4 lg:p-8 pt-16 lg:pt-8 overflow-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
