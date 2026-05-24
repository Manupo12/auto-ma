"use client";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

export function AuthGuard({ children }: { children: React.ReactNode }) {
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
  return <>{children}</>;
}
