"use client";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { MobileMenu } from "@/components/MobileMenu";
import { Sidebar } from "@/components/Sidebar";

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (pathname !== "/login") {
      fetch((process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/whoami", { credentials: "include" })
        .then(r => r.json())
        .then(d => { if (!d.autenticado) router.push("/login"); })
        .catch(() => {});
    }
  }, [pathname, router]);

  return (
    <div className="flex min-h-screen">
      <aside className="hidden lg:flex w-64 bg-slate-800 text-white flex-col" suppressHydrationWarning>
        <Sidebar />
      </aside>
      <MobileMenu />
      <main className="flex-1 p-4 lg:p-8 pt-16 lg:pt-8 overflow-auto">
        {children}
      </main>
    </div>
  );
}
