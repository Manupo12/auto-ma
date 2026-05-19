"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/hoy");
  }, [router]);
  return <div className="p-8 text-xl">Cargando…</div>;
}
