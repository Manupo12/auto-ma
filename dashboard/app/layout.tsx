import type { Metadata } from "next";
import "./globals.css";
import { ClientLayout } from "@/components/ClientLayout";

export const metadata: Metadata = {
  title: "RILO SAS — Dashboard",
  description: "Sistema de documentación clínica para fisioterapia ocupacional",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <body className="min-h-screen bg-slate-50">
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}
