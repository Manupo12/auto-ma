const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
const API = API_URL;

export async function login(pin: string): Promise<boolean> {
  try {
    const resp = await fetch(`${API}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin }),
      credentials: "include",
    });
    return resp.ok;
  } catch {
    return false;
  }
}

export async function logout(): Promise<void> {
  await fetch(`${API}/api/logout`, {
    method: "POST",
    credentials: "include",
  });
}

export async function whoami(): Promise<{
  autenticado: boolean;
  usuario: string | null;
}> {
  try {
    const resp = await fetch(`${API}/api/whoami`, { credentials: "include" });
    return resp.ok ? resp.json() : { autenticado: false, usuario: null };
  } catch {
    return { autenticado: false, usuario: null };
  }
}
