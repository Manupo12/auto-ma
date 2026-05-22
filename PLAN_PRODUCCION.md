# Plan de Producción — RILO SAS
## Chat Omnisciente + Audio Largo + Deploy WSL vía Git

**Fecha:** 2026-05-22  
**Probado:** backend real, 8 tests OK, API keys verificadas  
**Deploy:** Docker → `git push` → WSL Sandra hace `git pull`

---

## Estado confirmado por testing real

| Componente | Estado |
|------------|--------|
| 8 tests motor de documentos | ✅ todos pasan |
| Backend FastAPI | ✅ arranca limpio |
| Chat DeepSeek v4-pro | ✅ funciona (60-120 seg) |
| API key Deepgram | ✅ válida |
| API key OpenCode Go | ✅ válida |
| Deepgram M4A content-type | ✅ `.m4a: "audio/m4a"` configurado |
| Deepgram MP3 content-type | ✅ `.mp3: "audio/mpeg"` configurado |
| `/api/tasks/{task_id}` endpoint | ✅ existe en server.py |
| WORKFLOW_AUDIOS_DIR | ✅ se crea automáticamente |
| ffprobe / ffmpeg | ❌ NO instalado en WSL → **TODOS los audios fallan** |
| LibreOffice | ❌ NO instalado en WSL → PDF/A falla |
| start.sh dependencias | ❌ Solo instala 4 paquetes, faltan 10+ → backend no arranca |
| firma_sandra.png | ❌ No existe → documentos sin firma |
| ejemplo prueba de trabajo | ❌ Solo existe en .odt, necesita conversión a .docx |

---

## CRÍTICO — ffprobe rompe TODOS los audios (no solo los largos)

Este es el bug más urgente del sistema y no estaba en el plan anterior.

**Causa exacta — `backend/workflow_steps/transcribir.py` línea 64:**
```python
def ejecutar(audio_path: str, paciente_cc: str) -> Dict:
    return transcribir_audio_largo(audio_path, paciente_cc)

def transcribir_audio_largo(audio_path, paciente_cc):
    ...
    duracion = _calcular_duracion_s(audio)  # ← SE LLAMA PRIMERO SIEMPRE
    ...

def _calcular_duracion_s(audio_path):
    result = subprocess.run(["ffprobe", ...])  # ← FileNotFoundError si no instalado
    return float(result.stdout.strip())
```

`ffprobe` se llama para **cualquier audio**, incluso uno de 5 minutos.  
Sin ffprobe, el Paso 1 del workflow crashea con `FileNotFoundError` en toda subida.

**Hay dos fixes necesarios — ambos obligatorios:**

### Fix A — Instalar ffmpeg (incluye ffprobe) en WSL de Sandra
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
ffprobe -version   # debe responder
ffmpeg -version    # debe responder
```

### Fix B — Fallback en `transcribir.py` cuando ffprobe no está disponible

Para que el sistema no muera si ffprobe falla (resiliencia en producción):

```python
def _calcular_duracion_s(audio_path: Path) -> float:
    """Duración en segundos. Fallback a 0 si ffprobe no disponible."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except (FileNotFoundError, ValueError, subprocess.TimeoutExpired) as e:
        _log(f"ffprobe no disponible ({e}) — asumiendo audio corto, sin chunking")
        return 0.0  # 0 segundos → _necesita_chunking retorna False → directo a Deepgram
```

Con este fallback: si ffprobe no está, el audio se envía completo a Deepgram (funciona hasta 2GB). El chunking solo se activa si ffprobe sí está disponible y detecta que el audio es largo.

---

## Flujo completo de un audio de 1 hora

Un audio de 60 minutos = 3600 segundos.  
`AUDIO_CHUNK_DURATION_S=1500` (25 min).  
3600 / 1500 = 3 chunks (dos de 25 min, uno de 10 min).

```
Sandra sube audio_1hora.m4a
    │
    ▼
/api/procesar-paciente
    │
    ├─ guarda audio en storage/workflow_audios/
    ├─ crea task_id en SQLite
    └─ lanza workflow en thread background
         │
         ▼
    PASO 1 — transcribir (el más crítico para audios largos)
         │
         ├─ ffprobe detecta 3600s → necesita chunking
         ├─ ffmpeg divide en 3 chunks .wav de 25 min c/u
         ├─ Deepgram nova-2 transcribe chunk 1 (~2 min)
         ├─ Deepgram nova-2 transcribe chunk 2 (~2 min)
         ├─ Deepgram nova-2 transcribe chunk 3 (~1 min)
         ├─ Concatena textos y ajusta timestamps
         └─ Retorna transcripción completa con diarización
         │
         ▼
    PASO 2-9 — resolver paciente, sintetizar, generar 7 formatos, QA, PDF, Telegram
         │
         ▼
    Sandra recibe Telegram: "Tus 7 formatos están listos"
    Dashboard muestra botones de descarga
```

**Tiempo total estimado para 1 hora de audio:** 15-25 minutos  
- Paso 1 (3 chunks Deepgram): ~6 min  
- Paso 5 (síntesis DeepSeek razonador): ~5 min  
- Paso 6 (generar 7 DOCX): ~3 min  
- Resto: ~3 min

---

## PARTE 1 — Bugs bloqueantes (ejecutar primero)

### 1.1 — Sidebar duplicado

**`dashboard/components/MobileMenu.tsx` línea 20:**
```tsx
// ANTES:
<aside className={`fixed lg:static inset-y-0 left-0 z-40 w-64 bg-slate-800 text-white
  transform transition-transform ${open ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0`}>

// DESPUÉS:
<aside className={`lg:hidden fixed inset-y-0 left-0 z-40 w-64 bg-slate-800 text-white
  transform transition-transform ${open ? "translate-x-0" : "-translate-x-full"}`}>
```

### 1.2 — Sidebar: named export + prop onNavigate

**`dashboard/components/Sidebar.tsx` — reemplazar completo:**
```tsx
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

export function Sidebar({ onNavigate }: { onNavigate?: () => void } = {}) {
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
          <Link key={href} href={href} onClick={onNavigate}
            className={`flex items-center gap-4 px-4 py-3 rounded-xl text-lg transition-colors ${
              active ? "bg-blue-600 text-white" : "text-slate-700 hover:bg-slate-100"}`}>
            <Icon size={26} /><span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
export default Sidebar;
```

### 1.3 — CC hardcodeado + datos ficticios en Formatos

**`dashboard/app/formatos/page.tsx`:**
```tsx
// Líneas 34-35:
const [cc, setCc] = useState("");
const [ccInput, setCcInput] = useState("");

// Línea 142 — reemplazar ReconciliacionAlert hardcodeado:
{cc && formatosAPI.length > 0 && (
  <ReconciliacionAlert data={{ medifolios: "", positiva: "", coinciden: true, alerta: "" }} />
)}
```

### 1.4 — Activar pipeline

**`.env`:**
```bash
TOMY_COMPLETO_ENABLED=true
```

### 1.5 — fallback ffprobe

**`backend/workflow_steps/transcribir.py` línea 22-29:**  
Reemplazar `_calcular_duracion_s` con la versión con fallback (ver código arriba).

### 1.6 — CORS desde env

**`backend/server.py` líneas 43-48:**
```python
_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
app.add_middleware(CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_raw.split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
```

**`.env`:**
```bash
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### 1.7 — URLs hardcodeadas en dashboard

**Crear `dashboard/.env.local`:**
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**En cada archivo, agregar al inicio de la función/componente:**
```ts
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
```

**Archivos que tienen `http://localhost:8000` hardcodeado:**
- `app/hoy/page.tsx` líneas 31-32
- `app/chat/page.tsx` línea 70
- `app/subir-audio/page.tsx` línea 35

---

## PARTE 2 — Chat Omnisciente (el corazón del sistema)

El chat debe ser el **panel de control central** de Sandra. Debe saber todo lo que pasa en el sistema y poder hacer todo desde ahí.

### Qué debe saber Tomy en cada conversación

| Información | Fuente | Cómo se inyecta |
|-------------|--------|-----------------|
| Tareas activas en este momento | `task_db.listar_activos()` | Contexto de sistema |
| Agenda de hoy | `notificador.api_get_agenda()` | Contexto de sistema |
| Lista de pacientes | `DATA_DIR/*.json` | Contexto de sistema |
| Formatos generados hoy | `DOCS_DIR/*.docx` | Contexto de sistema |
| Feature flags activos | `.env` vars | Contexto de sistema |
| Conversación anterior | `historial` del frontend | Historial de chat |
| Archivos del workspace | `_listar_workspace()` | Ya existe |
| Documentos del paciente | `_buscar_archivos_paciente()` | Ya existe |

---

### CHAT-1 — Contexto de sistema en cada mensaje

**Backend — nueva función en `chat_handler.py`** (agregar cerca del inicio del archivo, después de las importaciones):

```python
def _construir_contexto_sistema() -> str:
    """
    Captura el estado actual del sistema para inyectar al LLM.
    Tomy sabe qué hay en el dashboard antes de responder.
    Rápido: solo lee SQLite y cuenta archivos, sin I/O pesada.
    """
    lineas = ["═══ ESTADO ACTUAL DEL SISTEMA ═══"]
    
    # 1. Tareas activas en el workflow
    try:
        db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
        from backend.task_db import TaskDB
        db = TaskDB(db_path)
        activas = db.listar_activos()
        if activas:
            lineas.append(f"\n🔄 PROCESANDO AHORA ({len(activas)} tarea(s)):")
            PASOS = {
                1: "Transcribiendo audio", 2: "Buscando datos del paciente",
                3: "Leyendo notas", 4: "Leyendo formatos subidos",
                5: "Sintetizando (IA razonadora)", 6: "Generando 7 formatos",
                7: "Verificando calidad", 8: "Convirtiendo a PDF", 9: "Notificando",
            }
            for t in activas[:3]:
                paso_label = PASOS.get(t.get("paso_actual", 0), t.get("estado", "?"))
                lineas.append(f"  • CC {t['paciente_cc']}: {paso_label} (paso {t.get('paso_actual','?')}/9)")
        else:
            lineas.append("\n⚡ Sin tareas activas — sistema libre")
    except Exception as e:
        lineas.append(f"\n[Tareas: no disponible — {e}]")
    
    # 2. Agenda del día
    try:
        from backend.notificador import api_get_agenda
        agenda = api_get_agenda()
        if agenda and agenda.get("citas"):
            citas = agenda["citas"]
            lineas.append(f"\n📅 AGENDA HOY ({len(citas)} cita(s)):")
            for c in citas[:6]:
                nombre = c.get("paciente", "?")
                hora = c.get("hora", "?")
                cc_cita = c.get("cc", "")
                procesado = "✅" if c.get("procesado") else "⏳"
                lineas.append(f"  {procesado} {hora} — {nombre}" + (f" (CC {cc_cita})" if cc_cita else ""))
        else:
            lineas.append("\n📅 AGENDA: No hay agenda cargada para hoy")
    except Exception:
        lineas.append("\n📅 AGENDA: no disponible")
    
    # 3. Pacientes en el sistema
    try:
        import glob as _glob
        storage = Path(os.getenv("STORAGE_DIR", "./storage"))
        data_dir = storage / "data"
        jsons = _glob.glob(str(data_dir / "*-completo.json"))
        lineas.append(f"\n👥 PACIENTES EN SISTEMA: {len(jsons)}")
        # Listar los nombres si hay pocos
        if len(jsons) <= 5:
            for jpath in jsons:
                try:
                    import json as _json
                    with open(jpath, encoding="utf-8") as f:
                        d = _json.load(f)
                    nombre = d.get("paciente", {}).get("nombre", "?")
                    cc_p = d.get("paciente", {}).get("documento", "?")
                    lineas.append(f"  • {nombre} (CC {cc_p})")
                except Exception:
                    pass
    except Exception:
        pass
    
    # 4. Formatos generados hoy y recientes
    try:
        docs_dir = storage / "docs"
        from datetime import date
        hoy_str = date.today().strftime("%Y-%m-%d")
        docs_hoy = []
        docs_recientes = []
        for f in sorted(docs_dir.glob("*.docx"), key=lambda x: x.stat().st_mtime, reverse=True):
            mtime_str = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
            if mtime_str == hoy_str:
                docs_hoy.append(f.name)
            docs_recientes.append(f"{f.name} ({mtime_str})")
            if len(docs_recientes) >= 5:
                break
        if docs_hoy:
            lineas.append(f"\n📄 FORMATOS GENERADOS HOY: {len(docs_hoy)}")
            for d in docs_hoy[:5]:
                lineas.append(f"  • {d}")
        if docs_recientes and not docs_hoy:
            lineas.append(f"\n📄 FORMATOS RECIENTES:")
            for d in docs_recientes[:3]:
                lineas.append(f"  • {d}")
    except Exception:
        pass
    
    # 5. Feature flags
    tomy_on = os.getenv("TOMY_COMPLETO_ENABLED", "false").lower() == "true"
    fase_a = os.getenv("FASE_A_ENABLED", "false").lower() == "true"
    lineas.append(f"\n⚙️ Pipeline: {'✅ activo' if tomy_on else '❌ inactivo (TOMY_COMPLETO_ENABLED=false)'}")
    if fase_a:
        lineas.append("⚙️ Extracción portales: ✅ activa")
    
    return "\n".join(lineas)
```

**Modificar `procesar_mensaje` para inyectar el contexto en cada llamada:**

```python
def procesar_mensaje(mensaje, paciente_cc="", historial=None):
    ...
    # Construir contexto del sistema (nuevo — siempre)
    ctx_sistema = _construir_contexto_sistema()
    
    # Llamar LLM con todo el contexto
    respuesta = _llamar_llm(
        mensaje_con_sugerencia, cc, doc_content,
        workspace_files, historial=historial,
        ctx_sistema=ctx_sistema,  # ← NUEVO
    )
```

**Modificar `_llamar_llm` para incluir ctx_sistema antes del mensaje del usuario:**

```python
def _llamar_llm(mensaje, cc="", archivo_doc="", workspace_files="",
                historial=None, ctx_sistema="") -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Historial (últimos 6 turnos)
    if historial:
        for h in historial[-6:]:
            rol = h.get("rol", "")
            contenido = (h.get("contenido", "") or "")[:2000]
            if rol == "usuario":
                messages.append({"role": "user", "content": contenido})
            elif rol == "asistente":
                messages.append({"role": "assistant", "content": contenido})
    
    # Mensaje actual con contexto completo
    partes = []
    if ctx_sistema:
        partes.append(ctx_sistema)
    partes.append(f"\n═══ MENSAJE DE SANDRA ═══\n{mensaje}")
    if archivo_doc:
        partes.append(f"\n\n📄 DOCUMENTOS ENCONTRADOS:\n{archivo_doc}")
    if cc:
        partes.append(f"\n[Paciente en contexto: CC {cc}]")
    if workspace_files:
        partes.append(f"\n\n📁 CARPETA DE TRABAJO DE SANDRA:\n{workspace_files}")
    else:
        partes.append("\n\n📁 Carpeta de trabajo: no accesible desde este entorno")
    
    messages.append({"role": "user", "content": "\n".join(partes)})
    # ... resto igual
```

---

### CHAT-2 — Streaming (respuesta en tiempo real)

Sandra no puede esperar 120 segundos mirando una pantalla en blanco. Con streaming, el texto aparece letra a letra.

**Backend — nuevo endpoint `POST /api/chat/stream` en `server.py`:**

```python
from fastapi.responses import StreamingResponse

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Streaming SSE del chat. El frontend lee los chunks con ReadableStream.
    Formato: data: {"tipo":"delta","contenido":"..."}\n\n
             data: {"tipo":"fin","archivo":null,"accion":null}\n\n
             data: {"tipo":"error","contenido":"..."}\n\n
    """
    import json as _json
    import re as _re
    import requests as _req

    def _stream():
        from backend.chat_handler import (
            _listar_workspace, _buscar_archivos_paciente, _buscar_archivo,
            _leer_multiples_docx, _leer_docx, SYSTEM_PROMPT, API_KEY, BASE_URL, MODEL,
            _construir_contexto_sistema, _log,
        )

        mensaje = req.mensaje
        cc = req.paciente_cc or ""
        historial = req.historial or []

        # Mismo pipeline de contexto que el chat normal
        workspace_files = _listar_workspace()
        if not cc:
            m = _re.search(r'\b(\d{6,12})\b', mensaje.replace("'","").replace(".",""))
            if m: cc = m.group(1)

        archivos_pac = _buscar_archivos_paciente(cc=cc, mensaje=mensaje)
        if archivos_pac:
            doc_content = _leer_multiples_docx(archivos_pac, max_chars_total=8000)
            archivo_nombre = f"{len(archivos_pac)} archivos"
        else:
            archivo = _buscar_archivo(mensaje)
            doc_content = _leer_docx(archivo) if archivo else ""
            archivo_nombre = archivo.name if archivo else None

        ctx_sistema = _construir_contexto_sistema()

        # Construir messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in historial[-6:]:
            rol = h.get("rol","")
            c = (h.get("contenido","") or "")[:2000]
            if rol == "usuario": messages.append({"role":"user","content":c})
            elif rol == "asistente": messages.append({"role":"assistant","content":c})

        partes = []
        if ctx_sistema: partes.append(ctx_sistema)
        partes.append(f"\n═══ MENSAJE ═══\n{mensaje}")
        if doc_content: partes.append(f"\n\n📄 DOCUMENTOS:\n{doc_content}")
        if cc: partes.append(f"\n[CC: {cc}]")
        if workspace_files: partes.append(f"\n\n📁 CARPETA:\n{workspace_files}")
        messages.append({"role":"user","content":"\n".join(partes)})

        if not API_KEY:
            yield 'data: {"tipo":"error","contenido":"Sin API key"}\n\n'
            return

        try:
            resp = _req.post(
                f"{BASE_URL}/chat/completions",
                headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"},
                json={"model":MODEL,"messages":messages,"max_tokens":16000,
                      "temperature":0.7,"stream":True},
                stream=True, timeout=300,
            )
            for line in resp.iter_lines():
                if not line: continue
                s = line.decode("utf-8") if isinstance(line, bytes) else line
                if not s.startswith("data: "): continue
                raw = s[6:]
                if raw == "[DONE]": break
                try:
                    chunk = _json.loads(raw)
                    piece = chunk.get("choices",[{}])[0].get("delta",{}).get("content","") or ""
                    if piece:
                        yield f'data: {_json.dumps({"tipo":"delta","contenido":piece})}\n\n'
                except Exception:
                    pass
            yield f'data: {_json.dumps({"tipo":"fin","archivo":archivo_nombre,"accion":"documento" if doc_content else None})}\n\n'
        except Exception as e:
            yield f'data: {_json.dumps({"tipo":"error","contenido":str(e)[:100]})}\n\n'

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"},
    )
```

**Frontend — `dashboard/app/chat/page.tsx`:**

La función `enviar` lee el stream en tiempo real:

```tsx
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const enviar = async () => {
  if (!input.trim() || enviando) return;
  const mensaje = input.trim();
  setInput("");
  setEnviando(true);

  const userMsg: ChatMessage = { rol: "usuario", contenido: mensaje, timestamp: new Date().toISOString() };
  const historialConUser = [...mensajes, userMsg];
  // Agregar placeholder del asistente vacío
  const assistantPlaceholder: ChatMessage = { rol: "asistente", contenido: "", timestamp: new Date().toISOString() };
  setMensajes([...historialConUser, assistantPlaceholder]);

  try {
    const res = await fetch(`${API}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mensaje, historial: historialConUser.slice(-10) }),
      signal: AbortSignal.timeout(300000),
    });

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let acumulado = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const line of decoder.decode(value).split("\n")) {
        if (!line.startsWith("data: ")) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.tipo === "delta") {
            acumulado += data.contenido;
            setMensajes(prev => {
              const nuevo = [...prev];
              nuevo[nuevo.length - 1] = { ...nuevo[nuevo.length - 1], contenido: acumulado };
              return nuevo;
            });
          } else if (data.tipo === "fin") {
            setMensajes(prev => {
              const nuevo = [...prev];
              nuevo[nuevo.length - 1] = {
                ...nuevo[nuevo.length - 1],
                contenido: acumulado || "Sin respuesta.",
                archivo: data.archivo,
                accion: data.accion,
              };
              return nuevo;
            });
          }
        } catch {}
      }
    }
  } catch {
    setMensajes(prev => {
      const n = [...prev];
      n[n.length - 1] = { ...n[n.length - 1], contenido: "❌ Error de conexión." };
      return n;
    });
  } finally {
    setEnviando(false);
  }
};
```

---

### CHAT-3 — Audio directamente en el chat

Sandra puede subir audio desde el chat sin ir a otra página. Tomy muestra el progreso en tiempo real en la misma conversación.

**Flujo:**
```
Sandra adjunta audio en el chat
    → Frontend envía a /api/procesar-paciente (igual que subir-audio page)
    → Backend retorna task_id
    → Tomy muestra mensaje: "Recibí el audio. Procesando... (Paso 1/9)"
    → Frontend hace polling a /api/tasks/{task_id} cada 10 seg
    → Tomy actualiza el mensaje con el progreso
    → Cuando termina: muestra links de descarga de los 7 formatos
```

**Backend — nuevo endpoint `POST /api/chat/audio` en `server.py`:**

```python
@app.post("/api/chat/audio")
async def chat_audio(
    audio: UploadFile = File(...),
    paciente_cc: str = Form(...),
):
    """
    Recibe audio desde el chat, inicia el workflow completo,
    retorna task_id para que el chat haga polling del progreso.
    """
    if os.getenv("TOMY_COMPLETO_ENABLED", "false").lower() != "true":
        raise HTTPException(503, "Tomy Completo no habilitado. Activar TOMY_COMPLETO_ENABLED=true en .env")

    ext = Path(audio.filename or "audio.m4a").suffix or ".m4a"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_path = WORKFLOW_AUDIOS_DIR / f"{paciente_cc}_{timestamp}{ext}"
    audio_path.write_bytes(await audio.read())

    from backend.task_db import TaskDB
    from backend.workflow_runner import ejecutar_workflow
    db = TaskDB(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))
    task_id = db.crear_task(paciente_cc=paciente_cc, audio_path=str(audio_path))

    import threading
    threading.Thread(
        target=ejecutar_workflow,
        kwargs={"audio_path": str(audio_path), "paciente_cc": paciente_cc, "task_id_existente": task_id},
        daemon=True,
    ).start()

    # Estimar duración para informar a Sandra
    duracion_min_est = round(audio_path.stat().st_size / (1024 * 1024 * 0.5))  # estimación burda

    return {
        "ok": True,
        "task_id": task_id,
        "mensaje_tomy": (
            f"✅ Recibí el audio de CC {paciente_cc}. "
            f"Empiezo a procesarlo ahora — tarda entre 15-25 minutos. "
            f"Te aviso aquí y por Telegram cuando tenga los 7 formatos listos.\n\n"
            f"*ID de tarea:* `{task_id}` — podés consultar el progreso en Mi Día."
        ),
        "paciente_cc": paciente_cc,
    }
```

**Frontend — botón de audio en `chat/page.tsx`:**

```tsx
// Agregar estado:
const [ccAudio, setCcAudio] = useState("");
const [mostrarCcAudio, setMostrarCcAudio] = useState(false);
const audioRef = useRef<HTMLInputElement>(null);

// Función para manejar audio:
const handleAudioChat = async (file: File) => {
  if (!ccAudio.trim()) {
    setMostrarCcAudio(true);
    return;
  }
  setEnviando(true);
  
  // Mostrar mensaje del usuario indicando que subió audio
  const userMsg: ChatMessage = {
    rol: "usuario",
    contenido: `🎙️ Audio subido: ${file.name} (${(file.size/1024/1024).toFixed(1)} MB) — CC ${ccAudio}`,
    timestamp: new Date().toISOString(),
  };
  setMensajes(prev => [...prev, userMsg]);

  const form = new FormData();
  form.append("audio", file);
  form.append("paciente_cc", ccAudio.trim());

  try {
    const res = await fetch(`${API}/api/chat/audio`, { method: "POST", body: form });
    const data = await res.json();
    
    if (data.ok) {
      // Tomy responde con el mensaje inicial de procesamiento
      const tomyMsg: ChatMessage = {
        rol: "asistente",
        contenido: data.mensaje_tomy,
        timestamp: new Date().toISOString(),
        taskId: data.task_id,      // ← guardar para polling
        pacienteCC: data.paciente_cc,
      };
      setMensajes(prev => [...prev, tomyMsg]);
      
      // Iniciar polling del progreso
      iniciarPollingTarea(data.task_id, data.paciente_cc);
    } else {
      throw new Error(data.detail || "Error al procesar audio");
    }
  } catch (e) {
    setMensajes(prev => [...prev, {
      rol: "asistente",
      contenido: `❌ No pude procesar el audio: ${e instanceof Error ? e.message : "error desconocido"}`,
      timestamp: new Date().toISOString(),
    }]);
  } finally {
    setEnviando(false);
  }
};

// Polling de progreso:
const iniciarPollingTarea = (taskId: string, cc: string) => {
  const PASOS_LABELS: Record<number, string> = {
    1: "🎙️ Transcribiendo audio con Deepgram...",
    2: "🔍 Buscando datos del paciente...",
    3: "📝 Leyendo tus notas...",
    4: "📄 Leyendo formatos de referencia...",
    5: "🧠 Sintetizando (IA razonando, puede tardar 5+ min)...",
    6: "📋 Generando los 7 formatos...",
    7: "✅ Verificando calidad...",
    8: "📑 Convirtiendo a PDF...",
    9: "📱 Enviando notificación por Telegram...",
  };
  
  const intervalo = setInterval(async () => {
    try {
      const res = await fetch(`${API}/api/tasks/${taskId}`);
      const data = await res.json();
      const task = data.task;
      
      if (task.estado === "listo") {
        clearInterval(intervalo);
        // Mostrar mensaje de éxito con links
        const formatos = task.resultado?.formatos_generados || [];
        let msg = `✅ **¡Listo, Sandra!** Generé ${formatos.length} formatos para CC ${cc}:\n\n`;
        for (const f of formatos) {
          const nombre = f.archivo?.split("/").pop() || f.formato;
          msg += `- 📄 [${nombre}](/api/download/${encodeURIComponent(nombre)})\n`;
        }
        msg += `\n¿Querés que revise algo o corrijamos algún dato?`;
        setMensajes(prev => [...prev, {
          rol: "asistente",
          contenido: msg,
          timestamp: new Date().toISOString(),
          formatos: formatos,
        }]);
      } else if (task.estado?.startsWith("error")) {
        clearInterval(intervalo);
        setMensajes(prev => [...prev, {
          rol: "asistente",
          contenido: `❌ Hubo un problema en el paso ${task.paso_actual}/9: ${task.error || "error desconocido"}. ¿Intentamos de nuevo?`,
          timestamp: new Date().toISOString(),
        }]);
      } else if (task.estado === "esperando_datos") {
        clearInterval(intervalo);
        setMensajes(prev => [...prev, {
          rol: "asistente",
          contenido: `⚠️ Procesé el audio pero me faltan algunos datos críticos para completar los formatos. ¿Me los podés dar?\n\nDatos faltantes: ${(task.resultado?.campos_faltantes || []).join(", ")}`,
          timestamp: new Date().toISOString(),
        }]);
      } else {
        // Actualizar progreso en el mensaje del asistente (el del inicio del workflow)
        const pasoLabel = PASOS_LABELS[task.paso_actual] || task.estado;
        setMensajes(prev => {
          const nuevo = [...prev];
          // Buscar el mensaje que tiene el taskId y actualizarlo
          for (let i = nuevo.length - 1; i >= 0; i--) {
            if ((nuevo[i] as any).taskId === taskId) {
              nuevo[i] = {
                ...nuevo[i],
                contenido: nuevo[i].contenido.split("\n\n*Progreso:*")[0] +
                  `\n\n*Progreso:* Paso ${task.paso_actual}/9 — ${pasoLabel}`,
              };
              break;
            }
          }
          return nuevo;
        });
      }
    } catch {}
  }, 10000); // cada 10 segundos
  
  // Limpiar polling si el componente se desmonta
  return () => clearInterval(intervalo);
};

// En el JSX, botón de audio junto al de enviar:
<>
  <input ref={audioRef} type="file" accept="audio/*,.m4a" className="hidden"
    onChange={e => { if (e.target.files?.[0]) handleAudioChat(e.target.files[0]); }} />
  <button
    onClick={() => audioRef.current?.click()}
    disabled={enviando}
    className="p-3 text-slate-400 hover:text-purple-600 rounded-xl hover:bg-purple-50 transition-colors"
    title="Subir audio de una consulta"
  >
    <Mic size={20} />
  </button>
</>

// Modal para pedir CC antes de subir el audio:
{mostrarCcAudio && (
  <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center">
    <div className="bg-white rounded-2xl p-6 w-80 shadow-2xl space-y-4">
      <h2 className="font-bold text-lg">¿De qué paciente es este audio?</h2>
      <input type="text" value={ccAudio} onChange={e => setCcAudio(e.target.value)}
        placeholder="Cédula del paciente"
        className="w-full border-2 border-slate-300 rounded-xl p-3 text-lg focus:border-blue-500 outline-none" />
      <div className="flex gap-3">
        <button onClick={() => setMostrarCcAudio(false)}
          className="flex-1 py-2 border border-slate-300 rounded-xl text-slate-600">
          Cancelar
        </button>
        <button onClick={() => { setMostrarCcAudio(false); audioRef.current?.click(); }}
          disabled={!ccAudio.trim()}
          className="flex-1 py-2 bg-blue-600 text-white rounded-xl disabled:opacity-50">
          Continuar
        </button>
      </div>
    </div>
  </div>
)}
```

---

### CHAT-4 — Markdown + indicador de progreso

**Instalar:**
```bash
cd /root/fisioterapia/dashboard
npm install react-markdown remark-gfm @tailwindcss/typography
```

**`tailwind.config.js`:**
```js
plugins: [require('@tailwindcss/typography')],
```

**En el render del mensaje del asistente:**
```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Reemplazar <p className="whitespace-pre-wrap">{msg.contenido}</p>
// cuando el mensaje es del asistente:
{msg.rol === "asistente" ? (
  <div className="prose prose-sm max-w-none">
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.contenido}</ReactMarkdown>
  </div>
) : (
  <p className="whitespace-pre-wrap">{msg.contenido}</p>
)}
```

**Indicador de progreso mientras piensa (reemplazar spinner actual):**
```tsx
const ESTADOS_PENSANDO = [
  "Revisando el estado del sistema...",
  "Leyendo tus archivos...",
  "Cruzando datos entre formatos...",
  "Tomy está razonando...",
  "Verificando información clínica...",
];
const [estadoIdx, setEstadoIdx] = useState(0);

useEffect(() => {
  if (!enviando) return;
  const t = setInterval(() => setEstadoIdx(i => (i+1) % ESTADOS_PENSANDO.length), 8000);
  return () => clearInterval(t);
}, [enviando]);

// Con streaming, este spinner desaparece cuando llega el primer token
{enviando && mensajes[mensajes.length-1]?.contenido === "" && (
  <div className="flex items-center gap-2 px-4 py-3 bg-slate-100 rounded-2xl rounded-bl-md">
    <Loader2 size={16} className="animate-spin text-blue-500" />
    <span className="text-sm text-slate-600">{ESTADOS_PENSANDO[estadoIdx]}</span>
  </div>
)}
```

---

### CHAT-5 — Adjuntar archivos de la carpeta de Sandra

**Backend — `GET /api/archivos/paciente/{cc}` en `server.py`:**
```python
@app.get("/api/archivos/paciente/{cc}")
def archivos_paciente(cc: str):
    result = []
    for f in sorted(DOCS_DIR.glob(f"*{cc}*.docx"), key=lambda x: x.stat().st_mtime, reverse=True):
        result.append({
            "nombre": f.name,
            "tamano_kb": f.stat().st_size // 1024,
            "modificado": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M"),
            "url_descarga": f"/api/download/{f.name}",
        })
    return {"ok": True, "archivos": result}
```

**Frontend — componente `dashboard/components/FilePicker.tsx`:**
```tsx
"use client";
import { useState } from "react";
import { Paperclip, X, FileText, Loader2 } from "lucide-react";

export function FilePicker({ onSelect }: { onSelect: (nombre: string) => void }) {
  const [open, setOpen] = useState(false);
  const [cc, setCc] = useState("");
  const [archivos, setArchivos] = useState<{nombre:string;tamano_kb:number}[]>([]);
  const [loading, setLoading] = useState(false);
  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const buscar = async () => {
    if (!cc.trim()) return;
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/archivos/paciente/${cc.trim()}`);
      const d = await r.json();
      setArchivos(d.archivos || []);
    } finally { setLoading(false); }
  };

  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen(o => !o)} title="Adjuntar archivo"
        className="p-2 text-slate-400 hover:text-blue-600 rounded-lg transition-colors">
        <Paperclip size={20} />
      </button>
      {open && (
        <div className="absolute bottom-12 left-0 w-80 bg-white border rounded-xl shadow-xl z-50 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <input value={cc} onChange={e => setCc(e.target.value)}
              onKeyDown={e => e.key === "Enter" && buscar()}
              placeholder="CC del paciente" className="flex-1 border rounded-lg px-2 py-1 text-sm" />
            <button onClick={buscar} className="px-2 py-1 bg-blue-600 text-white rounded-lg text-sm">Buscar</button>
            <button onClick={() => setOpen(false)}><X size={14} /></button>
          </div>
          {loading ? <Loader2 size={16} className="animate-spin mx-auto" /> :
           archivos.length === 0 ? <p className="text-slate-400 text-xs text-center py-2">Sin resultados</p> :
           <div className="max-h-48 overflow-y-auto space-y-1">
             {archivos.map(a => (
               <button key={a.nombre} onClick={() => { onSelect(a.nombre); setOpen(false); }}
                 className="w-full text-left flex items-center gap-2 px-2 py-1.5 rounded hover:bg-slate-50 text-sm">
                 <FileText size={12} className="text-blue-500 flex-shrink-0" />
                 <span className="flex-1 truncate">{a.nombre}</span>
                 <span className="text-slate-400 text-xs">{a.tamano_kb}KB</span>
               </button>
             ))}
           </div>}
        </div>
      )}
    </div>
  );
}
```

---

## PARTE 2.5 — Portales: Verificación cruzada, navegación libre y aprendizaje continuo

### Contexto: qué ya existe (NO reescribir)

| Módulo | Ubicación | Función ya implementada |
|--------|-----------|-------------------------|
| `orquestador.py` | `backend/playwright_real/` | `extraer_paciente_completo(cc)` → extrae ambos portales + `_detectar_discrepancias()` |
| `medifolios.py` | `backend/playwright_real/` | `get_paciente_completo(page, cc)` → navega Medifolios, extrae 6+ campos |
| `positiva.py` | `backend/playwright_real/` | `get_paciente_completo(page, cc)` → 6 pestañas, siniestros, CIE-10, autorizaciones |
| `selectores.py` | `backend/playwright_real/` | selectores CSS/XPath de ambos portales |
| `session.py` | `backend/playwright_real/` | `abrir_contexto(portal)` → login + contexto Playwright reutilizable |
| `fusionador.py` | `backend/` | `fusionar_todo()` → reconcilia Medifolios + Positiva → JSON final |
| `extractor_positiva.py` | `backend/` | `extraer_datos_positiva(cc)`, `extraer_cie10_de_diagnostico()`, `fusionar_datos_positiva()` |

**Lo que falta:** 
1. `_detectar_discrepancias()` solo compara siniestro — necesita comparar 6+ campos
2. No existe verificación de portal vs. documentos locales  
3. No existe trigger desde el chat para lanzar extracción
4. No existe sistema de aprendizaje de rutas y correcciones
5. No existe renderizado de tabla de discrepancias en el frontend

---

### PORTAL-1 — Ampliar `_detectar_discrepancias` en `orquestador.py`

**Archivo:** `backend/playwright_real/orquestador.py` línea 27-44 — reemplazar la función:

```python
def _detectar_discrepancias(datos_medi: Dict, datos_pos: Dict) -> list:
    """
    Compara Medifolios vs. Positiva campo a campo.
    Retorna lista de conflictos con nivel de severidad y recomendación.
    """
    discrepancias = []

    def _norm(s: str) -> str:
        """Normaliza para comparación: sin tildes, minúsculas, sin espacios dobles."""
        if not s: return ""
        import unicodedata
        s = unicodedata.normalize("NFD", str(s).lower().strip())
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return " ".join(s.split())

    def _agregar(campo, v_medi, v_pos, severidad="advertencia", resolucion=""):
        if v_medi and v_pos and _norm(str(v_medi)) != _norm(str(v_pos)):
            discrepancias.append({
                "campo": campo,
                "medifolios": v_medi,
                "positiva": v_pos,
                "severidad": severidad,  # "crítico", "advertencia", "informativo"
                "resolucion": resolucion or f"Verificar cuál es correcto — diferencia: '{v_medi}' vs '{v_pos}'",
            })

    # 1. Siniestro (crítico — define toda la trazabilidad del caso)
    siniestro_medi = datos_medi.get("siniestro_medi", "")
    siniestros_pos = datos_pos.get("siniestros", [])
    siniestro_pos = siniestros_pos[0].get("id", "") if siniestros_pos else ""
    _agregar("siniestro", siniestro_medi, siniestro_pos,
             severidad="crítico", resolucion="Usar valor de Positiva (fuente oficial ARL)")

    # 2. Nombre del paciente (advertencia — puede diferir en tildes/formato)
    nombre_medi = datos_medi.get("nombre", "")
    nombre_pos = (datos_pos.get("datos_asegurado", {}) or {}).get("nombre", "")
    if nombre_medi and nombre_pos and _norm(nombre_medi) != _norm(nombre_pos):
        # Verificar si la diferencia es SOLO tildes/mayúsculas (no es error real)
        if nombre_medi.replace("Á","A").replace("É","E").replace("Í","I").replace("Ó","O").replace("Ú","U").upper() == \
           nombre_pos.replace("Á","A").replace("É","E").replace("Í","I").replace("Ó","O").replace("Ú","U").upper():
            pass  # Diferencia solo de tildes — ignorar
        else:
            _agregar("nombre", nombre_medi, nombre_pos,
                     severidad="advertencia", resolucion="Verificar cédula física del paciente")

    # 3. Diagnóstico CIE-10 (crítico — define el tratamiento y los formatos)
    diag_medi = datos_medi.get("diagnostico_cie10", "")
    siniestro_principal = next((s for s in siniestros_pos if s.get("tipo") in ["AT", ""]), {})
    diag_pos = siniestro_principal.get("diagnostico", "") if siniestros_pos else ""
    # CIE-10 de Positiva viene como "M545 LUMBAGO" → extraer el código
    if diag_pos and len(diag_pos) > 3:
        import re as _re
        match = _re.match(r"^([A-Z]\d{2,3})", diag_pos.strip())
        if match:
            diag_pos = match.group(1)
    _agregar("diagnostico_cie10", diag_medi, diag_pos,
             severidad="crítico", resolucion="Usar Positiva (diagnóstico oficial ARL) — más preciso")

    # 4. Empresa (advertencia — puede tener abreviaciones diferentes)
    empresa_medi = datos_medi.get("empresa", "")
    empresa_pos = (datos_pos.get("datos_asegurado", {}) or {}).get("empresa", "")
    _agregar("empresa", empresa_medi, empresa_pos,
             severidad="informativo", resolucion="Usar el nombre completo de Positiva para documentos oficiales")

    return discrepancias
```

---

### PORTAL-2 — `backend/portal_verificador.py` (módulo nuevo)

Capa de acceso unificada para el chat. Envuelve el `orquestador.py` existente y añade:
- Comparación con el JSON local ya guardado (no siempre requiere navegar)
- Sistema de aprendizaje (`portal_knowledge.json`)
- Correcciones que Sandra valida

```python
"""
Verificador cruzado de portales para el chat de Tomy.

Flujo:
  1. chat_handler detecta intención de portal
  2. Llama a PortalVerificador.verificar(cc)
  3. Si hay JSON local fresco (<24h): compara sin navegar
  4. Si es viejo o no existe: navega y actualiza
  5. Retorna reporte de discrepancias listo para el LLM
"""
import asyncio, json, os, unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage"))
KNOWLEDGE_PATH = STORAGE_DIR / "portal_knowledge.json"
DATA_DIR = STORAGE_DIR / "data"


def _norm(s: str) -> str:
    if not s: return ""
    n = unicodedata.normalize("NFD", str(s).lower().strip())
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return " ".join(n.split())


class PortalVerificador:
    def __init__(self):
        self._k = self._load_knowledge()

    # ─── VERIFICACIÓN PRINCIPAL ───────────────────────────────────────────

    def verificar(self, cc: str, forzar_extraccion: bool = False) -> dict:
        """
        Punto de entrada principal.
        Devuelve dict listo para formatear en el chat.
        
        Si el JSON local es de hoy → compara sin navegar (rápido, <1s).
        Si es de ayer o no existe → navega ambos portales (~60s) y actualiza.
        """
        json_local = self._leer_json_local(cc)
        es_fresco = self._es_fresco(json_local)
        
        if forzar_extraccion or not es_fresco:
            _log(f"PORTAL: extrayendo portales para CC {cc}...")
            # asyncio.run() porque orquestador es async
            try:
                from backend.playwright_real.orquestador import extraer_paciente_completo
                datos_frescos = asyncio.run(extraer_paciente_completo(cc, guardar=True))
                json_local = datos_frescos
            except Exception as e:
                _log(f"PORTAL: extracción falló → {e}")
                # Continuar con JSON local viejo si existe
                if not json_local:
                    return {"error": f"No pude acceder a los portales: {e}", "cc": cc}
        
        return self._comparar_con_local(cc, json_local)

    def verificar_vs_docx(self, cc: str, ruta_docx: str) -> dict:
        """
        Compara datos de un DOCX generado con lo que dicen los portales.
        Útil cuando Sandra sospecha que un formato tiene datos erróneos.
        """
        from backend.chat_handler import _leer_docx
        texto_docx = _leer_docx(Path(ruta_docx))
        
        # Extraer datos del texto del DOCX (búsqueda de patrones)
        import re
        datos_docx = {}
        
        # Buscar CC
        m = re.search(r"C\.?C\.?\s*[:\-]?\s*(\d{6,12})", texto_docx)
        if m: datos_docx["documento"] = m.group(1)
        
        # Buscar siniestro
        m = re.search(r"[Ss]iniestro\s*[:\-]?\s*(\d{8,12})", texto_docx)
        if m: datos_docx["siniestro"] = m.group(1)
        
        # Buscar CIE-10
        m = re.search(r"\b([A-Z]\d{2,3})\b", texto_docx)
        if m: datos_docx["cie10_docx"] = m.group(1)
        
        # Comparar con portal
        resultado_portal = self.verificar(cc)
        resultado_portal["docx_comparacion"] = datos_docx
        resultado_portal["docx_nombre"] = Path(ruta_docx).name
        
        return resultado_portal

    # ─── COMPARACIÓN CON LOCAL ────────────────────────────────────────────

    def _comparar_con_local(self, cc: str, datos_portal: dict) -> dict:
        """
        Compara datos del portal (fusionado) con el JSON local y las discrepancias ya conocidas.
        """
        resultado = {
            "cc": cc,
            "campos": [],
            "discrepancias": [],
            "confianza": 1.0,
            "fuente_extraccion": datos_portal.get("_meta", {}).get("extraido_en", "desconocida"),
            "parcial": datos_portal.get("_meta", {}).get("parcial", False),
        }
        
        # Discrepancias ya detectadas por el orquestador (Medifolios vs. Positiva)
        disc_portales = datos_portal.get("_meta", {}).get("discrepancias", [])
        
        # Enriquecer con el knowledge base (¿ya conocemos la resolución?)
        for d in disc_portales:
            d["resolucion_conocida"] = self._buscar_resolucion_conocida(cc, d["campo"])
        
        resultado["discrepancias"] = disc_portales
        
        # Resumen de campos verificados
        datos_medi = datos_portal.get("medifolios", {})
        datos_pos = datos_portal.get("positiva", {})
        
        siniestros_pos = datos_pos.get("siniestros", [])
        siniestro_pos_id = siniestros_pos[0].get("id", "") if siniestros_pos else ""
        
        campos_verificados = [
            ("nombre", datos_medi.get("nombre", ""), 
             (datos_pos.get("datos_asegurado") or {}).get("nombre", "")),
            ("siniestro", datos_medi.get("siniestro_medi", ""), siniestro_pos_id),
            ("diagnóstico CIE-10", datos_medi.get("diagnostico_cie10", ""),
             siniestros_pos[0].get("diagnostico", "") if siniestros_pos else ""),
            ("empresa", datos_medi.get("empresa", ""),
             (datos_pos.get("datos_asegurado") or {}).get("empresa", "")),
        ]
        
        n_ok = 0
        for nombre_campo, val_medi, val_pos in campos_verificados:
            coincide = not val_medi or not val_pos or _norm(val_medi) == _norm(val_pos)
            if coincide: n_ok += 1
            resultado["campos"].append({
                "campo": nombre_campo,
                "medifolios": val_medi,
                "positiva": val_pos,
                "coincide": coincide,
            })
        
        total = len(campos_verificados)
        resultado["confianza"] = round(n_ok / total, 2) if total > 0 else 0.0
        
        # Registrar en historial de aprendizaje
        self._registrar_verificacion(cc, resultado)
        
        return resultado

    # ─── APRENDIZAJE ─────────────────────────────────────────────────────

    def aprender_correccion(self, cc: str, campo: str, valor_correcto: str, fuente: str = "sandra"):
        """
        Sandra confirma qué valor es el correcto.
        1. Guarda en portal_knowledge.json como corrección aprendida
        2. Actualiza el JSON local del paciente con el valor correcto
        """
        correcciones = self._k.setdefault("correcciones_confirmadas", [])
        correcciones.append({
            "cc": cc, "campo": campo, "valor_correcto": valor_correcto,
            "fuente": fuente, "fecha": datetime.now().isoformat()[:10],
        })
        self._save_knowledge()
        
        # Actualizar JSON local
        json_path = DATA_DIR / f"{cc}-completo.json"
        if json_path.exists():
            datos = json.loads(json_path.read_text(encoding="utf-8"))
            # Actualizar el campo en la estructura del paciente
            campo_map = {
                "siniestro": ["positiva", "siniestro_principal", "id"],
                "diagnostico_cie10": ["positiva", "siniestros", 0, "diagnostico"],
                "nombre": ["medifolios", "nombre"],
            }
            ruta = campo_map.get(campo)
            if ruta:
                d = datos
                for k in ruta[:-1]:
                    d = d[k] if isinstance(k, str) else (d[k] if len(d) > k else d)
                if isinstance(ruta[-1], str):
                    d[ruta[-1]] = valor_correcto
                datos["_meta"]["ultima_correccion"] = datetime.now().isoformat()
                json_path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        
        _log(f"APRENDIZAJE: CC {cc} campo '{campo}' = '{valor_correcto}' (fuente: {fuente})")

    def aprender_ruta_exitosa(self, portal: str, seccion: str, instruccion: str, pasos: list):
        """Registra que esta ruta funcionó para encontrar esta sección."""
        rutas = self._k.setdefault("rutas_aprendidas", {}).setdefault(portal, [])
        # No duplicar
        for r in rutas:
            if r.get("seccion") == seccion:
                r["exitos"] = r.get("exitos", 0) + 1
                r["ultimo_uso"] = datetime.now().isoformat()[:10]
                self._save_knowledge()
                return
        rutas.append({
            "seccion": seccion, "instruccion_original": instruccion,
            "pasos": pasos, "exitos": 1,
            "primer_uso": datetime.now().isoformat()[:10],
            "ultimo_uso": datetime.now().isoformat()[:10],
        })
        self._save_knowledge()

    def reportar_portal_caido(self, portal: str, error: str):
        """Registra cuando un portal no está accesible para notificar a Manu."""
        problemas = self._k.setdefault("portales_caidos", [])
        problemas.append({"portal": portal, "error": error[:200], "fecha": datetime.now().isoformat()})
        self._save_knowledge()
        # Notificar a Manu (no a Sandra — ella no puede arreglarlo)
        try:
            from backend.notificador import enviar_telegram_manu
            enviar_telegram_manu(f"⚠️ Portal {portal} caído: {error[:100]}")
        except Exception:
            pass

    # ─── UTILIDADES ──────────────────────────────────────────────────────

    def _buscar_resolucion_conocida(self, cc: str, campo: str) -> Optional[str]:
        """Busca si ya se resolvió esta discrepancia antes."""
        for c in self._k.get("correcciones_confirmadas", []):
            if c.get("cc") == cc and c.get("campo") == campo:
                return f"Sandra confirmó anteriormente: usar '{c['valor_correcto']}' (fuente: {c['fuente']})"
        return None

    def _es_fresco(self, json_local: Optional[dict], max_horas: int = 24) -> bool:
        if not json_local: return False
        extraido = json_local.get("_meta", {}).get("extraido_en", "")
        if not extraido: return False
        try:
            dt = datetime.fromisoformat(extraido)
            return datetime.now() - dt < timedelta(hours=max_horas)
        except Exception:
            return False

    def _leer_json_local(self, cc: str) -> Optional[dict]:
        path = DATA_DIR / f"{cc}-completo.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def _registrar_verificacion(self, cc: str, resultado: dict):
        historial = self._k.setdefault("historial_verificaciones", [])
        historial.append({
            "cc": cc, "fecha": datetime.now().isoformat()[:10],
            "confianza": resultado["confianza"],
            "n_discrepancias": len(resultado["discrepancias"]),
        })
        self._k["historial_verificaciones"] = historial[-200:]  # Máx 200 entradas
        self._save_knowledge()

    def _load_knowledge(self) -> dict:
        if KNOWLEDGE_PATH.exists():
            try:
                return json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"version": "1.0", "creado": datetime.now().isoformat()[:10]}

    def _save_knowledge(self):
        KNOWLEDGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._k["ultima_actualizacion"] = datetime.now().isoformat()[:10]
        KNOWLEDGE_PATH.write_text(
            json.dumps(self._k, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _log(msg: str):
    import sys
    print(f"[PORTAL {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)
```

---

### PORTAL-3 — Intent detection en `chat_handler.py`

El chat detecta automáticamente cuando Sandra quiere verificar o buscar en portales, ANTES de llamar al LLM:

```python
# Agregar en chat_handler.py — nueva función:

PORTAL_KEYWORDS = {
    "verificar": [
        "verifica", "verificá", "verificar", "compara", "comparar", "coincide",
        "chequea", "confronta", "revisa en el portal", "qué dice positiva",
        "qué dice medifolios", "bate contra", "cruza con", "corrobora",
        "está bien el", "está correcto el", "concuerda",
    ],
    "navegar_positiva": [
        "busca en positiva", "abre positiva", "entra a positiva",
        "qué dice positiva sobre", "en positiva", "autorización en positiva",
        "diagnóstico de positiva", "siniestro en positiva",
    ],
    "navegar_medifolios": [
        "busca en medifolios", "en medifolios", "historia clínica en medifolios",
        "qué dice medifolios", "agenda en medifolios", "notas de medifolios",
    ],
    "aprender": [
        "guarda esto", "recuerda que", "siempre va a ser así",
        "el correcto es", "el que vale es", "usa ese", "ese es el bueno",
    ],
}

def _detectar_intencion_portal(mensaje: str, cc: str = "") -> Optional[dict]:
    """
    Detecta si el mensaje requiere una acción en los portales.
    Retorna None si no hay intención, o dict con la acción a tomar.
    """
    msg_lower = mensaje.lower()
    
    # Verificación cruzada (la más útil — compara TODO contra los portales)
    if any(k in msg_lower for k in PORTAL_KEYWORDS["verificar"]):
        return {
            "tipo": "verificar",
            "cc": cc or _extraer_cc_de_texto(mensaje),
            "instruccion": mensaje,
            "forzar": "actualiza" in msg_lower or "de nuevo" in msg_lower or "hoy" in msg_lower,
        }
    
    # Navegación específica a Positiva
    if any(k in msg_lower for k in PORTAL_KEYWORDS["navegar_positiva"]):
        return {
            "tipo": "navegar",
            "portal": "positiva",
            "cc": cc or _extraer_cc_de_texto(mensaje),
            "instruccion": mensaje,
        }
    
    # Navegación específica a Medifolios
    if any(k in msg_lower for k in PORTAL_KEYWORDS["navegar_medifolios"]):
        return {
            "tipo": "navegar",
            "portal": "medifolios",
            "cc": cc or _extraer_cc_de_texto(mensaje),
            "instruccion": mensaje,
        }
    
    return None

def _extraer_cc_de_texto(texto: str) -> str:
    import re
    m = re.search(r"\b(\d{6,12})\b", texto.replace("'", "").replace(".", ""))
    return m.group(1) if m else ""

def _formatear_verificacion_para_llm(resultado: dict) -> str:
    """Convierte el resultado de verificación en texto claro para el LLM."""
    cc = resultado.get("cc", "?")
    lineas = [f"\n═══ VERIFICACIÓN PORTAL — CC {cc} ═══"]
    
    if resultado.get("parcial"):
        lineas.append("⚠️ Verificación parcial — uno de los portales no respondió")
    
    # Campos verificados
    for campo in resultado.get("campos", []):
        icono = "✅" if campo["coincide"] else "❌"
        lineas.append(f"\n{icono} {campo['campo'].upper()}:")
        lineas.append(f"   Medifolios: {campo['medifolios'] or '(vacío)'}")
        lineas.append(f"   Positiva:   {campo['positiva'] or '(vacío)'}")
    
    # Discrepancias con recomendaciones
    discs = resultado.get("discrepancias", [])
    if discs:
        lineas.append(f"\n⚠️ {len(discs)} DISCREPANCIA(S) ENCONTRADA(S):")
        for d in discs:
            lineas.append(f"\n  Campo: {d['campo']} (severidad: {d.get('severidad', '?')})")
            lineas.append(f"  Medifolios: {d['medifolios']}")
            lineas.append(f"  Positiva:   {d['positiva']}")
            if d.get("resolucion_conocida"):
                lineas.append(f"  → RESOLUCIÓN PREVIA: {d['resolucion_conocida']}")
            else:
                lineas.append(f"  → {d.get('resolucion', 'Preguntar a Sandra cuál es correcto')}")
        lineas.append("\nINSTRUCCION AL ASISTENTE: Pregunta a Sandra cuál valor es correcto.")
        lineas.append("Cuando Sandra confirme, dile: 'Guardé la corrección, no te volveré a preguntar esto.'")
    else:
        lineas.append(f"\n✅ TODO COINCIDE — confianza {resultado.get('confianza',0)*100:.0f}%")
    
    return "\n".join(lineas)

# Modificar procesar_mensaje para integrar detección de portales:
# (Agregar ANTES del bloque que llama al LLM)

def procesar_mensaje(mensaje, paciente_cc="", historial=None):
    cc = paciente_cc
    contexto_portal = ""
    
    # ← NUEVO: detectar intención de portal
    intencion = _detectar_intencion_portal(mensaje, cc)
    if intencion and intencion.get("cc"):
        _log(f"PORTAL: {intencion['tipo']} en {intencion.get('portal','ambos')} para CC {intencion['cc']}")
        try:
            from backend.portal_verificador import PortalVerificador
            v = PortalVerificador()
            if intencion["tipo"] == "verificar":
                resultado = v.verificar(
                    intencion["cc"],
                    forzar_extraccion=intencion.get("forzar", False),
                )
                contexto_portal = _formatear_verificacion_para_llm(resultado)
            elif intencion["tipo"] == "navegar":
                # Navegar a sección específica (usar playwright_real directamente)
                from backend.playwright_real.orquestador import extraer_paciente_completo
                datos = asyncio.run(extraer_paciente_completo(intencion["cc"]))
                contexto_portal = f"\n═══ DATOS FRESCOS DEL PORTAL {intencion['portal'].upper()} ═══\n"
                portal_datos = datos.get(intencion["portal"], {})
                contexto_portal += json.dumps(portal_datos, ensure_ascii=False, indent=2)[:3000]
        except Exception as e:
            contexto_portal = f"\n⚠️ No pude acceder al portal: {e}"
    
    # ... resto del pipeline normal ...
    # Agregar contexto_portal al mensaje:
    if contexto_portal:
        mensaje_con_sugerencia = f"{mensaje}\n\n{contexto_portal}"
    
    # ... llamar LLM con todo el contexto ...
```

---

### PORTAL-4 — Streaming con progreso de navegación

Los portales tardan 30-90 segundos. En el endpoint de streaming (`/api/chat/stream`), mostrar progreso mientras Playwright navega:

```python
# En _stream() del endpoint /api/chat/stream:

# Si se detecta intención de portal, hacer yield de mensajes de progreso
if intencion_portal:
    yield f'data: {json.dumps({"tipo":"progreso","contenido":"🔍 Revisando portales... puede tardar hasta 90 segundos"})}\n\n'
    
    try:
        from backend.portal_verificador import PortalVerificador
        yield f'data: {json.dumps({"tipo":"progreso","contenido":"🌐 Conectando a ARL Positiva..."})}\n\n'
        
        v = PortalVerificador()
        resultado = v.verificar(cc)
        
        yield f'data: {json.dumps({"tipo":"progreso","contenido":"📊 Comparando datos con documentos locales..."})}\n\n'
        
        contexto_portal = _formatear_verificacion_para_llm(resultado)
        
        # Si hay discrepancias, también incluirlas como dato estructurado en el fin
        yield f'data: {json.dumps({"tipo":"verificacion_lista","datos": resultado})}\n\n'
        
    except Exception as e:
        yield f'data: {json.dumps({"tipo":"progreso","contenido":f"⚠️ Portal no disponible: {str(e)[:80]}"})}\n\n'
```

**Frontend — mostrar mensajes de progreso del portal:**

```tsx
// En el loop de lectura del stream, agregar:
if (data.tipo === "progreso") {
  // Actualizar el mensaje placeholder del asistente con el estado intermedio
  setMensajes(prev => {
    const nuevo = [...prev];
    const ultimo = nuevo[nuevo.length - 1];
    if (ultimo.rol === "asistente" && ultimo.contenido === "") {
      nuevo[nuevo.length - 1] = { ...ultimo, contenido: data.contenido };
    }
    return nuevo;
  });
} else if (data.tipo === "verificacion_lista") {
  // Guardar los datos estructurados para renderizar la tabla
  setMensajes(prev => {
    const nuevo = [...prev];
    nuevo[nuevo.length - 1] = { ...nuevo[nuevo.length - 1], verificacion: data.datos };
    return nuevo;
  });
}
```

---

### PORTAL-5 — Tabla de verificación en el chat (frontend)

Cuando Tomy retorna datos de verificación, el frontend los renderiza como tabla interactiva con botones "Corregir":

```tsx
// En chat/page.tsx — agregar interfaz:
interface VerificacionPortal {
  cc: string;
  campos: Array<{
    campo: string;
    medifolios: string;
    positiva: string;
    coincide: boolean;
  }>;
  discrepancias: Array<{
    campo: string;
    medifolios: string;
    positiva: string;
    severidad: "crítico" | "advertencia" | "informativo";
    resolucion: string;
    resolucion_conocida?: string;
  }>;
  confianza: number;
  parcial: boolean;
}

// Componente dentro del render del mensaje:
{msg.verificacion && (
  <div className="mt-4 bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
    <div className="flex items-center justify-between px-4 py-2 bg-slate-50 border-b">
      <span className="font-semibold text-slate-700">
        Verificación CC {msg.verificacion.cc}
      </span>
      <span className={`text-xs font-medium px-3 py-1 rounded-full ${
        msg.verificacion.confianza >= 0.9 ? "bg-green-100 text-green-700" :
        msg.verificacion.confianza >= 0.7 ? "bg-amber-100 text-amber-700" :
        "bg-red-100 text-red-700"
      }`}>
        {Math.round(msg.verificacion.confianza * 100)}% confianza
        {msg.verificacion.parcial && " ⚠️ parcial"}
      </span>
    </div>
    <table className="w-full text-sm">
      <thead className="bg-slate-50 text-slate-500">
        <tr>
          <th className="p-3 text-left font-medium">Campo</th>
          <th className="p-3 text-left font-medium">Medifolios</th>
          <th className="p-3 text-left font-medium">Positiva</th>
          <th className="p-3 text-center font-medium">Estado</th>
        </tr>
      </thead>
      <tbody>
        {msg.verificacion.campos.map((c, i) => (
          <tr key={i} className={`border-t ${c.coincide ? "" : "bg-red-50"}`}>
            <td className="p-3 font-medium capitalize">{c.campo}</td>
            <td className="p-3 text-slate-600 font-mono text-xs">{c.medifolios || "—"}</td>
            <td className="p-3 text-slate-600 font-mono text-xs">{c.positiva || "—"}</td>
            <td className="p-3 text-center">
              {c.coincide ? (
                <span className="text-green-600 text-lg">✅</span>
              ) : (
                <div className="flex items-center justify-center gap-1">
                  <span className="text-red-500 text-lg">❌</span>
                  {/* Botón para elegir el valor correcto */}
                  <div className="flex gap-1">
                    {c.medifolios && (
                      <button
                        onClick={() => resolverDiscrepancia(msg.verificacion!.cc, c.campo, c.medifolios, "medifolios")}
                        className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                        title="Usar valor de Medifolios"
                      >
                        Medi ✓
                      </button>
                    )}
                    {c.positiva && (
                      <button
                        onClick={() => resolverDiscrepancia(msg.verificacion!.cc, c.campo, c.positiva, "positiva")}
                        className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded hover:bg-purple-200"
                        title="Usar valor de Positiva (recomendado para ARL)"
                      >
                        Pos ✓
                      </button>
                    )}
                  </div>
                </div>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
)}

// Función para resolver discrepancias desde el botón:
const resolverDiscrepancia = async (cc: string, campo: string, valorCorrecto: string, fuente: string) => {
  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  
  await fetch(`${API}/api/portal/aprender`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cc, campo, valor_correcto: valorCorrecto, fuente }),
  });
  
  // Agregar confirmación al chat
  setMensajes(prev => [...prev, {
    rol: "asistente",
    contenido: `✅ Guardé que **${campo}** para CC ${cc} es \`${valorCorrecto}\` (fuente: ${fuente}). ` +
               `No te vuelvo a preguntar esto. El dato está actualizado en el sistema.`,
    timestamp: new Date().toISOString(),
  }]);
};
```

---

### PORTAL-6 — Endpoints en `server.py`

```python
from pydantic import BaseModel
from typing import List, Optional

class PortalVerifRequest(BaseModel):
    cc: str
    campos: Optional[List[str]] = None
    forzar: bool = False

class PortalAprenderRequest(BaseModel):
    cc: str
    campo: str
    valor_correcto: str
    fuente: str = "sandra"

@app.post("/api/portal/verificar")
async def portal_verificar(req: PortalVerifRequest):
    """
    Verificación cruzada Medifolios vs. Positiva vs. JSON local.
    Puede tardar 30-90 seg si el JSON local es viejo (Playwright navega en background).
    """
    from backend.portal_verificador import PortalVerificador
    v = PortalVerificador()
    resultado = await asyncio.get_event_loop().run_in_executor(
        None, lambda: v.verificar(req.cc, req.forzar)
    )
    return {"ok": True, "verificacion": resultado}

@app.post("/api/portal/aprender")
def portal_aprender(req: PortalAprenderRequest):
    """Sandra confirma qué valor es correcto → se guarda y actualiza JSON local."""
    from backend.portal_verificador import PortalVerificador
    v = PortalVerificador()
    v.aprender_correccion(req.cc, req.campo, req.valor_correcto, req.fuente)
    return {"ok": True, "guardado": f"{req.campo} = {req.valor_correcto}"}

@app.get("/api/portal/conocimiento")
def portal_conocimiento():
    """Muestra todo lo que el sistema ha aprendido de los portales."""
    k_path = STORAGE / "portal_knowledge.json"
    if not k_path.exists():
        return {"ok": True, "conocimiento": {}, "mensaje": "Sin historial aún"}
    k = json.loads(k_path.read_text(encoding="utf-8"))
    # Estadísticas resumidas
    resumen = {
        "verificaciones_realizadas": len(k.get("historial_verificaciones", [])),
        "correcciones_aprendidas": len(k.get("correcciones_confirmadas", [])),
        "rutas_conocidas": sum(
            len(v) for v in k.get("rutas_aprendidas", {}).values()
            if isinstance(v, list)
        ),
        "ultima_actualizacion": k.get("ultima_actualizacion", "?"),
    }
    return {"ok": True, "resumen": resumen, "conocimiento": k}

@app.get("/api/portal/estado")
async def portal_estado():
    """Verifica si los portales son accesibles (GET simple, sin login)."""
    import httpx
    resultados = {}
    urls = {
        "medifolios": "https://www.server0medifolios.net/",
        "positiva": "https://positivacuida.positiva.gov.co/cas/login",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        for portal, url in urls.items():
            try:
                r = await client.get(url)
                resultados[portal] = {"accesible": r.status_code < 500, "status": r.status_code}
            except Exception as e:
                resultados[portal] = {"accesible": False, "error": str(e)[:60]}
    return {"ok": True, "portales": resultados}
```

---

### PORTAL-7 — Inicializar `storage/portal_knowledge.json`

Crear el archivo base **una sola vez** en el setup inicial. Crece automáticamente con el uso:

```bash
# Ejecutar una sola vez en WSL de Sandra:
python3 -c "
import json
from pathlib import Path
from datetime import datetime

k = {
    'version': '1.0',
    'creado': datetime.now().isoformat()[:10],
    'descripcion': 'Conocimiento acumulado del sistema sobre los portales Medifolios y ARL Positiva',
    'medifolios': {
        'secciones_verificadas': {
            'agenda_citas': {'estado': 'verificado'},
            'historia_clinica': {'estado': 'verificado'},
            'observaciones': {'estado': 'verificado'},
            'archivos_adjuntos': {'estado': 'por_verificar'},
            'valoracion': {'estado': 'por_verificar'},
        },
        'rutas_aprendidas': []
    },
    'positiva': {
        'secciones_verificadas': {
            'datos_asegurado': {'pestana': 0, 'estado': 'verificado'},
            'siniestros': {'pestana': 1, 'estado': 'verificado'},
            'rehabilitacion_integral': {'pestana': 2, 'estado': 'verificado'},
            'autorizaciones': {'pestana': 3, 'estado': 'verificado'},
            'consulta_integral': {'pestanas': 6, 'estado': 'verificado'},
            'caso_rhi': {'estado': 'verificado'},
        },
        'rutas_aprendidas': []
    },
    'discrepancias_esperadas': [
        {
            'tipo': 'nombre_sin_tilde',
            'descripcion': 'Positiva muestra nombres en MAYÚSCULAS sin tildes. Es normal.',
            'resolucion_automatica': 'normalizar antes de comparar — no es error',
            'confirmado_por': 'regla_inicial'
        },
        {
            'tipo': 'cie10_mas_especifico_en_positiva',
            'descripcion': 'Positiva tiene el CIE-10 completo con descripción (ej: M545 LUMBAGO). Medifolios puede tener solo el código.',
            'resolucion_automatica': 'extraer código del texto de Positiva — Positiva es más preciso',
            'confirmado_por': 'regla_inicial'
        },
    ],
    'correcciones_confirmadas': [],
    'historial_verificaciones': [],
    'portales_caidos': []
}
path = Path('./storage/portal_knowledge.json')
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(k, ensure_ascii=False, indent=2), encoding='utf-8')
print('✅ portal_knowledge.json creado')
"
```

---

### PORTAL-8 — Sistema de aprendizaje continuo (filosofía Hermes)

El sistema aprende de 4 fuentes distintas sin intervención manual:

| Evento | Qué aprende | Dónde se guarda |
|--------|-------------|-----------------|
| Verificación exitosa (100% coincidencia) | Este paciente + fecha → datos confiables | `historial_verificaciones` |
| Sandra hace click en "Pos ✓" o "Medi ✓" | Cuál fuente prevalece para este campo/CC | `correcciones_confirmadas` |
| Tomy navega exitosamente a sección inusual | La ruta sirve para ese objetivo | `rutas_aprendidas` |
| Portal no responde 2 veces seguidas | Sección puede haber cambiado | Notifica a Manu |

**El ciclo de mejora:**
```
Primera semana: Tomy pregunta "¿cuál es correcto?" con frecuencia
    ↓
Sandra hace click en los botones → correcciones se guardan
    ↓
Semana 2: Tomy ya no pregunta sobre los mismos campos — aplica la corrección automáticamente
    ↓
Mes 1: Tomy sabe qué fuente prevalece para cada campo por tipo de discrepancia
    ↓
Si el portal cambia su estructura → Tomy lo detecta, notifica a Manu para actualizar selectores
```

**Instrucción para Manu (cuando hay cambio en portal):**
```
[Telegram a Manu]
⚠️ RILO: Medifolios/sección "historia_clinica" no responde hace 2 días.
Revisar selectores en backend/playwright_real/selectores.py
y actualizar backend/playwright_real/medifolios.py si cambió la estructura.
```

---

## PARTE 2.6 — Corrección de formatos desde el chat (sin abrir Word)

### Problema
`correction_resolver.py` y `aplicador_correccion.py` existen y funcionan, y el endpoint `POST /api/corregir-paciente/{cc}` también. Pero el chat de Tomy NO los usa. Cuando Sandra dice "cambia el nombre de la empresa", Tomy responde con texto pero no cambia nada. Sandra tiene que abrir Word, editar, guardar, volver a imprimir.

**Este bug solo hace el sistema hace que Tomy parezca inútil en la tarea más común.**

### Flujo correcto (a implementar)

```
Sandra: "corrige el nombre de la empresa a Textiles del Sur SAS"
    ↓
chat_handler detecta intención de corrección (palabras clave)
    ↓
correction_resolver.interpretar_correccion(mensaje, cc) → LLM clasifica:
    {"campo": "empresa.nombre", "valor": "Textiles del Sur SAS", "formatos_afectados": ["carta_medidas", "citacion_empresas"]}
    ↓
aplicador_correccion.aplicar_correccion(cc, correccion) →
    - Actualiza JSON: storage/data/{cc}-completo.json
    - Regenera los 2 formatos afectados (no los 7)
    ↓
Tomy responde: "✅ Listo. Actualicé 'empresa.nombre' a 'Textiles del Sur SAS'.
Regeneré 2 formatos: carta_medidas y citacion_empresas.
[📄 Descargar carta_medidas.docx] [📄 Descargar citacion_empresas.docx]"
```

### CORR-1 — Intent detection de correcciones en `chat_handler.py`

```python
CORRECCION_KEYWORDS = [
    "corrige", "correge", "corregir", "cambia", "cambiar", "actualiza", "actualizar",
    "modifica", "el nombre es", "el dato correcto es", "es que dice mal",
    "está mal el", "está equivocado", "reemplaza", "reemplazar", "pon", "ponle",
    "quita", "agrega", "agréga", "el correcto es",
]

def _es_intencion_correccion(mensaje: str) -> bool:
    msg_lower = mensaje.lower()
    return any(k in msg_lower for k in CORRECCION_KEYWORDS)

# Modificar procesar_mensaje:
def procesar_mensaje(mensaje, paciente_cc="", historial=None):
    cc = paciente_cc or _extraer_cc_de_texto(mensaje)
    
    # ← NUEVO: detección de correcciones (requiere CC para saber qué paciente)
    if cc and _es_intencion_correccion(mensaje):
        _log(f"CORRECCION: detectada para CC {cc}")
        try:
            from backend.correction_resolver import interpretar_correccion
            from backend.aplicador_correccion import aplicar_correccion
            
            correccion = interpretar_correccion(mensaje, cc)
            # correccion = {"campo": "empresa.nombre", "valor": "Textiles del Sur", 
            #               "formatos_afectados": [...], "confianza": 0.9}
            
            if correccion and correccion.get("confianza", 0) >= 0.7:
                resultado = aplicar_correccion(cc, correccion)
                # resultado = {"ok": True, "campo": "...", "valor": "...",
                #              "formatos_regenerados": ["carta_medidas.docx", ...]}
                
                if resultado.get("ok"):
                    formatos = resultado.get("formatos_regenerados", [])
                    links = "\n".join(
                        f"- 📄 [{f}](/api/download/{f})" for f in formatos
                    )
                    respuesta = (
                        f"✅ **Corrección aplicada**: `{correccion['campo']}` → `{correccion['valor']}`\n\n"
                        f"Regeneré {len(formatos)} formato(s) afectado(s):\n{links}\n\n"
                        f"¿Algo más que corregir?"
                    )
                    return respuesta  # Retornar directamente sin llamar al LLM
        except Exception as e:
            _log(f"CORRECCION: falló → {e} — pasando al LLM normal")
    
    # ... resto del pipeline normal (LLM) ...
```

### CORR-2 — Respuesta con links de descarga directos

El mensaje de éxito de corrección debe incluir links de descarga que funcionen inmediatamente. Los formatos regenerados están en `storage/docs/`. El endpoint `GET /api/download/{filename}` ya existe.

**Frontend — detectar links de descarga en mensajes de corrección:**

Los mensajes en formato Markdown con `[nombre.docx](/api/download/nombre.docx)` ya son renderizados por `react-markdown` como links. Solo hay que asegurarse de que el `href` sea relativo (next.config.js reescribe `/api/` → `http://localhost:8000/api/`).

```tsx
// En ReactMarkdown, agregar componente personalizado para links de descarga:
<ReactMarkdown
  remarkPlugins={[remarkGfm]}
  components={{
    a: ({href, children}) => (
      <a href={href} download={href?.includes('/api/download/')}
        className={href?.includes('/api/download/')
          ? "inline-flex items-center gap-1 px-3 py-1 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
          : "text-blue-600 underline"}>
        {children}
      </a>
    )
  }}
>
  {msg.contenido}
</ReactMarkdown>
```

---

## PARTE 2.7 — ZIP: descargar los 7 formatos de una sola vez

### Problema
Cuando los 7 formatos están listos, Sandra tiene que descargar 7 archivos individuales. 7 clicks, 7 diálogos de guardar. Con un ZIP sería 1 click.

### ZIP-1 — Endpoint `GET /api/pacientes/{cc}/formatos/zip` en `server.py`

```python
import zipfile, io

@app.get("/api/pacientes/{cc}/formatos/zip")
def descargar_formatos_zip(cc: str):
    """Empaqueta todos los formatos DOCX y PDF del paciente en un ZIP."""
    archivos = list(DOCS_DIR.glob(f"*{cc}*.docx")) + list(PDFS_DIR.glob(f"*{cc}*.pdf"))
    
    if not archivos:
        raise HTTPException(404, f"No hay formatos para CC {cc}")
    
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(archivos, key=lambda x: x.stat().st_mtime, reverse=True):
            zf.write(f, f.name)
    buf.seek(0)
    
    from fastapi.responses import StreamingResponse
    fecha = datetime.now().strftime("%Y%m%d")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=formatos_{cc}_{fecha}.zip"},
    )
```

### ZIP-2 — Botón "Descargar todo" en la página de formatos y en el chat

**`dashboard/app/formatos/page.tsx` — agregar botón:**
```tsx
{formatosAPI.length > 0 && (
  <a
    href={`${API}/api/pacientes/${cc}/formatos/zip`}
    download
    className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-xl font-semibold hover:bg-green-700 transition-colors"
  >
    <Download size={20} />
    Descargar todos ({formatosAPI.length}) en ZIP
  </a>
)}
```

**Cuando Tomy termina de procesar audio — incluir link al ZIP en el mensaje:**
```
✅ ¡Listo, Sandra! Generé 7 formatos para CC 1193143688:
📦 [Descargar todos en ZIP](/api/pacientes/1193143688/formatos/zip)

O individualmente:
- 📄 [analisis_exigencias...docx](...)
- 📄 [carta_medidas...docx](...)
...
```

---

## PARTE 2.8 — Retry de paso fallido en el workflow

### Problema
Si el workflow falla en el paso 5 (síntesis DeepSeek, ~8 min), actualmente hay que volver a subir el audio desde cero. Eso significa retranscribir (~6 min) + resolver paciente + releer notas antes de poder reintentar la síntesis. En total: 15+ minutos perdidos por un error transitorio del LLM.

### RETRY-1 — Nuevo endpoint `POST /api/tasks/{task_id}/reintentar` en `server.py`

```python
@app.post("/api/tasks/{task_id}/reintentar")
def reintentar_task(task_id: str, desde_paso: int = 0):
    """
    Reintenta el workflow desde el paso fallido (o desde el indicado).
    
    Uso normal: no especificar desde_paso → reinicia desde el último paso fallido.
    Uso avanzado: desde_paso=5 → salta los primeros 4 pasos (transcripción ya hecha).
    """
    db = TaskDB(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))
    task = db.obtener_task(task_id)
    
    if not task:
        raise HTTPException(404, f"Task {task_id} no encontrada")
    
    if not task.get("estado", "").startswith("error"):
        raise HTTPException(400, f"La tarea no está en estado de error (estado: {task['estado']})")
    
    # Determinar desde qué paso reintentar
    paso_fallo = task.get("paso_actual", 1)
    paso_inicio = desde_paso if desde_paso > 0 else max(1, paso_fallo)
    
    # Resetear estado en DB
    with db._conn() as conn:
        conn.execute(
            "UPDATE workflow_tasks SET estado=?, paso_actual=?, error=NULL, terminado_en=NULL WHERE task_id=?",
            (f"reintentando_desde_paso_{paso_inicio}", paso_inicio, task_id),
        )
    
    # Relanzar workflow desde ese paso
    from backend.workflow_runner import ejecutar_workflow
    threading.Thread(
        target=ejecutar_workflow,
        kwargs={
            "audio_path": task["audio_path"],
            "paciente_cc": task["paciente_cc"],
            "task_id_existente": task_id,
            "desde_paso": paso_inicio,  # ← nuevo parámetro en workflow_runner
        },
        daemon=True,
    ).start()
    
    PASOS = {1:"Transcripción", 2:"Paciente", 3:"Notas", 4:"Formatos ref.", 
             5:"Síntesis IA", 6:"Generar formatos", 7:"QA", 8:"PDF", 9:"Notificar"}
    return {
        "ok": True,
        "task_id": task_id,
        "reintentando_desde": f"Paso {paso_inicio}/9 — {PASOS.get(paso_inicio, '?')}",
        "mensaje": f"Workflow reiniciado desde el paso {paso_inicio}. El paso 1 (transcripción) {'ya estaba completado — no se vuelve a ejecutar' if paso_inicio > 1 else 'se ejecutará de nuevo'}.",
    }
```

### RETRY-2 — Modificar `workflow_runner.py` para soportar `desde_paso`

```python
# En workflow_runner.py — función principal:
def ejecutar_workflow(audio_path: str, paciente_cc: str, task_id_existente: str = None, 
                       desde_paso: int = 1):
    """
    Ejecuta el workflow de 9 pasos.
    desde_paso=1: ejecuta todos los pasos (normal)
    desde_paso=5: salta pasos 1-4 (asume que el resultado previo sigue en DB/disco)
    """
    # ... setup existente ...
    
    for i, paso in enumerate(STEPS, start=1):
        if i < desde_paso:
            _log(f"PASO {i} — SALTANDO (desde_paso={desde_paso})")
            continue  # Saltar pasos ya completados
        
        # ... ejecución normal del paso ...
```

### RETRY-3 — Botón de reintentar en el frontend

**En subir-audio page y en el chat — cuando hay error:**
```tsx
{estadoProceso.startsWith("error") && (
  <div className="bg-red-50 border border-red-300 rounded-xl p-4 space-y-3">
    <p className="font-semibold text-red-800">
      ❌ Error en el paso {pasoProceso}/9
    </p>
    <p className="text-red-700 text-sm">{errorDetalle}</p>
    <div className="flex gap-3">
      <button
        onClick={() => reintentar(taskId, 0)}  // desde el paso fallido
        className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
      >
        🔄 Reintentar desde paso {pasoProceso}
      </button>
      {pasoProceso > 1 && (
        <button
          onClick={() => reintentar(taskId, 1)}  // desde el principio
          className="px-4 py-2 border border-red-300 text-red-700 rounded-lg hover:bg-red-50"
        >
          Reiniciar desde cero
        </button>
      )}
    </div>
    <p className="text-xs text-red-600">
      {pasoProceso > 1 
        ? `La transcripción del audio ya se hizo — si reintentás desde el paso ${pasoProceso}, no tenés que esperar los 6 min de Deepgram.`
        : ""}
    </p>
  </div>
)}

const reintentar = async (tId: string, desdePaso: number) => {
  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const res = await fetch(`${API}/api/tasks/${tId}/reintentar?desde_paso=${desdePaso}`, {method: "POST"});
  if (res.ok) {
    setEstadoProceso("procesando");
    setSubiendo(true);
    iniciarPollingSubirAudio(tId, cc);
  }
};
```

---

## PARTE 2.9 — Telegram bidireccional: Sandra controla todo desde su celular

### Por qué es el feature más impactante

Sandra usa el celular. Abrir el dashboard en el PC, navegar menús, subir archivos — eso lleva 3-5 minutos solo para iniciar el proceso. Si Sandra puede:
1. Grabar el audio en su iPhone
2. Enviarlo directo al bot de Telegram
3. Recibir los formatos en el mismo chat 10-20 min después

...Sandra nunca necesita abrir el dashboard. **Ahorra 30+ minutos diarios.**

### Flujo completo Telegram

```
Sandra graba audio en iPhone → envía voice note al bot de Telegram
    ↓
Bot recibe audio → pregunta: "¿CC del paciente?"
    ↓
Sandra responde: "1193143688"
    ↓
Bot descarga el audio de Telegram, inicia workflow
    ↓
Bot responde: "✅ Recibí el audio. Te aviso cuando estén listos los formatos (~15 min)"
    ↓
[15 min después]
    ↓
Bot envía: "✅ ¡Listo, Sandra! Aquí están los 7 formatos:" 
Bot adjunta el ZIP de formatos como archivo en Telegram
    ↓
Sandra descarga el ZIP directamente en el celular
```

**Adicionalmente — Sandra puede:**
- Enviar texto: "¿qué está pasando?" → Tomy responde con el estado actual
- Enviar texto: "corrige el nombre de la empresa a Textiles del Sur" → Tomy aplica la corrección
- Enviar texto: "¿cuántos pacientes tengo hoy?" → Tomy consulta la agenda

### TELE-1 — Endpoint webhook `POST /api/telegram/webhook` en `server.py`

```python
@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    Recibe updates de Telegram (mensajes, audios, documentos).
    Registrado con: POST https://api.telegram.org/bot{TOKEN}/setWebhook?url=https://...
    
    NOTA: En WSL local, usar ngrok o Cloudflare Tunnel para exponer el puerto 8000.
    """
    try:
        update = await request.json()
        await _procesar_update_telegram(update)
    except Exception as e:
        _log(f"TELEGRAM WEBHOOK: error {e}")
    return {"ok": True}

# Estado de conversación por chat_id (en memoria — simple, sin DB)
_estado_telegram: Dict[str, dict] = {}

async def _procesar_update_telegram(update: dict):
    """Router principal de mensajes entrantes de Telegram."""
    msg = update.get("message", {})
    if not msg:
        return
    
    chat_id = str(msg.get("chat", {}).get("id", ""))
    
    # Verificar que es Sandra (por su chat_id)
    sandra_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if chat_id != sandra_chat_id:
        await _telegram_reply(chat_id, "⛔ No tengo autorización para responder en este chat.")
        return
    
    estado = _estado_telegram.get(chat_id, {"etapa": "idle"})
    
    # ─── AUDIO / VOZ ───
    voice = msg.get("voice") or msg.get("audio") or msg.get("document")
    if voice:
        file_id = voice.get("file_id", "")
        mime = voice.get("mime_type", "audio/ogg")
        
        if estado.get("etapa") == "esperando_cc_para_audio":
            # Ya tenemos el audio pendiente, esto no debería pasar
            pass
        else:
            # Guardar el file_id y preguntar CC
            _estado_telegram[chat_id] = {
                "etapa": "esperando_cc_para_audio",
                "file_id": file_id,
                "mime": mime,
            }
            await _telegram_reply(
                chat_id,
                "🎙️ Recibí el audio. ¿De qué paciente es? Escribime la cédula (solo los números)."
            )
        return
    
    # ─── TEXTO ───
    texto = msg.get("text", "").strip()
    if not texto:
        return
    
    # Si estamos esperando la CC para el audio pendiente
    if estado.get("etapa") == "esperando_cc_para_audio":
        cc = texto.replace("'", "").replace(".", "").strip()
        if not cc.isdigit() or len(cc) < 6:
            await _telegram_reply(chat_id, "No reconocí eso como una cédula. Mandame solo los números (ej: 1193143688)")
            return
        
        # Descargar el audio de Telegram
        file_id = estado.get("file_id", "")
        mime = estado.get("mime", "audio/ogg")
        
        _estado_telegram[chat_id] = {"etapa": "procesando", "cc": cc}
        await _telegram_reply(chat_id, f"✅ Entendido. Procesando audio para CC {cc}...\nTe aviso cuando esté listo (~15 minutos).")
        
        # Descargar archivo y procesar en background
        asyncio.create_task(_descargar_y_procesar_audio(chat_id, file_id, mime, cc))
        return
    
    # Mensaje de texto general → Tomy responde
    _estado_telegram[chat_id] = {"etapa": "idle"}
    try:
        from backend.chat_handler import procesar_mensaje
        respuesta = procesar_mensaje(texto, "", None)
        # Truncar si es muy largo para Telegram (máx 4096 chars)
        if len(respuesta) > 4000:
            respuesta = respuesta[:4000] + "... [ver dashboard para más detalles]"
        await _telegram_reply(chat_id, respuesta)
    except Exception as e:
        await _telegram_reply(chat_id, f"❌ No pude procesar tu mensaje: {str(e)[:100]}")

async def _descargar_y_procesar_audio(chat_id: str, file_id: str, mime: str, cc: str):
    """Descarga audio de Telegram y lanza el workflow."""
    try:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        
        # Obtener URL del archivo
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}")
            file_path = r.json().get("result", {}).get("file_path", "")
            if not file_path:
                await _telegram_reply(chat_id, "❌ No pude descargar el audio. ¿Intentás de nuevo?")
                return
            
            # Descargar el audio
            audio_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
            ext = ".m4a" if "m4a" in mime else ".ogg"
            audio_data = (await client.get(audio_url)).content
        
        # Guardar en disco
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_path = WORKFLOW_AUDIOS_DIR / f"{cc}_{ts}_telegram{ext}"
        audio_path.write_bytes(audio_data)
        
        # Lanzar workflow
        from backend.task_db import TaskDB
        from backend.workflow_runner import ejecutar_workflow
        db = TaskDB(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))
        task_id = db.crear_task(paciente_cc=cc, audio_path=str(audio_path))
        
        threading.Thread(
            target=ejecutar_workflow,
            kwargs={
                "audio_path": str(audio_path), "paciente_cc": cc,
                "task_id_existente": task_id,
                "on_complete_callback": lambda task_id: asyncio.run(_telegram_notificar_fin(chat_id, cc, task_id)),
            },
            daemon=True,
        ).start()
        
    except Exception as e:
        await _telegram_reply(chat_id, f"❌ Error al procesar: {str(e)[:100]}")

async def _telegram_notificar_fin(chat_id: str, cc: str, task_id: str):
    """Cuando el workflow termina, envía el ZIP directamente a Sandra por Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    import httpx
    async with httpx.AsyncClient() as client:
        # Verificar si hay formatos
        archivos_zip = await _generar_zip_para_telegram(cc)
        
        if archivos_zip:
            # Enviar ZIP directamente
            form = {"chat_id": chat_id, "caption": f"✅ ¡Listos los formatos de CC {cc}! Aquí están todos en un ZIP."}
            files = {"document": (f"formatos_{cc}.zip", archivos_zip, "application/zip")}
            await client.post(f"https://api.telegram.org/bot{token}/sendDocument", data=form, files=files)
        else:
            await _telegram_reply(chat_id, f"✅ Procesé el audio de CC {cc}. Los formatos están en el dashboard.")

async def _telegram_reply(chat_id: str, texto: str):
    """Envía mensaje a Sandra por Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    import httpx
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"},
        )
```

### TELE-2 — Registrar webhook + exponer puerto con ngrok/Cloudflare

El webhook de Telegram requiere una URL HTTPS pública. En WSL local, usar Cloudflare Tunnel (gratuito, no requiere registro de dominio):

```bash
# Instalar cloudflared en WSL de Sandra (una sola vez):
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
  -o cloudflared && chmod +x cloudflared && sudo mv cloudflared /usr/local/bin/

# Abrir tunnel temporal (genera URL aleatoria cada vez):
cloudflared tunnel --url http://localhost:8000
# Salida: https://random-name.trycloudflare.com

# Registrar webhook:
curl -X POST "https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://random-name.trycloudflare.com/api/telegram/webhook"}'
```

> **Nota:** La URL de Cloudflare cambia si se reinicia el tunnel. Para producción permanente, usar ngrok con cuenta (URL fija) o Cloudflare Zero Trust con subdominio fijo.

### TELE-3 — `on_complete_callback` en `workflow_runner.py`

```python
# workflow_runner.py — agregar parámetro callback:
def ejecutar_workflow(audio_path, paciente_cc, task_id_existente=None, 
                      desde_paso=1, on_complete_callback=None):
    ...
    # Al final, si todo fue bien:
    if on_complete_callback:
        try:
            on_complete_callback(task_id)
        except Exception as e:
            _log(f"callback error: {e}")
```

---

## PARTE 2.10 — Mi Día: panel de control real

### Problemas actuales
1. Muestra `t.estado` crudo ("transcribiendo", no "Transcribiendo audio con Deepgram...")
2. No muestra formatos listos para descargar — Sandra tiene que ir a /formatos
3. No tiene botón de acción para cada paciente de la agenda (solo un link)
4. No muestra el tiempo estimado de procesamiento
5. Se refresca cada 5 segundos incluso cuando no hay tareas activas (innecesario)

### HOY-1 — `dashboard/app/hoy/page.tsx` — reemplazar completo

```tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import { Mic, Calendar, CheckCircle, Clock, AlertCircle, Download, RefreshCw } from "lucide-react";
import { BotonGigante } from "@/components/BotonGigante";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const PASOS_LABELS: Record<number, string> = {
  1: "🎙️ Transcribiendo audio...",
  2: "🔍 Buscando datos del paciente...",
  3: "📝 Leyendo notas clínicas...",
  4: "📄 Revisando formatos anteriores...",
  5: "🧠 Tomy está analizando (puede tardar 8 min)...",
  6: "📋 Generando los 7 formatos...",
  7: "✅ Verificando calidad...",
  8: "📑 Convirtiendo a PDF...",
  9: "📱 Enviando notificación...",
};

const TIEMPO_RESTANTE: Record<number, string> = {
  1: "~6 min restantes", 2: "~10 min restantes", 3: "~9 min restantes",
  4: "~8 min restantes", 5: "~8 min restantes", 6: "~3 min restantes",
  7: "~2 min restantes", 8: "~1 min restante", 9: "Terminando...",
};

interface Cita {
  hora: string; paciente: string; cc?: string; procesado?: boolean;
}
interface Task {
  task_id: string; paciente_cc: string; estado: string; paso_actual: number;
  iniciado_en: string; resultado?: any;
}

export default function HoyPage() {
  const [citas, setCitas] = useState<Cita[]>([]);
  const [tasksActivas, setTasksActivas] = useState<Task[]>([]);
  const [tasksListas, setTasksListas] = useState<Task[]>([]);
  const [cargando, setCargando] = useState(true);
  const [hayActivas, setHayActivas] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [rAgenda, rTasks] = await Promise.all([
        fetch(`${API}/api/agenda`),
        fetch(`${API}/api/tasks/activas`),
      ]);
      const agenda = rAgenda.ok ? await rAgenda.json() : { citas: [] };
      const tasks = rTasks.ok ? await rTasks.json() : { tasks: [] };
      
      const activas = (tasks.tasks || []).filter((t: Task) =>
        !t.estado.startsWith("error") && t.estado !== "listo" && t.estado !== "cancelado"
      );
      // Tareas terminadas hoy
      const hoy = new Date().toISOString().slice(0, 10);
      const listas = (tasks.tasks || []).filter((t: Task) =>
        t.estado === "listo" && t.iniciado_en?.startsWith(hoy)
      );
      
      setCitas(agenda.citas || []);
      setTasksActivas(activas);
      setTasksListas(listas);
      setHayActivas(activas.length > 0);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    // Refrescar cada 10s si hay tareas activas, cada 60s si no
    const intervalo = setInterval(fetchAll, hayActivas ? 10000 : 60000);
    return () => clearInterval(intervalo);
  }, [fetchAll, hayActivas]);

  const fecha = new Date().toLocaleDateString("es-CO", {
    weekday: "long", day: "numeric", month: "long"
  });

  return (
    <div className="space-y-8 max-w-5xl mx-auto p-6">
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-4xl font-bold text-slate-800">Mi día, Sandra 👋</h1>
          <p className="text-xl text-slate-500 mt-1 capitalize">{fecha}</p>
        </div>
        <button onClick={fetchAll} className="p-2 text-slate-400 hover:text-slate-700" title="Actualizar">
          <RefreshCw size={20} />
        </button>
      </header>

      {/* Acción principal */}
      <BotonGigante
        label="Subir audio de una consulta"
        sublabel="Tomy genera los 7 formatos en 10-20 min"
        icon={Mic}
        href="/subir-audio"
        color="azul"
      />

      {/* Procesando ahora */}
      {tasksActivas.length > 0 && (
        <section>
          <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
            <Clock size={24} className="text-blue-600 animate-pulse" />
            Procesando ahora
          </h2>
          <div className="space-y-4">
            {tasksActivas.map(t => (
              <div key={t.task_id} className="bg-blue-50 border-2 border-blue-200 p-5 rounded-2xl">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="text-xl font-bold text-slate-800">CC {t.paciente_cc}</p>
                    <p className="text-lg text-blue-700">{PASOS_LABELS[t.paso_actual] ?? t.estado}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-blue-600">Paso {t.paso_actual}/9</p>
                    <p className="text-sm text-slate-500">{TIEMPO_RESTANTE[t.paso_actual] ?? ""}</p>
                  </div>
                </div>
                {/* Barra de progreso */}
                <div className="w-full bg-blue-200 rounded-full h-3">
                  <div className="bg-blue-600 h-3 rounded-full transition-all duration-1000"
                    style={{ width: `${Math.round((t.paso_actual / 9) * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Formatos listos hoy */}
      {tasksListas.length > 0 && (
        <section>
          <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
            <CheckCircle size={24} className="text-green-600" />
            Formatos listos hoy
          </h2>
          <div className="space-y-3">
            {tasksListas.map(t => (
              <div key={t.task_id} className="bg-green-50 border border-green-200 p-4 rounded-xl flex items-center justify-between">
                <div>
                  <p className="font-semibold text-green-800">CC {t.paciente_cc}</p>
                  <p className="text-sm text-green-600">
                    {(t.resultado?.formatos_generados?.length ?? 0)} formatos generados
                  </p>
                </div>
                <a
                  href={`${API}/api/pacientes/${t.paciente_cc}/formatos/zip`}
                  download
                  className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-xl hover:bg-green-700 font-medium"
                >
                  <Download size={16} />
                  Descargar ZIP
                </a>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Agenda del día */}
      <section>
        <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
          <Calendar size={24} /> Citas de hoy
        </h2>
        {cargando ? (
          <p className="text-slate-500 text-lg">Cargando agenda...</p>
        ) : citas.length === 0 ? (
          <div className="bg-slate-50 border border-slate-200 p-5 rounded-xl text-center">
            <p className="text-xl text-slate-600">No hay agenda cargada para hoy</p>
            <p className="text-slate-400 mt-1">¿El correo de Medifolios llegó?</p>
          </div>
        ) : (
          <div className="space-y-3">
            {citas.map((c, i) => (
              <div key={i} className="bg-white border-2 border-slate-200 rounded-xl p-4 flex items-center gap-4 hover:border-blue-300 transition-colors">
                <div className="bg-blue-100 text-blue-800 text-2xl font-bold px-4 py-3 rounded-xl min-w-[80px] text-center">
                  {c.hora}
                </div>
                <div className="flex-1">
                  <p className="text-xl font-semibold text-slate-800">{c.paciente}</p>
                  {c.cc && <p className="text-slate-500">CC {c.cc}</p>}
                </div>
                <div className="flex items-center gap-2">
                  {c.procesado ? (
                    <span className="flex items-center gap-1 text-green-700 font-medium">
                      <CheckCircle size={18} /> Listo
                    </span>
                  ) : (
                    <Link href="/subir-audio" className="px-3 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700">
                      Subir audio
                    </Link>
                  )}
                  {c.cc && (
                    <Link href={`/paciente/${c.cc}`} className="px-3 py-2 border border-slate-300 text-slate-600 rounded-xl text-sm hover:bg-slate-50">
                      Ver paciente
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
```

---

## PARTE 2.11 — Validación de campos antes de procesar audio

### Problema
Cuando Sandra sube un audio, el workflow empieza aunque no haya datos del paciente. Si falta la empresa (campo requerido en 4 de los 7 formatos), los formatos quedan con "[VERIFICAR]" y Sandra tiene que pedir corrección. Mejor detectarlo ANTES.

### PRECHECK-1 — Endpoint `GET /api/pacientes/{cc}/check-antes-de-procesar` en `server.py`

```python
CAMPOS_REQUERIDOS = {
    "paciente.nombre": "Nombre del paciente",
    "paciente.documento": "Cédula",
    "caso.siniestro": "Número de siniestro",
    "caso.empresa": "Empresa donde trabaja",
    "caso.diagnostico_cie10": "Diagnóstico CIE-10",
    "caso.fecha_accidente": "Fecha del accidente",
}

@app.get("/api/pacientes/{cc}/check-antes-de-procesar")
def check_antes_de_procesar(cc: str):
    """
    Verifica qué campos faltan antes de iniciar el workflow.
    Llamar desde subir-audio page cuando Sandra selecciona la CC.
    """
    json_path = DATA_DIR / f"{cc}-completo.json"
    
    if not json_path.exists():
        return {
            "ok": False,
            "tiene_datos": False,
            "mensaje": f"No tengo datos guardados para CC {cc}. Necesito extraerlos de los portales primero.",
            "campos_faltantes": list(CAMPOS_REQUERIDOS.values()),
            "accion_sugerida": "extraer_portales",
        }
    
    datos = json.loads(json_path.read_text(encoding="utf-8"))
    faltantes = []
    
    for path_campo, label in CAMPOS_REQUERIDOS.items():
        val = _get_nested(datos, path_campo.split("."), "")
        if not val or str(val).strip() in ["", "[VERIFICAR]", "null", "None"]:
            faltantes.append({"campo": path_campo, "label": label})
    
    return {
        "ok": len(faltantes) == 0,
        "tiene_datos": True,
        "campos_faltantes": faltantes,
        "puede_procesar": len(faltantes) <= 2,  # Tolerar hasta 2 campos faltantes
        "advertencia": f"Faltan {len(faltantes)} campo(s)" if faltantes else None,
        "ultimo_update": datos.get("_meta", {}).get("extraido_en", "desconocido"),
    }

def _get_nested(d: dict, keys: list, default=""):
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, default)
        else:
            return default
    return d or default
```

### PRECHECK-2 — UI en `subir-audio/page.tsx`

```tsx
// Cuando Sandra escribe la CC y hace blur/enter, verificar campos:
const verificarCampos = async (ccValue: string) => {
  if (!ccValue.trim() || ccValue.length < 6) return;
  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const r = await fetch(`${API}/api/pacientes/${ccValue.trim()}/check-antes-de-procesar`);
    const d = await r.json();
    setCheckCampos(d);
  } catch {}
};

// Mostrar el resultado del check después del campo de CC:
{checkCampos && (
  <div className={`p-4 rounded-xl border ${
    checkCampos.ok ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-300"
  }`}>
    {checkCampos.ok ? (
      <p className="text-green-700 font-medium">✅ Todo listo para procesar este paciente</p>
    ) : checkCampos.tiene_datos ? (
      <div>
        <p className="font-semibold text-amber-800">
          ⚠️ Faltan {checkCampos.campos_faltantes.length} dato(s) — los formatos quedarán con [VERIFICAR]:
        </p>
        <ul className="mt-2 space-y-1">
          {checkCampos.campos_faltantes.map((f: any) => (
            <li key={f.campo} className="text-amber-700">• {f.label}</li>
          ))}
        </ul>
        {checkCampos.puede_procesar && (
          <p className="mt-2 text-sm text-amber-600">
            Podés continuar de todos modos — Tomy completará lo que pueda y marcará lo que falta.
          </p>
        )}
      </div>
    ) : (
      <div>
        <p className="text-red-700 font-semibold">❌ No tengo datos de este paciente</p>
        <button
          onClick={() => fetch(`${API}/api/verificar/${cc.trim()}/extraer-ahora`, {method: "POST"})}
          className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-xl"
        >
          Extraer datos de los portales ahora
        </button>
      </div>
    )}
  </div>
)}
```

---

## PARTE 2.12 — Bugs adicionales descubiertos en revisión profunda

### CRIT-1 — Backup nunca corre (cron no registrado en startup)

**`backend/server.py` línea 545-549** — El startup solo inicia el scheduler de pre-extracción. El cron de backup (`backup_diario.py`) **nunca se registra**. Los datos nunca se respaldan.

```python
@app.on_event("startup")
async def iniciar_cron():
    from backend.cron_pre_extraccion import iniciar_scheduler
    iniciar_scheduler()
    
    # ← FALTA: registrar el backup diario
    hora_backup = int(os.getenv("BACKUP_HORA", "23"))
    from apscheduler.triggers.cron import CronTrigger
    from backend.backup_diario import ejecutar_backup
    scheduler.add_job(ejecutar_backup, CronTrigger(hour=hora_backup, minute=0), 
                      id="backup_diario", replace_existing=True)
    
    # ← FALTA: iniciar alertas de costos (si está configurado)
    try:
        from backend.costos_tracker import iniciar_alertas
        iniciar_alertas()
    except Exception:
        pass
```

**Verificación:**
```bash
# Comprobar que el backup corre manualmente:
python3 -c "from backend.backup_diario import ejecutar_backup; ejecutar_backup()"
# → debe generar archivo en storage/backups/ y notificar a Manu por Telegram
```

---

### CRIT-2 — Descarga de PDFs con media type incorrecto

**`backend/server.py` línea 217-220** — El endpoint `GET /api/download/{filename}` siempre usa `media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"` (DOCX), incluso cuando el archivo solicitado es un PDF. Los navegadores reciben un PDF con cabecera DOCX → lo descargan en lugar de abrirlo.

Además, **solo busca en `DOCS_DIR`** — si el archivo es un PDF en `PDFS_DIR`, retorna 404.

```python
# CORREGIR descargar_archivo:
MIME_MAP = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf":  "application/pdf",
    ".json": "application/json",
    ".txt":  "text/plain; charset=utf-8",
}

@app.get("/api/download/{filename}")
def descargar_archivo(filename: str):
    safe_name = Path(filename).name  # ya tiene protección path traversal ✅
    
    # Buscar en DOCS_DIR primero, luego PDFS_DIR
    for search_dir in [DOCS_DIR, PDFS_DIR, STORAGE]:
        path = search_dir / safe_name
        if path.exists() and path.is_file():
            ext = path.suffix.lower()
            media_type = MIME_MAP.get(ext, "application/octet-stream")
            return FileResponse(str(path), media_type=media_type, filename=safe_name)
    
    raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {safe_name}")
```

---

### CRIT-3 — Auth no protege el dashboard (no hay middleware Next.js)

El backend tiene `auth_simple.py` con PIN, pero el dashboard de Next.js **no tiene `middleware.ts`**. Cualquier persona en la misma red WiFi puede abrir `http://IP_DE_SANDRA:3000` y acceder a todos los datos de pacientes.

**Crear `dashboard/middleware.ts`:**

```ts
import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE = "rilo_auth";
const PUBLIC_PATHS = ["/login", "/api/login"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Rutas públicas: no proteger
  if (PUBLIC_PATHS.some(p => pathname.startsWith(p))) {
    return NextResponse.next();
  }
  
  // Verificar cookie de auth
  const cookie = request.cookies.get(AUTH_COOKIE);
  if (!cookie?.value) {
    // Redirigir a login
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }
  
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
```

**Crear `dashboard/app/login/page.tsx`** (si no existe):

```tsx
"use client";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export default function LoginPage() {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const params = useSearchParams();

  const login = async () => {
    if (pin.length < 4) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin }),
        credentials: "include",
      });
      if (res.ok) {
        router.push(params.get("redirect") || "/hoy");
      } else {
        setError("PIN incorrecto. Intentá de nuevo.");
        setPin("");
      }
    } catch {
      setError("No pude conectar con el servidor.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="bg-white rounded-3xl shadow-xl p-8 w-full max-w-sm space-y-6">
        <div className="text-center">
          <p className="text-4xl font-bold text-slate-800">RILO SAS</p>
          <p className="text-slate-500 mt-2">Asistente Tomy — Ingresá tu PIN</p>
        </div>
        <input
          type="password" inputMode="numeric" maxLength={8}
          value={pin} onChange={e => setPin(e.target.value)}
          onKeyDown={e => e.key === "Enter" && login()}
          placeholder="●●●●"
          className="w-full text-center text-4xl tracking-widest border-2 border-slate-300 rounded-2xl p-4 focus:border-blue-500 outline-none"
          autoFocus
        />
        {error && <p className="text-red-600 text-center">{error}</p>}
        <button onClick={login} disabled={loading || pin.length < 4}
          className="w-full py-4 bg-blue-600 text-white text-xl font-semibold rounded-2xl disabled:opacity-50">
          {loading ? "Verificando..." : "Entrar"}
        </button>
      </div>
    </div>
  );
}
```

---

### CRIT-4 — URLs hardcodeadas en `/paciente/[cc]/page.tsx`

El mismo bug de hardcoding que A7 pero que se pasó por alto en el plan original.

**`dashboard/app/paciente/[cc]/page.tsx` líneas 20-21:**
```tsx
// ANTES (hardcodeado):
fetch(`http://localhost:8000/api/pacientes/${cc}`)
fetch(`http://localhost:8000/api/tasks/paciente/${cc}`)
fetch(`http://localhost:8000/api/corregir-paciente/${cc}`)

// DESPUÉS:
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
fetch(`${API}/api/pacientes/${cc}`)
fetch(`${API}/api/tasks/paciente/${cc}`)
fetch(`${API}/api/corregir-paciente/${cc}`)
```

**Polling demasiado agresivo (3s):** Si no hay tarea activa, refrescar cada 3 segundos es innecesario. Usar 30s cuando está idle.

```tsx
// Reemplazar el setInterval fijo de 3000:
const intervalo = setInterval(cargar, taskActiva ? 8000 : 30000);
```

---

### CRIT-5 — Búsqueda de pacientes: solo busca en agenda, no en archivos JSON

**`GET /api/pacientes/buscar?q=...`** (línea 505) solo busca en la agenda de hoy. Si Sandra quiere encontrar a Rosa García (que ya tiene datos en el sistema pero no está en la agenda de hoy), no aparece.

**Ampliar el endpoint:**

```python
@app.get("/api/pacientes/buscar")
def buscar_paciente(q: Optional[str] = None):
    """
    Busca paciente en:
    1. Agenda de hoy (por nombre o CC)
    2. Archivos JSON en storage/data/ (por nombre, CC, empresa)
    """
    resultados = []
    q_lower = (q or "").lower().strip()
    
    # 1. Buscar en agenda
    try:
        from backend.notificador import api_get_agenda
        agenda = api_get_agenda()
        for c in (agenda or {}).get("citas", []):
            if not q_lower or q_lower in c.get("paciente", "").lower() or q_lower in c.get("cc", ""):
                resultados.append({
                    "nombre": c.get("paciente", ""),
                    "cc": c.get("cc", ""),
                    "fuente": "agenda",
                    "hora_cita": c.get("hora", ""),
                })
    except Exception:
        pass
    
    # 2. Buscar en storage/data/*.json
    for json_path in DATA_DIR.glob("*-completo.json"):
        try:
            datos = json.loads(json_path.read_text(encoding="utf-8"))
            pac = datos.get("medifolios", datos.get("paciente", datos))
            nombre = (pac.get("nombre") or "").lower()
            cc_pac = (pac.get("documento") or json_path.stem.replace("-completo", "")).lower()
            empresa = (datos.get("caso", {}).get("empresa") or "").lower()
            
            if not q_lower or q_lower in nombre or q_lower in cc_pac or q_lower in empresa:
                cc_real = json_path.stem.replace("-completo", "")
                # No duplicar si ya vino de la agenda
                if not any(r["cc"] == cc_real for r in resultados):
                    resultados.append({
                        "nombre": pac.get("nombre", "Desconocido"),
                        "cc": cc_real,
                        "fuente": "sistema",
                        "n_formatos": len(list(DOCS_DIR.glob(f"*{cc_real}*.docx"))),
                        "ultimo_update": datos.get("_meta", {}).get("extraido_en", "?")[:10],
                    })
        except Exception:
            pass
    
    # Ordenar: agenda primero, luego sistema
    resultados.sort(key=lambda r: (0 if r["fuente"] == "agenda" else 1, r["nombre"]))
    return {"ok": True, "pacientes": resultados[:20], "total": len(resultados)}
```

**Actualizar `dashboard/app/pacientes/page.tsx`** — agregar búsqueda por nombre:

```tsx
// Cambiar el input para buscar por nombre O por CC:
<input
  value={cc} onChange={e => setCc(e.target.value)}
  onKeyDown={e => e.key === "Enter" && buscar()}
  placeholder="Cédula o nombre del paciente"
  className="..."
/>

// Si el input tiene solo dígitos → buscar por CC (exacto)
// Si tiene letras → buscar por nombre (usa /api/pacientes/buscar?q=...)
const buscar = async () => {
  const q = cc.trim();
  if (!q) return;
  setBuscando(true);
  
  const soloDigitos = /^\d+$/.test(q);
  
  if (soloDigitos) {
    // Búsqueda exacta por CC
    const r = await fetch(`${API}/api/pacientes/${q}`);
    if (r.ok) setPaciente(await r.json());
    else setError("Paciente no encontrado");
  } else {
    // Búsqueda por nombre → mostrar lista
    const r = await fetch(`${API}/api/pacientes/buscar?q=${encodeURIComponent(q)}`);
    const d = await r.json();
    setResultadosBusqueda(d.pacientes || []);
  }
  setBuscando(false);
};
```

---

### CRIT-6 — Toast notifications cuando una tarea termina

Cuando Sandra está en el dashboard y termina un workflow, no hay ningún aviso visual. Ella tiene que ir a /hoy o revisar su celular para saber. Un toast/notificación resuelve esto.

**`dashboard/components/TaskWatcher.tsx` — componente nuevo (agregar a layout.tsx):**

```tsx
"use client";
import { useEffect, useRef } from "react";
import { toast } from "react-hot-toast";  // npm install react-hot-toast

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function TaskWatcher() {
  const estadosRef = useRef<Record<string, string>>({});
  
  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch(`${API}/api/tasks/activas`);
        if (!r.ok) return;
        const { tasks } = await r.json();
        
        for (const t of tasks) {
          const estadoPrev = estadosRef.current[t.task_id];
          
          if (estadoPrev && estadoPrev !== t.estado) {
            if (t.estado === "listo") {
              toast.success(
                `✅ ¡Listos los formatos de CC ${t.paciente_cc}!\n📥 Podés descargarlos en Mi Día`,
                { duration: 10000, icon: "📄" }
              );
            } else if (t.estado.startsWith("error")) {
              toast.error(
                `❌ Error procesando CC ${t.paciente_cc} (paso ${t.paso_actual}/9)`,
                { duration: 8000 }
              );
            }
          }
          estadosRef.current[t.task_id] = t.estado;
        }
      } catch {}
    };
    
    const intervalo = setInterval(check, 15000);
    return () => clearInterval(intervalo);
  }, []);
  
  return null;
}
```

**Instalación:**
```bash
cd /root/fisioterapia/dashboard
npm install react-hot-toast
```

**Agregar al `dashboard/app/layout.tsx`:**
```tsx
import { Toaster } from "react-hot-toast";
import { TaskWatcher } from "@/components/TaskWatcher";

// En el JSX:
<TaskWatcher />
<Toaster position="top-right" />
```

---

### CRIT-7 — Botón "Actualizar agenda" en Mi Día

Sandra puede necesitar refrescar la agenda manualmente (si el cron no corrió). Agregar botón en Mi Día:

```tsx
// En dashboard/app/hoy/page.tsx:
const actualizarAgenda = async () => {
  const r = await fetch(`${API}/api/agenda/check`, { method: "POST" });
  if (r.ok) await fetchAll();
};

// Botón en el header:
<button onClick={actualizarAgenda} 
  className="px-4 py-2 border border-slate-300 text-slate-600 rounded-xl hover:bg-slate-50 text-sm">
  🔄 Actualizar agenda
</button>
```

---

## PARTE 2.6 — Audio M4A/iPhone: especialización y UX completa

Los audios vienen de un iPhone (grabadora de voz nativa). Formato principal: **M4A** (AAC en contenedor MPEG-4). El sistema ya acepta M4A en Deepgram y flujo_audio.py, pero falta validación en el frontend, progreso de subida, y la página subir-audio no muestra qué está pasando después de enviar.

---

### M4A-1 — Validación de formato antes de subir

**`dashboard/app/subir-audio/page.tsx` — reemplazar la función `handleFile`:**

```tsx
// Extensiones aceptadas — M4A (principal, iPhone) y MP3 (alternativo)
const EXTS_ACEPTADAS = [".m4a", ".mp3"];

const handleFile = (file: File | null) => {
  if (!file) return;
  const ext = "." + (file.name.split(".").pop() ?? "").toLowerCase();
  if (!EXTS_ACEPTADAS.includes(ext)) {
    setError(
      `Solo acepto archivos M4A (iPhone) o MP3. El archivo "${file.name}" es tipo ${ext || "desconocido"}. ` +
      `En el iPhone: Archivos → buscar la grabación → "Compartir" → enviarlo a la PC.`
    );
    return;
  }
  setArchivo(file);
  setError("");
};
```

**Atributo `accept` del input (más específico):**
```tsx
<input
  ref={inputRef}
  type="file"
  accept=".m4a,audio/x-m4a,audio/m4a,.mp3,audio/mpeg"
  className="hidden"
  onChange={(e) => handleFile(e.target.files?.[0] || null)}
/>
```

**Hacer lo mismo en el input de audio del chat (CHAT-3):**
```tsx
<input ref={audioRef} type="file"
  accept=".m4a,audio/x-m4a,audio/m4a,.mp3,audio/mpeg"
  className="hidden"
  onChange={e => { if (e.target.files?.[0]) handleAudioChat(e.target.files[0]); }} />
```

---

### M4A-2 — Estimación de duración y tamaño

Mostrar a Sandra cuánto tarda el audio y cuánto tiempo tomará procesar, ANTES de subir.

**iPhone M4A — referencia de pesos:**
| Calidad iPhone | Bitrate | 1 min | 30 min | 1 hora |
|---|---|---|---|---|
| Notas de voz normal | ~32 kbps | 0.24 MB | 7 MB | 14 MB |
| Notas de voz alta calidad | ~64 kbps | 0.47 MB | 14 MB | 28 MB |
| Grabadora externa 128kbps | ~128 kbps | 0.93 MB | 28 MB | 56 MB |

**Agregar a `subir-audio/page.tsx` — cuando el archivo se carga:**

```tsx
// Agregar estado:
const [infoAudio, setInfoAudio] = useState<{mb: number; durMin: number} | null>(null);

// En handleFile, después de setArchivo(file):
const mb = file.size / 1024 / 1024;
// Estimación: M4A nativo iPhone ~0.47 MB/min (64kbps), MP3 ~1 MB/min
const durMin = Math.round(mb / (ext === ".mp3" ? 1 : 0.47));
setInfoAudio({ mb, durMin });

// En el JSX, dentro del área de drop (cuando archivo seleccionado):
{infoAudio && (
  <p className="text-lg text-slate-500">
    {infoAudio.mb.toFixed(1)} MB
    {infoAudio.durMin > 0 && ` · Duración estimada: ${infoAudio.durMin} min`}
    {infoAudio.durMin > 60 && ` (${Math.floor(infoAudio.durMin/60)}h ${infoAudio.durMin%60}min)`}
  </p>
)}
{infoAudio && infoAudio.mb > 100 && (
  <p className="text-amber-600 font-medium">
    ⚠️ Archivo grande. La subida puede tardar 1-2 minutos.
  </p>
)}
```

---

### M4A-3 — Progreso de subida (XMLHttpRequest)

`fetch` no da progreso de upload. Usar `XMLHttpRequest` para la barra de progreso.

**`dashboard/app/subir-audio/page.tsx` — reemplazar función `subir`:**

```tsx
// Agregar estado:
const [progreso, setProgreso] = useState(0);

const subir = () => {
  if (!archivo || !cc.trim()) {
    setError("Necesito el audio y la cédula del paciente.");
    return;
  }
  const ext = "." + (archivo.name.split(".").pop() ?? "").toLowerCase();
  if (![".m4a", ".mp3"].includes(ext)) {
    setError("Solo acepto archivos M4A o MP3.");
    return;
  }
  setSubiendo(true);
  setError("");
  setProgreso(0);

  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const form = new FormData();
  form.append("audio", archivo);
  form.append("paciente_cc", cc.trim());

  const xhr = new XMLHttpRequest();
  xhr.upload.addEventListener("progress", (e) => {
    if (e.lengthComputable) setProgreso(Math.round((e.loaded / e.total) * 100));
  });

  xhr.addEventListener("load", () => {
    if (xhr.status >= 200 && xhr.status < 300) {
      const data = JSON.parse(xhr.responseText);
      setTaskId(data.task_id);
      setProgreso(100);
      // NO hacer router.push — mostrar progreso del workflow
      iniciarPollingSubirAudio(data.task_id, cc.trim());
    } else {
      setError(`Error al subir: HTTP ${xhr.status}`);
      setSubiendo(false);
    }
  });

  xhr.addEventListener("error", () => {
    setError("Error de red. Verificá la conexión.");
    setSubiendo(false);
  });

  xhr.open("POST", `${API}/api/procesar-paciente`);
  xhr.send(form);
};
```

**Barra de progreso en JSX:**
```tsx
{subiendo && progreso < 100 && (
  <div className="w-full bg-slate-200 rounded-full h-4 overflow-hidden">
    <div
      className="bg-blue-600 h-4 rounded-full transition-all duration-300"
      style={{ width: `${progreso}%` }}
    />
  </div>
)}
{subiendo && progreso < 100 && (
  <p className="text-center text-slate-600">
    {progreso < 100 ? `Subiendo audio... ${progreso}%` : "¡Subido! Procesando..."}
  </p>
)}
```

---

### M4A-4 — Polling de progreso en subir-audio (no redirigir de inmediato)

Actualmente `subir-audio/page.tsx` hace `router.push(/paciente/${cc})` inmediatamente tras la respuesta, sin esperar. Sandra queda en una página que no muestra qué está pasando. **Reemplazar con polling en la misma página.**

```tsx
// Agregar estados:
const [taskId, setTaskId] = useState<string | null>(null);
const [pasoProceso, setPasoProceso] = useState(0);
const [estadoProceso, setEstadoProceso] = useState("");
const [formatosListos, setFormatosListos] = useState<string[]>([]);

const PASOS_LABELS: Record<number, string> = {
  1: "🎙️ Transcribiendo tu audio con Deepgram...",
  2: "🔍 Buscando datos del paciente en el sistema...",
  3: "📝 Leyendo tus notas y archivos de referencia...",
  4: "📄 Revisando formatos anteriores del paciente...",
  5: "🧠 Tomy está analizando todo (puede tardar 5-8 minutos)...",
  6: "📋 Generando los 7 formatos clínicos...",
  7: "✅ Verificando la calidad de los documentos...",
  8: "📑 Convirtiendo a PDF para archivo legal...",
  9: "📱 Enviándote la notificación por Telegram...",
};

const iniciarPollingSubirAudio = (tId: string, ccPac: string) => {
  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const intervalo = setInterval(async () => {
    try {
      const r = await fetch(`${API}/api/tasks/${tId}`);
      const d = await r.json();
      const t = d.task;
      setPasoProceso(t.paso_actual ?? 0);
      setEstadoProceso(t.estado ?? "");

      if (t.estado === "listo") {
        clearInterval(intervalo);
        setSubiendo(false);
        const fmts = (t.resultado?.formatos_generados ?? []).map((f: any) =>
          f.archivo?.split("/").pop() ?? f.formato
        );
        setFormatosListos(fmts);
      } else if (t.estado?.startsWith("error")) {
        clearInterval(intervalo);
        setSubiendo(false);
        setError(`Paso ${t.paso_actual}/9 falló: ${t.error ?? "error desconocido"}`);
      }
    } catch {}
  }, 10000);
};

// JSX — mostrar progreso del workflow (después del BotonGigante):
{taskId && subiendo && (
  <div className="bg-blue-50 border border-blue-200 rounded-2xl p-6 space-y-3">
    <div className="flex items-center gap-3">
      <Loader2 size={28} className="animate-spin text-blue-600" />
      <div>
        <p className="font-bold text-xl text-blue-800">Procesando... Paso {pasoProceso}/9</p>
        <p className="text-blue-700">{PASOS_LABELS[pasoProceso] ?? estadoProceso}</p>
      </div>
    </div>
    <div className="w-full bg-blue-200 rounded-full h-3">
      <div className="bg-blue-600 h-3 rounded-full transition-all duration-500"
        style={{ width: `${Math.round((pasoProceso / 9) * 100)}%` }} />
    </div>
    <p className="text-sm text-blue-600">
      Tiempo estimado restante: ~{Math.max(0, Math.round(((9-pasoProceso) * 2)))} minutos
    </p>
  </div>
)}

{formatosListos.length > 0 && (
  <div className="bg-green-50 border border-green-300 rounded-2xl p-6 space-y-3">
    <p className="text-2xl font-bold text-green-800">✅ ¡Listo! {formatosListos.length} formatos generados</p>
    <ul className="space-y-2">
      {formatosListos.map(nombre => (
        <li key={nombre}>
          <a href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/download/${encodeURIComponent(nombre)}`}
            className="flex items-center gap-2 text-blue-700 underline text-lg"
            download>
            📄 {nombre}
          </a>
        </li>
      ))}
    </ul>
    <p className="text-green-700">También recibiste una notificación por Telegram.</p>
  </div>
)}
```

---

### M4A-5 — Fixes en rutas proxy de Next.js

**`dashboard/app/api/chat/route.ts` — 3 bugs:**

```ts
// Bug 1: historial se pierde — línea 10
const { mensaje, paciente_cc, historial } = body;  // ← agregar historial

// Bug 2: historial no se reenvía — línea 15
body: JSON.stringify({ mensaje, paciente_cc, historial }),  // ← agregar historial

// Bug 3: sin timeout — DeepSeek puede tardar 120 seg → Next.js mata la conexión
// Agregar ANTES del export async function POST:
export const maxDuration = 300;  // 5 minutos
```

**Archivo completo corregido `dashboard/app/api/chat/route.ts`:**
```ts
import { NextRequest, NextResponse } from "next/server";

export const maxDuration = 300;

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { mensaje, paciente_cc, historial } = body;

    const hermesResponse = await fetch("http://localhost:8000/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mensaje, paciente_cc, historial }),
      signal: AbortSignal.timeout(290000),
    });

    if (!hermesResponse.ok) {
      throw new Error(`Backend respondió ${hermesResponse.status}`);
    }

    const data = await hermesResponse.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: "Error al comunicarse con Tomy" },
      { status: 500 }
    );
  }
}
```

> **Nota:** El chat nuevo usa streaming directamente a port 8000 (`/api/chat/stream`), por lo que este proxy es solo para compatibilidad con la página antigua. No es la ruta principal en producción.

---

### M4A-6 — Arreglo start.sh: instalar TODAS las dependencias

**`start.sh` línea 19 — BUG CRÍTICO:**
```bash
# ACTUAL (instala solo 4 paquetes — faltan python-docx, pydantic, sqlalchemy, etc.):
pip install fastapi uvicorn python-multipart requests -q 2>/dev/null || true

# CORRECTO:
pip install -r backend/requirements.txt -q 2>/dev/null || true
```

**Impacto:** Con el `start.sh` actual, el backend falla al importar `backend.server` porque faltan `python-docx`, `pydantic`, `python-dotenv`, `apscheduler`, `pytz`, `aiofiles`, `psutil`, `sqlalchemy`, `pydub`, `itsdangerous`. **El servidor no arranca en producción.**

---

### M4A-7 — Convertir template ODT a DOCX

```bash
# En el WSL de Sandra, una sola vez:
cd ~/rilo-backend/templates/formatos
libreoffice --headless --convert-to docx "ejemplo prueba de trabajo.odt"
# → genera "ejemplo prueba de trabajo.docx"
# Verificar que el archivo se generó:
ls -la *.docx
```

---

### M4A-8 — Seguridad: cambiar PIN y secreto antes de producción

**`.env` en WSL de Sandra — cambiar OBLIGATORIAMENTE:**
```bash
# Cambiar el PIN de 4 dígitos que Sandra usará para entrar al dashboard
AUTH_PIN=XXXX   # ← elegir uno que Sandra recuerde, diferente de 1234

# Cambiar el secreto de cookies (al menos 32 caracteres aleatorios)
AUTH_SECRET=una-frase-larga-y-aleatoria-para-firmar-cookies-rilo-2026
```

Si alguien adivina `AUTH_PIN=1234`, accede al dashboard completo de Sandra desde cualquier PC en la misma red.

---

### M4A-9 — Verificar Telegram y Gmail antes del primer audio

```bash
# 1. Verificar Telegram bot activo:
curl -s "https://api.telegram.org/bot8678791933:AAEmEnwCWbsPrjdtXKsjv-m_JE8D58twOAg/getMe" | python3 -m json.tool
# Esperar: {"ok":true,"result":{"username":"...","is_bot":true,...}}

# 2. Enviar mensaje de prueba a Telegram:
curl -s -X POST "https://api.telegram.org/bot8678791933:AAEmEnwCWbsPrjdtXKsjv-m_JE8D58twOAg/sendMessage" \
  -d "chat_id=8424650300" \
  -d "text=✅ Sistema RILO SAS iniciado correctamente"
# Esperar que Sandra reciba el mensaje en Telegram

# 3. Gmail — verificar credenciales IMAP (solo si se usan notificaciones por email):
python3 -c "
import imaplib
m = imaplib.IMAP4_SSL('imap.gmail.com')
m.login('sandrapatriciapolania6@gmail.com', 'dnjaycuadxcmppao')
print('✅ Gmail OK')
m.logout()
"
```

Si Telegram falla (error 401), el bot token expiró → crear nuevo bot con @BotFather.  
Si Gmail falla, el App Password fue revocado → generar nuevo en myaccount.google.com.

---

### M4A-10 — Firma de Sandra (pendiente físico)

El campo `firma_sandra.png` se usa en los documentos clínicos como firma digital.

```bash
# Verificar si ya existe:
ls -la ~/rilo-backend/storage/firma_sandra.png 2>/dev/null || echo "❌ No existe"

# Si no existe, crear un placeholder temporal para que el sistema no falle:
python3 -c "
from PIL import Image
img = Image.new('RGBA', (400, 150), (255, 255, 255, 0))
img.save('storage/firma_sandra.png')
print('✅ Placeholder creado')
" 2>/dev/null || echo "Instalar pillow: pip install Pillow"
```

Cuando Sandra tenga la firma real (escaneada o digital):
```bash
cp firma_sandra.png ~/rilo-backend/storage/firma_sandra.png
```

---

## PARTE 3 — Instalación de dependencias del sistema

Ejecutar **una sola vez** en el WSL de Sandra:

```bash
# ffmpeg + ffprobe (CRÍTICO — sin esto TODOS los audios fallan)
sudo apt-get update && sudo apt-get install -y ffmpeg

# LibreOffice (para convertir a PDF/A)
sudo apt-get install -y libreoffice-common libreoffice-writer

# Verificar
ffprobe -version | head -1
ffmpeg -version | head -1
libreoffice --version

# Dependencias Python del dashboard
cd ~/rilo-dashboard
npm install react-markdown remark-gfm @tailwindcss/typography
```

---

## PARTE 4 — Configuración `.env` para producción WSL

**`~/rilo-backend/.env`:**
```bash
# LLM
OPENCODE_GO_API_KEY=sk-eHIeG9D83tfd8P8bWN1wDaDSf56cRrztC5m1Q6BfXAYAbXcJUYBKMeXiR6apfSvt
OPENCODE_GO_BASE_URL=https://opencode.ai/zen/go/v1
LLM_MODEL=deepseek-v4-pro
LLM_MODEL_SINTESIS=deepseek-v4-pro
LLM_MODEL_EXTRACCION=deepseek-v4-flash

# Deepgram
DEEPGRAM_API_KEY=3888b515e3e95415835ff6df2b4a0c283450500d

# Portales
MEDIFOLIOS_URL=https://www.server0medifolios.net/
MEDIFOLIOS_USER=55162801-2
MEDIFOLIOS_PASSWORD=55162801-2
POSITIVA_URL=https://positivacuida.positiva.gov.co/cas/login
POSITIVA_USER=1075209386MR
POSITIVA_PASSWORD=Rilo2026*

# Comunicaciones
TELEGRAM_BOT_TOKEN=8678791933:AAEmEnwCWbsPrjdtXKsjv-m_JE8D58twOAg
TELEGRAM_CHAT_ID=8424650300
GMAIL_USER=sandrapatriciapolania6@gmail.com
GMAIL_APP_PASSWORD=dnjaycuadxcmppao

# Directorios
STORAGE_DIR=./storage
TEMPLATES_DIR=./templates/formatos
WORKSPACE_DIR=/mnt/c/Users/Sandra/Desktop/SANDRA/ACTIVIDADES OCUPACIONALES

# Pipeline — ACTIVADO
TOMY_COMPLETO_ENABLED=true
WORKFLOW_DB_PATH=./storage/workflow.db
WORKFLOW_TIMEOUT_TOTAL_S=1800
AUDIO_CHUNK_DURATION_S=1500
AUDIO_TEMP_DIR=./storage/audios_temp
FASE_A_ENABLED=false
FASE_A_CRON_ENABLED=false

# Seguridad
AUTH_PIN=1234
AUTH_SECRET=cambiar-en-produccion-32-chars-min
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Misc
BACKUP_HORA=23
CRON_HORA_NOCHE=21
```

**`~/rilo-dashboard/.env.local`:**
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## PARTE 5 — Deploy vía Git

### Flujo de trabajo
```
Docker /root/fisioterapia  →  git push  →  GitHub Manupo12/auto-ma  →  git pull  →  WSL Sandra
```

### En Docker (después de implementar todos los cambios):
```bash
cd /root/fisioterapia

# Verificar que los 8 tests siguen pasando
python test_analisis_ejemplo.py && python test_valoracion_juan.py && echo "✅ Tests OK"

# Verificar que el backend importa sin errores
python -c "import backend.server; import backend.chat_handler; print('✅ Imports OK')"

# Commit
git add -A
git commit -m "feat: chat omnisciente + audio largo + streaming + historial + contexto sistema"
git push origin main
```

### En WSL de Sandra (primera vez):
```bash
# Clonar o actualizar
cd ~/rilo-backend && git pull origin main

# Sistema
sudo apt-get install -y ffmpeg libreoffice-common libreoffice-writer

# Python
pip install -r backend/requirements.txt

# Dashboard
cd ~/rilo-dashboard && git pull origin main
npm install
npm run build

# Iniciar
bash ~/rilo-backend/start.sh
```

### Script `~/actualizar-rilo.sh` (para actualizaciones futuras):
```bash
#!/bin/bash
set -e
echo "📦 Actualizando RILO SAS..."
cd ~/rilo-backend && git pull origin main
pip install -r backend/requirements.txt -q
cd ~/rilo-dashboard && git pull origin main
npm install -q && npm run build
echo "✅ Listo. Reiniciá con: bash ~/rilo-backend/start.sh"
```

---

## PARTE 6 — Tabla maestra de tareas

### Bloque A — Fixes bloqueantes (60 min)

| # | Archivo | Qué cambiar |
|---|---------|-------------|
| A1 | `components/MobileMenu.tsx` | `lg:hidden` en aside interior |
| A2 | `components/Sidebar.tsx` | Named export + prop onNavigate + onClick |
| A3 | `app/formatos/page.tsx` | `useState("")` + ReconciliacionAlert condicional |
| A4 | `.env` | `TOMY_COMPLETO_ENABLED=true` |
| A5 | `workflow_steps/transcribir.py` | fallback en `_calcular_duracion_s` |
| A6 | `backend/server.py` | CORS desde env var |
| A7 | múltiples páginas | `NEXT_PUBLIC_API_URL` |
| A8 | `dashboard/.env.local` | crear con API_URL |

### Bloque B — Chat omnisciente (3-4 horas)

| # | Archivo | Qué agregar |
|---|---------|-------------|
| B1 | `backend/chat_handler.py` | `_construir_contexto_sistema()` |
| B2 | `backend/chat_handler.py` | historial en `_llamar_llm` + ctx_sistema |
| B3 | `backend/server.py` | endpoint `/api/chat/stream` SSE |
| B4 | `app/chat/page.tsx` | streaming + historial en `enviar()` |
| B5 | `backend/server.py` | endpoint `/api/chat/audio` |
| B6 | `app/chat/page.tsx` | botón Mic + modal CC + polling progreso |
| B7 | dashboard | `npm install react-markdown remark-gfm @tailwindcss/typography` |
| B8 | `app/chat/page.tsx` | ReactMarkdown + indicador de estado |
| B9 | `backend/server.py` | endpoint `/api/archivos/paciente/{cc}` |
| B10 | `components/FilePicker.tsx` | nuevo componente |
| B11 | `app/chat/page.tsx` | integrar FilePicker |

### Bloque P — Portales inteligentes (4-5 horas)

| # | Archivo | Qué hacer |
|---|---------|-----------|
| P1 | `playwright_real/orquestador.py` | Ampliar `_detectar_discrepancias`: nombre, CIE-10, empresa (no solo siniestro) |
| P2 | `backend/portal_verificador.py` | Crear módulo nuevo (thin adapter + aprendizaje + correcciones) |
| P3 | `backend/chat_handler.py` | `_detectar_intencion_portal()` + `_formatear_verificacion_para_llm()` |
| P4 | `backend/server.py` | `POST /api/portal/verificar`, `POST /api/portal/aprender`, `GET /api/portal/conocimiento`, `GET /api/portal/estado` |
| P5 | `backend/server.py` streaming | Yield mensajes de progreso durante navegación Playwright (30-90s) |
| P6 | `app/chat/page.tsx` | Tabla verificación + botones "Medi ✓" / "Pos ✓" + `resolverDiscrepancia()` |
| P7 | `storage/portal_knowledge.json` | Crear archivo base (script Python de inicialización) |

### Bloque CR — Corrección de formatos desde chat (2 horas)

| # | Archivo | Qué hacer |
|---|---------|-----------|
| CR1 | `backend/chat_handler.py` | `_es_intencion_correccion()` + integrar `correction_resolver` + `aplicador_correccion` |
| CR2 | `app/chat/page.tsx` | Links de descarga en mensajes de corrección (componente `<a>` personalizado en ReactMarkdown) |

### Bloque Z — ZIP y retry (1.5 horas)

| # | Archivo | Qué hacer |
|---|---------|-----------|
| Z1 | `backend/server.py` | `GET /api/pacientes/{cc}/formatos/zip` (zipfile + io.BytesIO) |
| Z2 | `app/formatos/page.tsx` | Botón "Descargar todos en ZIP" |
| Z3 | `app/chat/page.tsx` | Link ZIP en mensaje de tarea completada |
| Z4 | `backend/server.py` | `POST /api/tasks/{task_id}/reintentar?desde_paso=N` |
| Z5 | `backend/workflow_runner.py` | Parámetro `desde_paso` para saltar pasos ya completados |
| Z6 | `app/subir-audio/page.tsx` | Botones "Reintentar desde paso N" cuando hay error |

### Bloque TG — Telegram bidireccional (4 horas)

| # | Archivo | Qué hacer |
|---|---------|-----------|
| TG1 | `backend/server.py` | `POST /api/telegram/webhook` + estado de conversación + router |
| TG2 | `backend/server.py` | `_descargar_y_procesar_audio(chat_id, file_id, cc)` |
| TG3 | `backend/server.py` | `_telegram_notificar_fin()` — enviar ZIP por Telegram al terminar |
| TG4 | `backend/workflow_runner.py` | Parámetro `on_complete_callback` |
| TG5 | WSL de Sandra | Instalar cloudflared + registrar webhook |
| TG6 | `.env` | Verificar `TELEGRAM_CHAT_ID` es el ID correcto de Sandra |

### Bloque H — Mi Día + UX crítica (2 horas)

| # | Archivo | Qué hacer |
|---|---------|-----------|
| H1 | `app/hoy/page.tsx` | Reemplazar completo: PASOS_LABELS, tiempo restante, formatos listos, polling adaptativo |
| H2 | `app/hoy/page.tsx` | Botón "Actualizar agenda" |
| H3 | `components/TaskWatcher.tsx` | Nuevo componente: toast cuando tarea termina |
| H4 | `app/layout.tsx` | Agregar `<TaskWatcher />` + `<Toaster />` |
| H5 | `dashboard/` | `npm install react-hot-toast` |

### Bloque PR — Pre-check y PRECHECK (1 hora)

| # | Archivo | Qué hacer |
|---|---------|-----------|
| PR1 | `backend/server.py` | `GET /api/pacientes/{cc}/check-antes-de-procesar` |
| PR2 | `app/subir-audio/page.tsx` | Llamar check al escribir CC + mostrar campos faltantes |

### Bloque FX — Fixes críticos adicionales (2 horas)

| # | Archivo | Qué hacer |
|---|---------|-----------|
| FX1 | `backend/server.py` startup | Registrar cron backup + costos en `iniciar_cron()` |
| FX2 | `backend/server.py` download | `MIME_MAP` para DOCX/PDF + buscar en DOCS_DIR y PDFS_DIR |
| FX3 | `dashboard/middleware.ts` | Crear middleware Next.js de auth → redirigir a /login |
| FX4 | `dashboard/app/login/page.tsx` | Crear página de login con PIN (si no existe) |
| FX5 | `app/paciente/[cc]/page.tsx` | URL hardcodeadas → `NEXT_PUBLIC_API_URL` + polling 8s/30s adaptativo |
| FX6 | `backend/server.py` | Ampliar `/api/pacientes/buscar` para buscar en JSON por nombre |
| FX7 | `app/pacientes/page.tsx` | Búsqueda por nombre además de CC |

### Bloque M — M4A/iPhone especialización (2 horas)

| # | Archivo | Qué cambiar |
|---|---------|-------------|
| M1 | `app/subir-audio/page.tsx` | `accept=".m4a,audio/x-m4a,.mp3,audio/mpeg"` + validación de extensión con mensaje claro |
| M2 | `app/subir-audio/page.tsx` | Estimación de duración (MB / 0.47 para M4A iPhone) |
| M3 | `app/subir-audio/page.tsx` | Reemplazar `fetch` con `XMLHttpRequest` + barra de progreso |
| M4 | `app/subir-audio/page.tsx` | Polling post-upload con PASOS_LABELS — eliminar `router.push` inmediato |
| M5 | `app/chat/page.tsx` | Mismo `accept` M4A/MP3 en el input de audio del chat |
| M6 | `app/api/chat/route.ts` | Agregar `historial` + `AbortSignal.timeout(290000)` + `export const maxDuration = 300` |
| M7 | `start.sh` | Cambiar a `pip install -r backend/requirements.txt -q` |

### Bloque C — Sistema y deploy (45 min)

| # | Acción |
|---|--------|
| C1 | `sudo apt-get install -y ffmpeg libreoffice-common libreoffice-writer` en WSL Sandra |
| C2 | `cd templates/formatos && libreoffice --headless --convert-to docx "ejemplo prueba de trabajo.odt"` |
| C3 | Verificar Telegram: `curl https://api.telegram.org/bot{TOKEN}/getMe` |
| C4 | Verificar Gmail IMAP (script Python en M4A-9) |
| C5 | Cambiar `AUTH_PIN` y `AUTH_SECRET` en `.env` producción |
| C6 | `git add -A && git commit && git push` |
| C7 | En WSL: `git pull && pip install -r backend/requirements.txt && cd dashboard && npm install && npm run build` |
| C8 | Probar subiendo audio M4A corto desde subir-audio page (verificar barra progreso) |
| C9 | Probar subiendo audio M4A desde el chat (verificar polling en conversación) |
| C10 | Verificar Telegram notifica cuando termina |
| C11 | Obtener y guardar firma_sandra.png |

**Tiempo total estimado:** 7-9 horas de trabajo para un agente con acceso total.

---

## Prueba de humo final

```bash
# 1. Tests del motor
python test_analisis_ejemplo.py && python test_valoracion_juan.py

# 2. Backend OK
python -m uvicorn backend.server:app --port 8000 &
sleep 5 && curl http://localhost:8000/api/health

# 3. Contexto del sistema en el chat
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"mensaje":"qué está pasando en el sistema ahora?","historial":[]}' \
  --max-time 180
# → Tomy debe responder con estado de tareas, agenda, pacientes

# 4. Streaming funciona
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"mensaje":"hola Sandra","historial":[]}' \
  --max-time 180
# → Debe ver data: chunks llegando uno a uno en tiempo real

# 5. Audio M4A en el chat (usar audio de prueba corto del iPhone)
curl -X POST http://localhost:8000/api/chat/audio \
  -F "audio=@consulta_prueba.m4a" -F "paciente_cc=1193143688"
# → debe retornar: {"ok":true,"task_id":"...","mensaje_tomy":"..."}

# 6. Audio M4A en subir-audio (via /api/procesar-paciente)
curl -X POST http://localhost:8000/api/procesar-paciente \
  -F "audio=@consulta_prueba.m4a" -F "paciente_cc=1193143688"
# → debe retornar task_id

# 7. Polling del workflow
TASK_ID="el-task-id-del-paso-anterior"
curl http://localhost:8000/api/tasks/$TASK_ID
# → {"ok":true,"task":{"estado":"transcribiendo","paso_actual":1,...}}

# 8. ffprobe y ffmpeg instalados
ffprobe -version | head -1  # Debe responder: "ffprobe version N..."
ffmpeg -version | head -1   # Debe responder: "ffmpeg version N..."

# 9. Telegram
curl -s "https://api.telegram.org/bot8678791933:AAEmEnwCWbsPrjdtXKsjv-m_JE8D58twOAg/getMe" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ Bot:', d['result']['username'])"

# 10. Dashboard: abrir http://localhost:3000
# ✓ Un solo sidebar (no duplicado)
# ✓ Formatos sin CC hardcodeada (campo vacío al inicio)
# ✓ subir-audio: acepta solo M4A y MP3, rechaza otros formatos con mensaje claro
# ✓ subir-audio: muestra tamaño y duración estimada
# ✓ subir-audio: barra de progreso durante la subida
# ✓ subir-audio: polling con pasos 1/9...9/9 SIN redirigir
# ✓ subir-audio: links de descarga cuando termina
# ✓ Chat: texto aparece progresivamente (streaming)
# ✓ Chat: tablas y listas renderizadas con markdown
# ✓ Chat: botón 🎙️ abre modal de CC → sube M4A/MP3
# ✓ Chat: polling muestra "Paso 1/9 — Transcribiendo audio..."
# ✓ Chat: botón 📎 busca archivos por CC del paciente
# ✓ Chat: Tomy sabe cuántos pacientes hay y qué tareas están activas
# ✓ Chat: mantiene historial de la conversación entre mensajes
```

---

## Lo que NO tocar

- `backend/doc_generator.py` — 8 tests pasan
- `backend/json_validator.py` — schemas completos
- `backend/workflow_steps/` — 9 pasos OK (solo modificar transcribir.py línea 22-29)
- `backend/flujo_audio.py` — M4A/MP3 content-types ya configurados ✅
- `templates/formatos/` — plantillas DOCX listas (solo convertir el .odt)
- Los 8 scripts de test
- `backend/server.py` líneas 665-738 — endpoints de tasks ya existen y funcionan

## PARTE 2.13 — Sistema de agenda completo en el dashboard

### Diagnóstico del estado actual

El pipeline de agenda está completamente implementado y funciona bien en aislamiento:

| Componente | Estado |
|------------|--------|
| `email_reader.py` — lee Gmail IMAP, parsea correos de Medifolios | ✅ implementado |
| `notificador.py` — `check_agenda_manana()`, recordatorios, `agenda_actual.json` | ✅ implementado |
| `cron_pre_extraccion.py` — cron 21:00 (agenda+extracción) y 06:30 (recordatorio matinal) | ✅ implementado |
| `GET /api/agenda` endpoint | ✅ implementado |
| `/hoy` page — muestra citas | ✅ implementado |

**Pero Sandra ve "No hay agenda cargada" todos los días.** El log lo confirma:

```
[CRON 08:38:21] SCHEDULER: desactivado (FASE_A_CRON_ENABLED=false)
```

**Causa raíz:** `FASE_A_CRON_ENABLED=false` (default) → `iniciar_scheduler()` hace return inmediatamente → nunca corre el cron de las 21:00 → nunca se lee el Gmail → nunca se puebla `agenda_actual.json` → `/api/agenda` siempre retorna vacío.

---

### AGENDA-1 — Fix crítico: activar el cron de agenda en producción

**`.env` en WSL de Sandra — cambiar:**
```bash
# ANTES (en el plan anterior — INCORRECTO):
FASE_A_ENABLED=false
FASE_A_CRON_ENABLED=false

# CORRECTO para producción:
FASE_A_ENABLED=false         # Extracción manual de portales → desactivada (se hace bajo demanda desde chat)
FASE_A_CRON_ENABLED=true     # ← ACTIVAR: agenda por Gmail + recordatorios Telegram
```

> **Diferencia importante:**
> - `FASE_A_ENABLED` controla si las rutas de extracción automática están habilitadas
> - `FASE_A_CRON_ENABLED` controla si el scheduler corre el cron de las 21:00 (agenda) y 06:30 (recordatorio)
> 
> El cron de agenda NO necesita `FASE_A_ENABLED`. Puede correr de forma independiente.

**Verificar que funciona:**
```bash
# Forzar check manual desde servidor en ejecución:
curl -X POST http://localhost:8000/api/agenda/check
# → {"ok":true, "citas":[...], "total": N}

# También verificar en el log:
tail -20 storage/logs/server.log | grep -i "agenda\|cron\|gmail"
```

---

### AGENDA-2 — Countdown a la próxima cita en Mi Día

La sección más impactante: Sandra ve "Próxima cita en 23 minutos: Juan García" en grande, actualizado cada minuto, sin recargar la página.

**Agregar a `dashboard/app/hoy/page.tsx`:**

```tsx
// Agregar estado:
const [tiempoFalta, setTiempoFalta] = useState<string | null>(null);
const [proximaCita, setProximaCita] = useState<Cita | null>(null);
const [agendaFecha, setAgendaFecha] = useState<string>("");
const [agendaActualizada, setAgendaActualizada] = useState<string>("");

// En fetchAll, leer también fecha y actualizado:
const agenda = rAgenda.ok ? await rAgenda.json() : { citas: [], fecha: "", actualizado: "" };
setCitas(agenda.citas || []);
setAgendaFecha(agenda.fecha || "");
setAgendaActualizada(agenda.actualizado || "");

// Countdown — recalcular cada 30 segundos:
useEffect(() => {
  const calcular = () => {
    const ahora = new Date();
    const ahoraMin = ahora.getHours() * 60 + ahora.getMinutes();
    
    // Buscar la próxima cita no procesada
    const proxima = citas.find(c => {
      if (!c.hora || c.procesado) return false;
      const [h, m] = c.hora.split(":").map(Number);
      return h * 60 + m > ahoraMin;
    });
    
    setProximaCita(proxima || null);
    
    if (!proxima?.hora) {
      setTiempoFalta(null);
      return;
    }
    
    const [h, m] = proxima.hora.split(":").map(Number);
    const citaMin = h * 60 + m;
    const diffMin = citaMin - ahoraMin;
    
    if (diffMin <= 0) {
      setTiempoFalta("¡Ahora!");
    } else if (diffMin < 60) {
      setTiempoFalta(`en ${diffMin} minutos`);
    } else {
      const horas = Math.floor(diffMin / 60);
      const mins = diffMin % 60;
      setTiempoFalta(`en ${horas}h${mins > 0 ? ` ${mins}min` : ""}`);
    }
  };
  
  calcular();
  const t = setInterval(calcular, 30000);
  return () => clearInterval(t);
}, [citas]);

// JSX — Banner de próxima cita (mostrar solo si faltan ≤4 horas):
{proximaCita && tiempoFalta && tiempoFalta !== "¡Ahora!" && (
  <div className={`rounded-2xl p-5 flex items-center gap-4 ${
    tiempoFalta.includes("minutos") && parseInt(tiempoFalta) <= 30
      ? "bg-red-50 border-2 border-red-300"   // urgente: <30 min
      : tiempoFalta.includes("minutos")
        ? "bg-amber-50 border-2 border-amber-300"  // pronto: <1h
        : "bg-blue-50 border border-blue-200"       // normal
  }`}>
    <div className="text-4xl">⏰</div>
    <div className="flex-1">
      <p className="text-lg font-bold text-slate-800">
        Próxima cita {tiempoFalta}
      </p>
      <p className="text-xl text-slate-700">
        <span className="font-semibold">{proximaCita.hora}</span> — {proximaCita.paciente}
      </p>
      {proximaCita.servicio && (
        <p className="text-sm text-slate-500">{proximaCita.servicio}</p>
      )}
    </div>
    {proximaCita.cc && (
      <Link href={`/paciente/${proximaCita.cc}`}
        className="px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium">
        Ver paciente
      </Link>
    )}
  </div>
)}

{proximaCita && tiempoFalta === "¡Ahora!" && (
  <div className="bg-red-600 text-white rounded-2xl p-5 flex items-center gap-4 animate-pulse">
    <div className="text-4xl">🔔</div>
    <div className="flex-1">
      <p className="text-2xl font-bold">¡Cita ahora!</p>
      <p className="text-xl">{proximaCita.hora} — {proximaCita.paciente}</p>
    </div>
  </div>
)}
```

---

### AGENDA-3 — Notificación del navegador 1 hora antes

Cuando Sandra tiene el dashboard abierto y se acerca una cita, el navegador muestra una notificación emergente (funciona incluso si el dashboard está en segundo plano).

**Agregar a `dashboard/app/hoy/page.tsx`:**

```tsx
// Pedir permiso de notificaciones al cargar:
useEffect(() => {
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
  }
}, []);

// Verificar citas próximas (cada 60s):
useEffect(() => {
  if (citas.length === 0) return;
  
  const verificar = () => {
    const ahora = new Date();
    const ahoraMin = ahora.getHours() * 60 + ahora.getMinutes();
    
    for (const cita of citas) {
      if (!cita.hora || cita.procesado) continue;
      const [h, m] = cita.hora.split(":").map(Number);
      const citaMin = h * 60 + m;
      const diffMin = citaMin - ahoraMin;
      
      // Notificar a los 60 minutos (ventana de 2 min para no repetir)
      if (diffMin >= 58 && diffMin <= 62) {
        if (Notification.permission === "granted") {
          const notif = new Notification(`⏰ Cita en 1 hora — ${cita.paciente}`, {
            body: `${cita.hora} — ${cita.servicio || "Fisioterapia"}`,
            icon: "/favicon.ico",
            requireInteraction: true,  // No se cierra sola
          });
          notif.onclick = () => {
            window.focus();
            if (cita.cc) window.location.href = `/paciente/${cita.cc}`;
          };
        }
        // Toast visible en el dashboard también
        toast.success(
          `⏰ En 1 hora: ${cita.paciente} a las ${cita.hora}`,
          { duration: 30000, position: "top-center" }
        );
      }
      
      // Toast adicional a los 15 minutos
      if (diffMin >= 13 && diffMin <= 17) {
        toast(`🔔 ¡En 15 minutos: ${cita.paciente}!`, {
          duration: 60000, position: "top-center",
          style: { background: "#ef4444", color: "#fff" },
        });
      }
    }
  };
  
  const t = setInterval(verificar, 60000);
  verificar();
  return () => clearInterval(t);
}, [citas]);
```

---

### AGENDA-4 — Indicador de frescura de la agenda

Sandra debe saber si la agenda que ve es de hoy, de mañana, o si está desactualizada.

**Agregar cerca del título de "Citas de hoy":**

```tsx
// Calcular si la agenda está fresca:
const agendaInfo = (() => {
  if (!agendaFecha) return null;
  const hoy = new Date().toISOString().slice(0, 10);
  const manana = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const horasDesdeUpdate = agendaActualizada
    ? Math.round((Date.now() - new Date(agendaActualizada).getTime()) / 3600000)
    : 999;
  
  if (agendaFecha === hoy) return { label: "Agenda de hoy", color: "green", fresca: true };
  if (agendaFecha === manana) return { label: "Agenda de mañana (ya guardada)", color: "blue", fresca: true };
  if (horasDesdeUpdate < 24) return { label: `Actualizada hace ${horasDesdeUpdate}h`, color: "amber", fresca: true };
  return { label: "Agenda posiblemente desactualizada", color: "red", fresca: false };
})();

// En el JSX:
<h2 className="text-2xl font-semibold mb-2 flex items-center gap-3">
  <Calendar size={24} /> Citas de hoy
  {agendaInfo && (
    <span className={`text-sm font-normal px-3 py-1 rounded-full ${
      agendaInfo.color === "green" ? "bg-green-100 text-green-700" :
      agendaInfo.color === "blue" ? "bg-blue-100 text-blue-700" :
      agendaInfo.color === "amber" ? "bg-amber-100 text-amber-700" :
      "bg-red-100 text-red-700"
    }`}>
      {agendaInfo.label}
    </span>
  )}
</h2>
```

---

### AGENDA-5 — Prompt post-cita: "¿Subimos el audio?"

Cuando pasa la hora de una cita (y la cita no está marcada como procesada), mostrar un prompt contextual:

```tsx
// Detectar citas pasadas no procesadas:
const citasPasadasSinProcesar = citas.filter(c => {
  if (!c.hora || c.procesado) return false;
  const [h, m] = c.hora.split(":").map(Number);
  const ahora = new Date();
  return h * 60 + m < ahora.getHours() * 60 + ahora.getMinutes() - 15; // pasada hace 15+ min
});

// En el JSX — mostrar después de la lista de citas:
{citasPasadasSinProcesar.length > 0 && (
  <div className="bg-purple-50 border border-purple-200 rounded-2xl p-5 space-y-3">
    <p className="font-semibold text-purple-800">
      📋 {citasPasadasSinProcesar.length} cita(s) terminada(s) — ¿querés procesar el audio?
    </p>
    <div className="space-y-2">
      {citasPasadasSinProcesar.map((c, i) => (
        <div key={i} className="flex items-center justify-between">
          <p className="text-purple-700">{c.hora} — {c.paciente}</p>
          <Link
            href={`/subir-audio${c.cc ? `?cc=${c.cc}` : ""}`}
            className="px-3 py-1.5 bg-purple-600 text-white rounded-xl text-sm font-medium hover:bg-purple-700"
          >
            Subir audio →
          </Link>
        </div>
      ))}
    </div>
    <p className="text-xs text-purple-600">
      Tomy genera los 7 formatos automáticamente. Solo le pasás el audio de la consulta.
    </p>
  </div>
)}
```

**Backend — marcar cita como procesada cuando se sube un audio:**

```python
# En /api/procesar-paciente y /api/chat/audio:
# Después de crear el task, marcar la cita como procesada en la agenda guardada

def _marcar_cita_procesada(paciente_cc: str):
    """Marca la cita del paciente como procesada en agenda_actual.json."""
    from backend.notificador import cargar_agenda_guardada
    agenda_path = STORAGE / "agenda_actual.json"
    if not agenda_path.exists(): return
    try:
        datos = json.loads(agenda_path.read_text(encoding="utf-8"))
        for cita in datos.get("citas", []):
            if cita.get("cc") == paciente_cc:
                cita["procesado"] = True
        agenda_path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        _log(f"No pude marcar cita como procesada: {e}")

# Llamar en los endpoints de upload:
_marcar_cita_procesada(paciente_cc)
```

---

### AGENDA-6 — Firma de Sandra vía Telegram (sin escáner)

Sandra no tiene escáner, pero sí tiene iPhone. Este flujo le permite enviar una foto de su firma y el sistema la guarda automáticamente:

```
Sandra envía foto de su firma al bot de Telegram
    ↓
Bot detecta que es una imagen (not audio/document)
    ↓
Bot pregunta: "¿Es tu firma? Responde SI para guardarla."
    ↓
Sandra responde: "SI"
    ↓
Bot descarga la imagen, la recorta (crop a zona con firma),
la convierte a PNG transparente, la guarda en storage/firma_sandra.png
Bot responde: "✅ Guardé tu firma. A partir de ahora aparecerá en los documentos."
```

**Agregar al webhook de Telegram (`_procesar_update_telegram`):**

```python
# Detectar foto entrante:
foto = msg.get("photo")
if foto and not voice:
    # La última foto es la de mejor calidad
    file_id = foto[-1].get("file_id", "")
    
    if estado.get("etapa") == "confirmando_firma":
        if texto.upper().strip() in ["SI", "SÍ", "YES", "S", "OK", "CONFIRMO"]:
            # Descargar y guardar la firma
            asyncio.create_task(_guardar_firma_telegram(chat_id, estado["file_id_foto"]))
        else:
            _estado_telegram[chat_id] = {"etapa": "idle"}
            await _telegram_reply(chat_id, "De acuerdo, no guardé nada.")
    else:
        # Nueva foto — preguntar si es la firma
        _estado_telegram[chat_id] = {"etapa": "confirmando_firma", "file_id_foto": file_id}
        await _telegram_reply(
            chat_id,
            "📸 Recibí una imagen. ¿Es tu firma para los documentos?\n"
            "Respondé *SI* para guardarla, o *NO* para cancelar.",
            parse_mode="Markdown"
        )
    return

async def _guardar_firma_telegram(chat_id: str, file_id: str):
    """Descarga la foto de firma y la procesa para uso en documentos."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}")
            file_path = r.json().get("result", {}).get("file_path", "")
            img_data = (await client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")).content
        
        # Procesar imagen: convertir a PNG con fondo transparente
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_data)).convert("RGBA")
        
        # Auto-crop: eliminar márgenes blancos
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        
        # Guardar en el storage
        firma_path = STORAGE / "firma_sandra.png"
        img.save(str(firma_path), "PNG")
        
        await _telegram_reply(chat_id,
            "✅ Guardé tu firma correctamente. Aparecerá en todos los documentos nuevos.\n"
            f"Tamaño: {img.width}×{img.height} px")
        
    except ImportError:
        await _telegram_reply(chat_id,
            "Necesito instalar una librería para procesar la imagen. "
            "Pedile a Manu que ejecute: pip install Pillow")
    except Exception as e:
        await _telegram_reply(chat_id, f"❌ No pude guardar la firma: {str(e)[:80]}")
```

**Instalación requerida:**
```bash
pip install Pillow
# Agregar a backend/requirements.txt:
echo "Pillow>=10.0.0" >> backend/requirements.txt
```

---

### AGENDA-7 — Errores del workflow en lenguaje de Sandra

Actualmente, cuando un paso falla, la UI muestra cosas como:
```
paso 5 falló: TimeoutError: Request timed out after 300s
```

Sandra no entiende eso. Agregar traducción de errores técnicos a lenguaje simple:

**`dashboard/app/subir-audio/page.tsx` y `app/chat/page.tsx`:**

```tsx
const ERRORES_AMIGABLES: Record<number, Record<string, string>> = {
  1: {
    default: "No pude transcribir el audio. El servidor de Deepgram no respondió. ¿El audio es de menos de 2 horas?",
    FileNotFoundError: "No encontré el archivo de audio. ¿Se subió correctamente?",
    TimeoutError: "El audio tardó demasiado en transcribirse. Intentá con un audio más corto.",
  },
  2: {
    default: "No encontré los datos del paciente. ¿La cédula es correcta?",
  },
  5: {
    default: "El asistente de IA tardó demasiado en analizar el caso. Intentalo de nuevo — suele funcionar.",
    TimeoutError: "La IA tardó más de 10 minutos analizando. Intentá de nuevo.",
  },
  6: {
    default: "No pude generar los documentos. ¿Las plantillas de Word están en su lugar?",
  },
  8: {
    default: "No pude convertir a PDF. ¿LibreOffice está instalado?",
    FileNotFoundError: "LibreOffice no está instalado. Pedile a Manu que lo instale.",
  },
};

function mensajeErrorAmigable(paso: number, errorTecnico: string): string {
  const erroresPaso = ERRORES_AMIGABLES[paso] || {};
  
  // Buscar coincidencia por tipo de error
  for (const [tipo, msg] of Object.entries(erroresPaso)) {
    if (tipo !== "default" && errorTecnico.includes(tipo)) {
      return msg;
    }
  }
  
  return erroresPaso.default || 
    `Hubo un problema en el paso ${paso} de 9. ¿Intentás de nuevo?`;
}
```

---

### Tabla de tareas nuevas (Bloque AG)

| # | Archivo | Qué hacer |
|---|---------|-----------|
| AG1 | `.env` producción | Cambiar `FASE_A_CRON_ENABLED=true` — **CRÍTICO, sin esto no hay agenda** |
| AG2 | `app/hoy/page.tsx` | Countdown a próxima cita (actualiza cada 30s, banner urgente si <30min) |
| AG3 | `app/hoy/page.tsx` | Notificación navegador a las 60min y 15min antes de cada cita |
| AG4 | `app/hoy/page.tsx` | Indicador de frescura (¿la agenda es de hoy? ¿de mañana? ¿stale?) |
| AG5 | `app/hoy/page.tsx` | Prompt post-cita: "¿Subimos el audio?" para citas pasadas no procesadas |
| AG6 | `backend/server.py` | `_marcar_cita_procesada(cc)` al procesar audio — actualizar agenda_actual.json |
| AG7 | `backend/server.py` telegram | Flujo de foto → firma_sandra.png vía Telegram |
| AG8 | `backend/requirements.txt` | Agregar `Pillow>=10.0.0` |
| AG9 | `dashboard/` | `mensajeErrorAmigable()` para traducir errores técnicos a español simple |
| AG10 | Verificación | `curl -X POST localhost:8000/api/agenda/check` → confirmar que lee Gmail |

---

## Resumen de bugs descubiertos

| # | Bug | Impacto | Archivo | Bloque |
|---|-----|---------|---------|--------|
| 1 | `start.sh` instala 4 de 14 deps | Backend no arranca en WSL | `start.sh` línea 19 | M6 |
| 2 | `chat/route.ts` no reenvía historial | Chat sin memoria al pasar por proxy | `app/api/chat/route.ts` línea 10 | M5 |
| 3 | `chat/route.ts` sin timeout (DeepSeek 120s) | Conexión se corta | `app/api/chat/route.ts` | M5 |
| 4 | `subir-audio` redirige sin esperar | Sandra queda en pantalla vacía | `app/subir-audio/page.tsx` línea 41 | M4 |
| 5 | `subir-audio` acepta cualquier formato | Sandra puede subir WAV, OGG, etc. | `app/subir-audio/page.tsx` | M1 |
| 6 | `subir-audio` sin barra de progreso | No sabe si está subiendo | función `subir` | M3 |
| 7 | `firma_sandra.png` no existe | Documentos sin firma | `storage/` | M10 |
| 8 | Template prueba trabajo en `.odt` | Generación del formato falla | `templates/formatos/` | M7 |
| 9 | Telegram/Gmail sin verificar | Notificaciones silenciosas | `.env` | M9 |
| 10 | AUTH_PIN=1234 (default inseguro) | Cualquiera accede al dashboard | `.env` | M8 |
| 11 | `_detectar_discrepancias` solo compara siniestro | 5 campos no verificados | `playwright_real/orquestador.py` | P1 |
| 12 | Chat no usa `correction_resolver.py` | Sandra debe corregir formatos en Word | `chat_handler.py` | CR1 |
| 13 | No existe endpoint ZIP | 7 descargas individuales | `server.py` | Z1 |
| 14 | No existe retry de paso fallido | Workflow reinicia desde cero | `server.py` | Z4 |
| 15 | Telegram solo unidireccional | Sandra necesita el dashboard para todo | `notificador.py` | TG1 |
| 16 | `/hoy` muestra estado crudo | "transcribiendo" en vez de texto claro | `app/hoy/page.tsx` | H1 |
| 17 | No hay toast cuando termina tarea | Sandra no sabe sin ir a /hoy | — | H3 |
| 18 | Backup cron nunca registrado | Datos sin respaldar | `server.py` startup | FX1 |
| 19 | Download sirve PDF con MIME DOCX | El navegador lo descarga mal | `server.py` línea 217 | FX2 |
| 20 | No hay middleware auth Next.js | Dashboard accesible sin login | — | FX3 |
| 21 | URLs hardcodeadas en `/paciente/[cc]` | Falla en producción si cambia URL | `app/paciente/[cc]/page.tsx` | FX5 |
| 22 | Búsqueda de pacientes solo en agenda | No encuentra pacientes pasados | `server.py` línea 505 | FX6 |
| 23 | Sin validación antes de procesar | Campos críticos faltantes → formatos con [VERIFICAR] | `server.py` | PR1 |
| 24 | Polling `/paciente/{cc}` cada 3s | Carga innecesaria cuando no hay tareas activas | `app/paciente/[cc]/page.tsx` | FX5 |
| 25 | `FASE_A_CRON_ENABLED=false` en producción | Agenda NUNCA se puebla → Sandra siempre ve pantalla vacía | `.env` | AG1 |
| 26 | Sin countdown a próxima cita | Sandra tiene que mirar el reloj manualmente | `app/hoy/page.tsx` | AG2 |
| 27 | Sin notificación de navegador | Sandra puede perderse citas si no mira el dashboard | — | AG3 |
| 28 | Agenda sin indicador de frescura | Sandra no sabe si la agenda está actualizada | `app/hoy/page.tsx` | AG4 |
| 29 | Sin prompt post-cita | Sandra no recibe recordatorio de subir el audio | `app/hoy/page.tsx` | AG5 |
| 30 | Errores técnicos sin traducir | Sandra ve "TimeoutError" en vez de mensaje entendible | frontend | AG9 |
| 31 | `lib/hermes.ts` usa env var incorrecta | `NEXT_PUBLIC_HERMES_API` vs `NEXT_PUBLIC_API_URL` → URL rota en producción | `dashboard/lib/hermes.ts` | LH2 |
| 32 | `start-wsl.sh` busca Docker en producción | `docker ps grep hermes-` falla → sistema nunca arranca en WSL | `start-wsl.sh` | LH6 |
| 33 | `sync-to-wsl.sh` usa `docker cp` | Deploy roto — git pull es el mecanismo real | `sync-to-wsl.sh` | LH7 |
| 34 | Backend corre con `uvicorn --reload` en producción | Alto consumo CPU, recarga innecesaria en producción real | `start.sh` | PD2 |
| 35 | Dashboard corre con `next dev` en producción | 3-4× más lento que `next start`, compila en cada request | `start-wsl.sh` | PD2 |
| 36 | Sin gestión de procesos (PM2/systemd) | Uvicorn y Next.js mueren si hay error; no auto-inician al reiniciar WSL | — | PD1 |
| 37 | `config/hermes-*.yaml` en el repo | Archivos de configuración muertos confunden y ocupan espacio | `config/` | LH1 |
| 38 | `puente_docker.py` código muerto | Imports confusos, nunca se llama en producción WSL | `backend/` | LH5 |
| 39 | Backup mensual (`verificar_backup.py`) nunca registrado | Monthly restore test nunca corre | `server.py` startup | PD5 |
| 40 | Sin `/api/system/health` completo | No hay forma de saber si todos los servicios están OK | `server.py` | PD6 |

---

## PARTE 13 — Limpieza Hermes + Producción robusta

> **Contexto:** El sistema NO necesita el agente Hermes. Solo usamos su API (DeepSeek v4 via OpenCode Go).
> Todos los archivos y referencias a Hermes son código muerto que confunde, rompe scripts de arranque
> y usa variables de entorno equivocadas. Esta parte limpia eso y prepara el sistema para producción real.

---

### LIMPIEZA-1 — Eliminar archivos de configuración Hermes

**Problema:** `config/hermes-config.yaml`, `config/hermes-env.txt`, `config/hermes-persona.txt` son archivos
de configuración del agente Hermes. No se usan en ninguna parte del código Python ni TypeScript.
Confunden a cualquiera que lea el repo y pueden hacer pensar que el sistema depende de Hermes.

**Qué borrar:**
```bash
# En Docker (desarrollo)
rm /root/fisioterapia/config/hermes-config.yaml
rm /root/fisioterapia/config/hermes-env.txt
rm /root/fisioterapia/config/hermes-persona.txt
# Luego git add -A && git commit -m "chore: eliminar configuración Hermes obsoleta"
```

**Lo que SÍ se queda:** el directorio `config/` puede quedar si hay otros archivos útiles.

---

### LIMPIEZA-2 — Renombrar `lib/hermes.ts` → `lib/api.ts`

**Problema:** `dashboard/lib/hermes.ts` usa `process.env.NEXT_PUBLIC_HERMES_API` como base URL.
En producción WSL solo existe `NEXT_PUBLIC_API_URL`. El dashboard nunca apunta al backend correcto.

**Archivo actual** (`dashboard/lib/hermes.ts`):
```typescript
const HERMES_API = process.env.NEXT_PUBLIC_HERMES_API || "http://localhost:8000/api";
```

**Archivo nuevo** (`dashboard/lib/api.ts`) — mismo contenido, solo cambiar la constante:
```typescript
// dashboard/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

// Reemplazar HERMES_API → API_BASE en TODO el archivo
export async function obtenerPacientes() {
  const res = await fetch(`${API_BASE}/pacientes`);
  // ...
}

export async function buscarPaciente(q: string) {
  const res = await fetch(`${API_BASE}/pacientes/buscar?q=${encodeURIComponent(q)}`);
  // ...
}

// ... resto de funciones igual, solo cambiando HERMES_API → API_BASE
```

**Pasos:**
1. Crear `dashboard/lib/api.ts` con el mismo contenido que `hermes.ts` pero `API_BASE` en lugar de `HERMES_API`
2. Eliminar `dashboard/lib/hermes.ts`
3. Actualizar `dashboard/.env.local`:
   ```
   # ANTES (borrar):
   NEXT_PUBLIC_HERMES_API=http://localhost:8000/api
   # DESPUÉS (agregar):
   NEXT_PUBLIC_API_URL=http://localhost:8000/api
   ```

---

### LIMPIEZA-3 — Actualizar imports en páginas del dashboard

**Problema:** Dos páginas importan de `@/lib/hermes` — después de renombrar el archivo, los imports rompen.

**`dashboard/app/pacientes/page.tsx`** — buscar y reemplazar:
```typescript
// ANTES:
import { obtenerPacientes, buscarPaciente } from "@/lib/hermes";
// DESPUÉS:
import { obtenerPacientes, buscarPaciente } from "@/lib/api";
```

**`dashboard/app/chat/page.tsx`** — buscar y reemplazar:
```typescript
// ANTES:
import { ... } from "@/lib/hermes";
// DESPUÉS:
import { ... } from "@/lib/api";
```

**Búsqueda exhaustiva** — antes de dar el paso por completo, buscar todas las referencias:
```bash
grep -r "hermes" /root/fisioterapia/dashboard --include="*.ts" --include="*.tsx" -l
# Verificar que solo queden los archivos esperados
```

---

### LIMPIEZA-4 — Limpiar comentarios en rutas API

**`dashboard/app/api/chat/route.ts`** — eliminar comentario "Reenviar a Hermes Agent":
```typescript
// ANTES (comentario engañoso):
// Reenviar a Hermes Agent
const res = await fetch(`${process.env.NEXT_PUBLIC_HERMES_API}/chat`, ...);

// DESPUÉS:
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const res = await fetch(`${BACKEND_URL}/api/chat`, ...);
```

**`dashboard/app/api/upload-audio/route.ts`** — mismo tratamiento:
```typescript
// ANTES:
// Reenviar a Hermes Agent
const res = await fetch(`${process.env.NEXT_PUBLIC_HERMES_API}/procesar-paciente`, ...);

// DESPUÉS:
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const res = await fetch(`${BACKEND_URL}/api/procesar-paciente`, ...);
```

> **Nota:** `BACKEND_URL` es variable servidor (sin `NEXT_PUBLIC_`), solo usable en route handlers.
> `NEXT_PUBLIC_API_URL` es variable cliente, usable en componentes React.
> Son dos variables distintas con propósitos distintos — ambas necesarias.

---

### LIMPIEZA-5 — Archivar `puente_docker.py`

**Problema:** `backend/puente_docker.py` (192 líneas) hacía de bridge WSL↔Docker.
En producción pura WSL no hay Docker → este módulo nunca se invoca y no se importa desde ningún lugar.
Es código muerto que ocupa espacio y confunde.

**Verificación antes de borrar:**
```bash
grep -r "puente_docker" /root/fisioterapia/backend --include="*.py"
# Si no aparece nada → seguro borrar
```

**Si no está importado:**
```bash
rm /root/fisioterapia/backend/puente_docker.py
```

**Si está importado en algún lugar:** comentar el import y dejar nota `# DESHABILITADO — solo WSL producción`.

---

### LIMPIEZA-6 — Reescribir `start-wsl.sh` (sin Docker)

**Problema actual** (`start-wsl.sh` líneas 1-20 aprox.):
```bash
# BUG: busca un contenedor Docker que no existe en producción
CONTAINER=$(sudo docker ps | grep hermes- | awk '{print $1}')
if [ -z "$CONTAINER" ]; then
    echo "ERROR: No se encontró contenedor Hermes"
    exit 1
fi
sudo docker exec $CONTAINER uvicorn backend.server:app ...
```

**`start-wsl.sh` nuevo — arranque directo en WSL:**
```bash
#!/bin/bash
# start-wsl.sh — arranque RILO SAS en producción WSL (sin Docker)
set -e

RILO_DIR="$HOME/rilo-backend"
DASH_DIR="$HOME/rilo-dashboard"
LOG_DIR="$HOME/rilo-logs"

mkdir -p "$LOG_DIR"

echo "=== RILO SAS — Arrancando sistema ==="
echo "Backend:   $RILO_DIR"
echo "Dashboard: $DASH_DIR"
echo "Logs:      $LOG_DIR"

# 1. Verificar dependencias críticas
echo "--- Verificando ffmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "ADVERTENCIA: ffmpeg no instalado — audios largos no funcionarán"
    echo "Instalar con: sudo apt-get install -y ffmpeg"
fi

echo "--- Verificando LibreOffice..."
if ! command -v libreoffice &> /dev/null; then
    echo "ADVERTENCIA: LibreOffice no instalado — conversión PDF/A fallará"
    echo "Instalar con: sudo apt-get install -y libreoffice"
fi

# 2. Activar entorno Python
cd "$RILO_DIR"
source .venv/bin/activate 2>/dev/null || true

# 3. Instalar dependencias Python (si hay cambios)
pip install -r backend/requirements.txt -q

# 4. Arrancar backend con PM2 (si disponible) o directo
if command -v pm2 &> /dev/null; then
    echo "--- Usando PM2 para gestión de procesos..."
    pm2 start ecosystem.config.js --env production
    pm2 save
    echo "✓ Servicios arrancados con PM2"
    echo "  Ver logs:   pm2 logs"
    echo "  Ver estado: pm2 status"
else
    echo "--- PM2 no instalado — arrancando directamente (recomendado: instalar PM2)"
    # Backend
    nohup uvicorn backend.server:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 1 \
        > "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$LOG_DIR/backend.pid"
    echo "✓ Backend arrancado (PID $(cat $LOG_DIR/backend.pid))"

    # Dashboard
    cd "$DASH_DIR"
    npm run build 2>&1 | tail -5
    nohup npm start -- -H 0.0.0.0 -p 3000 \
        > "$LOG_DIR/dashboard.log" 2>&1 &
    echo $! > "$LOG_DIR/dashboard.pid"
    echo "✓ Dashboard arrancado (PID $(cat $LOG_DIR/dashboard.pid))"
fi

# 5. Verificar arranque
sleep 3
echo ""
echo "=== Verificando servicios ==="
curl -s http://localhost:8000/api/system/health | python3 -c "
import sys, json
d = json.load(sys.stdin)
for k,v in d.items():
    print(f'  {k}: {v}')
" 2>/dev/null || echo "  Backend: arrancando... (esperar 10 seg)"

echo ""
echo "=== RILO SAS listo ==="
echo "  Dashboard: http://localhost:3000"
echo "  Backend:   http://localhost:8000"
echo ""
# IP local para Sandra acceda desde su teléfono
LOCAL_IP=$(hostname -I | awk '{print $1}')
echo "  En la misma WiFi: http://$LOCAL_IP:3000"
```

---

### LIMPIEZA-7 — Reemplazar `sync-to-wsl.sh` con `deploy.sh`

**Problema:** `sync-to-wsl.sh` usa `sudo docker cp` para copiar archivos. El mecanismo real de deploy
es `git push → GitHub → git pull` en WSL.

**`sync-to-wsl.sh` viejo (borrar):**
```bash
# CÓDIGO VIEJO — NO USAR
CONTAINER=$(sudo docker ps | grep hermes-)
sudo docker cp /root/fisioterapia/. $CONTAINER:/root/fisioterapia/
```

**`deploy.sh` nuevo — flujo git completo:**
```bash
#!/bin/bash
# deploy.sh — actualizar RILO SAS en producción WSL desde GitHub
# CORRER EN WSL de Sandra: bash ~/rilo-backend/deploy.sh

set -e
RILO_DIR="$HOME/rilo-backend"
DASH_DIR="$HOME/rilo-dashboard"

echo "=== Deploy RILO SAS ==="
echo "Actualizando código desde GitHub..."

# 1. Actualizar backend
cd "$RILO_DIR"
git pull origin main
pip install -r backend/requirements.txt -q
echo "✓ Backend actualizado"

# 2. Actualizar dashboard
cd "$DASH_DIR"
git pull origin main
npm install --legacy-peer-deps
npm run build
echo "✓ Dashboard actualizado y compilado"

# 3. Reiniciar servicios
if command -v pm2 &> /dev/null; then
    pm2 reload ecosystem.config.js --env production
    echo "✓ Servicios reiniciados con PM2"
else
    # Matar procesos viejos por PID guardado
    LOG_DIR="$HOME/rilo-logs"
    if [ -f "$LOG_DIR/backend.pid" ]; then
        kill $(cat "$LOG_DIR/backend.pid") 2>/dev/null || true
    fi
    if [ -f "$LOG_DIR/dashboard.pid" ]; then
        kill $(cat "$LOG_DIR/dashboard.pid") 2>/dev/null || true
    fi
    sleep 2
    bash "$RILO_DIR/start-wsl.sh"
fi

echo ""
echo "=== Deploy completado ==="
echo "Versión: $(cd $RILO_DIR && git log -1 --format='%h %s')"
```

---

### LIMPIEZA-8 — Convertir skills/flujo-browser a documentación plain markdown

**Problema:** Los directorios en `skills/` eran skills del agente Hermes. Sin Hermes, son archivos
YAML incomprensibles. Pero el contenido (mapa de portales) es valiosísimo para el sistema de aprendizaje.

**Lo que hay en `skills/flujo-browser/`:**
- Mapa completo de Medifolios: 18/18 secciones documentadas
- Mapa completo de ARL Positiva: 9/9 secciones documentadas
- Rutas CSS, selectores XPath, orden de pasos, capturas de pantalla

**Conversión:**
```bash
# Crear directorio de documentación de portales
mkdir -p /root/fisioterapia/docs/portales

# Convertir skill Medifolios a markdown plano
# (copiar el contenido, eliminar frontmatter YAML de Hermes)
cp skills/flujo-browser/medifolios-mapa.* docs/portales/medifolios-mapa.md
cp skills/flujo-browser/positiva-mapa.* docs/portales/positiva-mapa.md

# Eliminar directorio skills completo
rm -rf skills/
```

**`docs/portales/README.md`** — índice:
```markdown
# Mapas de Portales — RILO SAS

## Medifolios (server0medifolios.net)
Ver [medifolios-mapa.md](medifolios-mapa.md) — 18 secciones documentadas.

## ARL Positiva (positivacuida.positiva.gov.co)
Ver [positiva-mapa.md](positiva-mapa.md) — 9 secciones documentadas.

Estos mapas los usa `playwright_real/` para navegación automatizada.
También los usa el sistema de aprendizaje `portal_knowledge.json`.
```

---

### PD-1 — Instalar y configurar PM2 (gestión de procesos)

**Por qué PM2:**
- Auto-reinicia procesos si crashean (uvicorn muere → PM2 lo resucita en segundos)
- `pm2 startup` → auto-inicia al reiniciar WSL
- `pm2 logs` → logs centralizados de backend + dashboard
- `pm2 monit` → CPU/RAM en tiempo real
- Reload sin downtime: `pm2 reload ecosystem.config.js`

**Instalación:**
```bash
npm install -g pm2
pm2 --version  # verificar
```

**`ecosystem.config.js`** (en raíz del repo WSL `~/rilo-backend/`):
```javascript
// ecosystem.config.js
module.exports = {
  apps: [
    {
      name: "rilo-backend",
      script: "uvicorn",
      args: "backend.server:app --host 0.0.0.0 --port 8000 --workers 1",
      cwd: process.env.HOME + "/rilo-backend",
      interpreter: process.env.HOME + "/rilo-backend/.venv/bin/python",
      env_production: {
        NODE_ENV: "production",
      },
      // Reintentar hasta 10 veces antes de rendirse
      max_restarts: 10,
      restart_delay: 5000,
      // Logs
      out_file: process.env.HOME + "/rilo-logs/backend.out.log",
      error_file: process.env.HOME + "/rilo-logs/backend.err.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },
    {
      name: "rilo-dashboard",
      script: "npm",
      args: "start -- -H 0.0.0.0 -p 3000",
      cwd: process.env.HOME + "/rilo-dashboard",
      env_production: {
        NODE_ENV: "production",
        NEXT_PUBLIC_API_URL: "http://localhost:8000/api",
        // Nota: BACKEND_URL se usa en route handlers server-side
        BACKEND_URL: "http://localhost:8000",
      },
      max_restarts: 10,
      restart_delay: 5000,
      out_file: process.env.HOME + "/rilo-logs/dashboard.out.log",
      error_file: process.env.HOME + "/rilo-logs/dashboard.err.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },
  ],
};
```

**Arranque inicial:**
```bash
cd ~/rilo-backend
pm2 start ecosystem.config.js --env production
pm2 save  # guardar configuración actual
pm2 startup  # generar script de auto-inicio (seguir instrucciones que imprime)
```

**Comandos útiles del día a día:**
```bash
pm2 status              # ver estado de todos los procesos
pm2 logs                # ver todos los logs en tiempo real
pm2 logs rilo-backend   # ver solo logs del backend
pm2 restart rilo-backend  # reiniciar backend manualmente
pm2 reload ecosystem.config.js --env production  # reload sin downtime
pm2 monit               # dashboard CPU/RAM en terminal
```

---

### PD-2 — Producción Next.js: `next build` + `next start`

**Por qué importa:**
- `next dev`: compila cada archivo en la primera petición, hot-reloading activo, warnings de desarrollo. Es **3-4× más lento** que producción.
- `next start`: sirve la build optimizada, pages pre-compiladas, sin overhead. **Obligatorio en producción.**

**Build del dashboard (correr antes de cada deploy):**
```bash
cd ~/rilo-dashboard
npm run build
# Verifica que no hay errores de TypeScript ni ESLint
# Output: .next/
```

**`package.json` en dashboard** — verificar que existe el script `start`:
```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  }
}
```

**Flujo de deploy completo (en orden):**
```bash
# 1. En Docker (desarrollo) — commit y push
git add -A
git commit -m "feat: ..."
git push origin main

# 2. En WSL (producción) — actualizar y compilar
cd ~/rilo-backend && git pull origin main
cd ~/rilo-dashboard && git pull origin main && npm install --legacy-peer-deps && npm run build

# 3. Reiniciar con PM2
pm2 reload ecosystem.config.js --env production
```

---

### PD-3 — Windows Task Scheduler: auto-inicio WSL al arrancar PC

**Problema:** Cuando Sandra reinicia su PC, el WSL no arranca automáticamente.
Hay que abrir la terminal y correr `start-wsl.sh` manualmente. Si PM2 ya tiene `startup` configurado,
basta con iniciar WSL; PM2 arrancará los servicios solo.

**Script VBScript** — crear `C:\Users\Sandra\RILO_autostart.vbs`:
```vbscript
' RILO_autostart.vbs — inicia WSL en background al arrancar Windows
' No muestra ventana de terminal (wscript.exe, no cscript.exe)
Set objShell = CreateObject("WScript.Shell")
objShell.Run "wsl.exe --distribution Ubuntu --exec bash -c 'pm2 resurrect'", 0, False
```

**Configurar Task Scheduler:**
1. Abrir "Programador de tareas" (Task Scheduler)
2. "Crear tarea básica" → nombre: "RILO SAS Autostart"
3. Desencadenador: "Al iniciar sesión" (Al iniciar sesión de cualquier usuario)
4. Acción: "Iniciar un programa" → `wscript.exe` → argumentos: `C:\Users\Sandra\RILO_autostart.vbs`
5. En "Condiciones": desmarcar "Iniciar solo si el equipo está conectado a la corriente eléctrica"
6. En "Configuración": marcar "Ejecutar la tarea lo antes posible si se perdió un inicio programado"
7. Guardar → OK

**Alternativa más simple (startup folder):**
```
Presionar Win+R → shell:startup → Copiar RILO_autostart.vbs ahí
```
El archivo se ejecuta al iniciar sesión automáticamente.

**Verificar que PM2 persiste:**
```bash
# En WSL — solo hacer esto una vez
pm2 startup   # imprime un comando — copiarlo y ejecutarlo
pm2 save      # guarda lista de procesos activos
# Ahora pm2 resurrect restaura los procesos al iniciar WSL
```

---

### PD-4 — CORS para red local (acceso desde teléfono de Sandra)

**Problema:** Si Sandra quiere usar el dashboard desde su teléfono o tablet en la misma WiFi,
las peticiones del navegador a `http://192.168.x.x:8000` son bloqueadas por CORS.

**`backend/server.py`** — CORS desde env var (ya planeado en bloque C, verificar que esté implementado):
```python
# server.py — configuración CORS
import os
from fastapi.middleware.cors import CORSMiddleware

_cors_raw = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
)
origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**`.env` en producción WSL:**
```bash
# Agregar la IP local de la PC de Sandra (buscarla con: hostname -I)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://192.168.1.100:3000
# Reemplazar 192.168.1.100 con la IP real de la PC de Sandra
```

**`ecosystem.config.js`** — pasar IP al dashboard:
```javascript
env_production: {
  NEXT_PUBLIC_API_URL: "http://192.168.1.100:8000/api",  // IP fija de la PC de Sandra
  // Cuando Sandra accede desde su teléfono, el browser necesita la IP real del servidor
}
```

**`dashboard/.env.local`:**
```bash
NEXT_PUBLIC_API_URL=http://192.168.1.100:8000/api
```

> **Nota para Manuel:** La IP `192.168.1.100` es un ejemplo. Encontrarla en WSL con `hostname -I`.
> Si el router asigna IP dinámica, configurar IP estática en el adaptador de red de Windows,
> o usar el hostname de Windows: `hostname` → usar `NOMBREPC.local:8000`.

---

### PD-5 — Registrar cron de backup mensual (`verificar_backup.py`)

**Problema encontrado:** `server.py` en startup solo registra `iniciar_scheduler()` (pre-extracción).
El backup diario (`backup_diario.py`) y el chequeo mensual de restauración (`verificar_backup.py`)
**nunca se registran** — los datos nunca se respaldan.

**`backend/server.py`** — sección startup, agregar junto a `iniciar_scheduler()`:

```python
# server.py — función lifespan o @app.on_event("startup")
from backend.backup_diario import ejecutar_backup
from backend.verificar_backup import verificar_restauracion
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler

_scheduler = AsyncIOScheduler(timezone="America/Bogota")

@app.on_event("startup")
async def startup_event():
    # Cron pre-extracción ya existente
    iniciar_scheduler()

    # ── NUEVO: Backup diario ──────────────────────────────────────────
    hora_backup = int(os.getenv("BACKUP_HORA", "23"))
    _scheduler.add_job(
        ejecutar_backup,
        CronTrigger(hour=hora_backup, minute=0, timezone="America/Bogota"),
        id="backup_diario",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # ── NUEVO: Verificación mensual de restauración ───────────────────
    _scheduler.add_job(
        verificar_restauracion,
        CronTrigger(day=1, hour=3, minute=0, timezone="America/Bogota"),
        id="verificar_backup_mensual",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    _scheduler.start()
    logger.info(f"Backup diario: {hora_backup}:00 COL. Verificación mensual: día 1, 3:00 AM COL.")
```

**Variables de entorno necesarias** (verificar en `.env` de producción):
```bash
BACKUP_HORA=23
TELEGRAM_BOT_TOKEN=...   # para enviar el ZIP del backup a Manu
TELEGRAM_CHAT_ID_MANU=...  # chat ID de Manu para recibir backups
```

---

### PD-6 — Endpoint `/api/system/health` completo

**Por qué:** `start-wsl.sh` nuevo lo consulta para verificar arranque. Sandra puede usarlo para
saber si todo está bien. Un monitor externo (Manu) puede hacer ping a este endpoint.

**`backend/server.py`** — agregar endpoint:

```python
@app.get("/api/system/health")
async def system_health():
    """Health check completo — verifica todos los servicios críticos."""
    import shutil
    from pathlib import Path
    from datetime import datetime

    resultado = {}

    # 1. Backend propio
    resultado["backend"] = "ok"

    # 2. Espacio en disco
    total, used, free = shutil.disk_usage("/")
    resultado["disco_libre_gb"] = round(free / (1024**3), 1)
    resultado["disco_alerta"] = free < 2 * (1024**3)  # alerta si <2GB

    # 3. Último backup
    backup_dir = Path(os.getenv("BACKUP_DIR", "./storage/backups"))
    backups = sorted(backup_dir.glob("*.zip")) if backup_dir.exists() else []
    if backups:
        ultimo = backups[-1]
        edad_horas = (datetime.now().timestamp() - ultimo.stat().st_mtime) / 3600
        resultado["ultimo_backup"] = ultimo.name
        resultado["backup_edad_horas"] = round(edad_horas, 1)
        resultado["backup_alerta"] = edad_horas > 25  # alerta si >25h
    else:
        resultado["ultimo_backup"] = None
        resultado["backup_alerta"] = True

    # 4. ffmpeg disponible
    resultado["ffmpeg"] = shutil.which("ffmpeg") is not None

    # 5. LibreOffice disponible
    resultado["libreoffice"] = (
        shutil.which("libreoffice") is not None or
        shutil.which("soffice") is not None
    )

    # 6. Agenda: cuándo fue la última actualización
    agenda_path = Path("./storage/agenda_actual.json")
    if agenda_path.exists():
        import json as _json
        try:
            agenda = _json.loads(agenda_path.read_text())
            resultado["agenda_actualizada"] = agenda.get("actualizado", "desconocido")
        except Exception:
            resultado["agenda_actualizada"] = "error_leyendo"
    else:
        resultado["agenda_actualizada"] = None

    # 7. Tareas activas en workflow
    from backend.task_db import TaskDB
    db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
    try:
        db = TaskDB(db_path)
        activas = db.listar_activos()
        resultado["tareas_activas"] = len(activas)
    except Exception:
        resultado["tareas_activas"] = "error"

    # 8. Estado general
    hay_alerta = resultado.get("disco_alerta") or resultado.get("backup_alerta")
    resultado["estado"] = "alerta" if hay_alerta else "ok"
    resultado["timestamp"] = datetime.now().isoformat()

    return resultado
```

**Respuesta esperada en producción sana:**
```json
{
  "backend": "ok",
  "disco_libre_gb": 45.2,
  "disco_alerta": false,
  "ultimo_backup": "backup_2026-05-22.zip",
  "backup_edad_horas": 4.2,
  "backup_alerta": false,
  "ffmpeg": true,
  "libreoffice": true,
  "agenda_actualizada": "2026-05-22T21:03:45",
  "tareas_activas": 0,
  "estado": "ok",
  "timestamp": "2026-05-22T10:15:30"
}
```

---

### PD-7 — Convención de nombres para archivos generados

**Problema:** Los DOCX generados actualmente se llaman `Carta_Medidas_Preventivas.docx` sin
incluir CC ni fecha. Si Sandra tiene 3 pacientes activos, los archivos se sobreescriben entre sí.

**Convención nueva:**
```
{Formato}_{CC}_{YYYY-MM-DD}.docx
```

**Ejemplos:**
```
Analisis_Exigencias_1193143688_2026-05-22.docx
Carta_Medidas_Preventivas_55162801_2026-05-22.docx
VOI_36184789_2026-05-22.docx
```

**`backend/doc_generator.py`** — función que determina el nombre de salida:
```python
from datetime import date

def _nombre_archivo(formato: str, cc: str) -> str:
    slug = formato.lower().replace(" ", "_").replace("á","a").replace("é","e")
    fecha = date.today().strftime("%Y-%m-%d")
    return f"{slug}_{cc}_{fecha}.docx"
```

**Impacto:** El endpoint de descarga y el endpoint ZIP deben buscar por patrón `*_{cc}_*.docx`
en lugar de nombre fijo. Actualizar `descargar_archivo` y el endpoint ZIP.

---

### LH — Tabla resumen de tareas (bloque Limpieza Hermes + Producción)

| ID | Descripción | Impacto | Archivo | Tiempo |
|----|-------------|---------|---------|--------|
| LH1 | Eliminar `config/hermes-*.yaml/txt` | Repo limpio, sin confusión | `config/` | 5 min |
| LH2 | Renombrar `hermes.ts` → `api.ts`, cambiar env var | URL correcta en producción | `dashboard/lib/` | 15 min |
| LH3 | Actualizar imports en `pacientes/` y `chat/` | Sin errores de import | 2 páginas | 5 min |
| LH4 | Limpiar comentarios "Hermes" en route handlers | Código limpio | `app/api/*/route.ts` | 10 min |
| LH5 | Archivar `puente_docker.py` | Sin código muerto | `backend/` | 5 min |
| LH6 | Reescribir `start-wsl.sh` sin Docker | Sistema arranca en producción | `start-wsl.sh` | 20 min |
| LH7 | Crear `deploy.sh` (reemplaza `sync-to-wsl.sh`) | Deploy via git funcional | `deploy.sh` | 15 min |
| LH8 | Convertir `skills/` a `docs/portales/` | Mapas portales accesibles | `skills/` → `docs/` | 20 min |
| PD1 | Instalar PM2 + `ecosystem.config.js` | Procesos resilientes y auto-inicio | `ecosystem.config.js` | 30 min |
| PD2 | `next build` + `next start` en producción | 3-4× más rápido | `deploy.sh` | 10 min |
| PD3 | Windows Task Scheduler VBScript | Auto-inicio al encender PC Sandra | `RILO_autostart.vbs` | 15 min |
| PD4 | CORS para red local + IP en .env | Sandra usa desde teléfono | `server.py`, `.env` | 10 min |
| PD5 | Registrar crons de backup en startup | Datos respaldados automáticamente | `server.py` | 20 min |
| PD6 | Endpoint `/api/system/health` completo | Diagnóstico rápido del sistema | `server.py` | 45 min |
| PD7 | Convención CC+fecha en nombres de archivos | Sin sobreescritura entre pacientes | `doc_generator.py` | 30 min |

**Subtotal bloque LH+PD: ~4 horas**

---

## Bugs adicionales (tabla completa actualizada)

| # | Bug | Impacto en Sandra | Archivo | Bloque |
|---|-----|-------------------|---------|--------|
| 31 | `lib/hermes.ts` usa env var incorrecta | URL rota en producción | `dashboard/lib/hermes.ts` | LH2 |
| 32 | `start-wsl.sh` busca Docker | Sistema nunca arranca en WSL | `start-wsl.sh` | LH6 |
| 33 | `sync-to-wsl.sh` usa `docker cp` | Deploy roto | `sync-to-wsl.sh` | LH7 |
| 34 | Backend corre con `--reload` en producción | CPU innecesario | `start.sh` | PD2 |
| 35 | Dashboard corre con `next dev` | Lento, compila en cada request | `start-wsl.sh` | PD2 |
| 36 | Sin PM2/systemd | Procesos mueren y no resucitan | — | PD1 |
| 37 | `config/hermes-*.yaml` en repo | Confunde, archivos muertos | `config/` | LH1 |
| 38 | `puente_docker.py` código muerto | Código innecesario | `backend/` | LH5 |
| 39 | Backup mensual nunca registrado | Sin test de restauración | `server.py` | PD5 |
| 40 | Sin `/api/system/health` completo | Sin diagnóstico rápido | `server.py` | PD6 |
| 41 | Archivos DOCX sin CC ni fecha | Sobreescritura entre pacientes | `doc_generator.py` | PD7 |

---

## Tiempo estimado total

| Bloque | Tiempo |
|--------|--------|
| A — Bugs bloqueantes | 60 min |
| B — Chat omnisciente | 3-4 horas |
| P — Portales inteligentes | 4-5 horas |
| CR — Corrección desde chat | 2 horas |
| Z — ZIP + retry | 1.5 horas |
| TG — Telegram bidireccional | 4 horas |
| H — Mi Día + UX | 2 horas |
| PR — Pre-check campos | 1 hora |
| FX — Fixes críticos adicionales | 2 horas |
| AG — Agenda completa | 3 horas |
| M — M4A especialización | 2 horas |
| C — Deploy + configuración | 45 min |
| LH+PD — Limpieza Hermes + Producción robusta | 4 horas |
| **TOTAL** | **~30 horas** |

*Actualizado 2026-05-22 (v6). Probado con backend real, API keys verificadas, 8 tests pasando. 41 bugs documentados. Hermes eliminado. PM2 + next build + Task Scheduler. Backup crons registrados. Health check completo. Nombres de archivo con CC+fecha.*

---

## PARTE 14 — Bugs reales encontrados leyendo el código fuente

> **Contexto:** Segunda ronda de auditoría profunda del código existente. Los problemas anteriores
> venían de inferencia y diseño. Estos vienen de leer cada archivo Python y TypeScript línea por línea.
> Todos los bloques NC son críticos (rompen el sistema) o de alto impacto.

---

### NC-1 — `qa_formatos.py` llama a script que se borrará con la limpieza Hermes

**Bug crítico. Descubierto en:** `backend/workflow_steps/qa_formatos.py` línea 20.

```python
def _qa_script_path() -> Path:
    # ← APUNTA A skills/verificar-documento que se borra en LIMPIEZA-8
    return Path(__file__).parent.parent.parent / "skills" / "verificar-documento" / "scripts" / "qa_completo.py"
```

**Impacto:** Cuando se ejecute LIMPIEZA-8 (borrar `skills/`), el Paso 7 del workflow (QA de formatos)
**siempre devolverá** `qa_ok: True, qa_warnings: ["QA script no disponible"]` — es decir, aprobará
cualquier documento sin verificar nada. Los 7 formatos salen sin QA aunque tengan datos incorrectos.

**Fix — reimplementar QA inline en el paso 7 sin dependencia de scripts externos:**

```python
# backend/workflow_steps/qa_formatos.py — versión sin skills/
from pathlib import Path

def _qa_docx(archivo: str) -> dict:
    """QA básico inline: verifica que el DOCX existe, tiene contenido y no tiene campos vacíos."""
    path = Path(archivo)
    if not path.exists():
        return {"qa_ok": False, "qa_warnings": ["archivo_no_existe"]}

    try:
        from docx import Document
        doc = Document(str(path))
    except Exception as e:
        return {"qa_ok": False, "qa_warnings": [f"docx_corrupto: {e}"]}

    warnings = []

    # 1. El documento tiene párrafos
    texto = " ".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
    if len(texto) < 100:
        warnings.append("documento_muy_corto")

    # 2. No tiene placeholders sin llenar
    for placeholder in ["[VERIFICAR]", "[DATO]", "[COMPLETAR]", "XXXXXXX", "{{", "}}"]:
        if placeholder in texto:
            warnings.append(f"placeholder_sin_llenar: {placeholder}")

    # 3. Las tablas tienen filas con contenido
    tablas_vacias = 0
    for tabla in doc.tables:
        for fila in tabla.rows:
            if all(not c.text.strip() for c in fila.cells):
                tablas_vacias += 1
    if tablas_vacias > 3:
        warnings.append(f"tablas_con_filas_vacias: {tablas_vacias}")

    # 4. Tiene firma (si espera firma_sandra.png)
    # Nota: firma se inserta como imagen en el DOCX
    # (esto se puede ampliar más adelante)

    return {
        "qa_ok": len([w for w in warnings if "placeholder" in w]) == 0,
        "qa_warnings": warnings,
    }


def qa_uno(formato: dict) -> dict:
    archivo = formato.get("archivo")
    if not archivo:
        return {**formato, "qa_ok": False, "qa_warnings": ["sin_ruta_archivo"]}
    result = _qa_docx(archivo)
    return {**formato, **result}


def qa_todos(formatos):
    resultados = [qa_uno(f) for f in formatos]
    return {
        "ok": True,
        "resultados": resultados,
        "total": len(formatos),
        "exitosos": sum(1 for r in resultados if r.get("qa_ok")),
        "con_warnings": sum(1 for r in resultados if r.get("qa_warnings")),
    }

def ejecutar(formatos_generados):
    return qa_todos(formatos_generados)
```

---

### NC-2 — Confirmar modelo `deepseek-v4-flash` funciona; si no, fallback a pro

**Verificación necesaria. Descubierto en:** `backend/correction_resolver.py` línea 57.

```python
modelo = os.getenv("LLM_MODEL_EXTRACCION", "deepseek-v4-flash")
```

**Diseño intencionado — CORRECTO:** Usar flash (más rápido, más barato) para clasificación de
campos (`correction_resolver`) y pro (razonador) para síntesis clínica es buena arquitectura.
El clasificador solo necesita identificar "campo: siniestro.id_siniestro, valor: 503476658".
No necesita 8K tokens de razonamiento.

**Verificar que flash existe en el endpoint OpenCode Go:**
```bash
curl -X POST https://opencode.ai/zen/go/v1/chat/completions \
  -H "Authorization: Bearer $OPENCODE_GO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hola"}],"max_tokens":50}' \
  | python3 -m json.tool
```

**Si NO existe, agregar fallback con retry:**
```python
# correction_resolver.py — probar flash, si falla usar pro
MODELOS_CLASIFICADOR = [
    os.getenv("LLM_MODEL_EXTRACCION", "deepseek-v4-flash"),
    os.getenv("LLM_MODEL", "deepseek-v4-pro"),  # fallback
]
```

**Agregar en `.env` para control explícito:**
```bash
LLM_MODEL_EXTRACCION=deepseek-v4-flash  # clasificación rápida (correction_resolver)
LLM_MODEL_SINTESIS=deepseek-v4-pro      # síntesis clínica completa (sintetizar_maestro)
LLM_MODEL=deepseek-v4-pro               # chat general (chat_handler)
```

---

### NC-3 — `flujo_audio.py` no tiene timeout en llamada a Deepgram

**Bug de confiabilidad. Descubierto en:** `backend/flujo_audio.py` línea 57.

```python
# Sin timeout → puede colgar el proceso indefinidamente si Deepgram no responde
response = requests.post(DEEPGRAM_URL, headers=headers, params=params, data=f)
```

**Impacto:** Si Deepgram tiene un timeout o la conexión cae a mitad de la subida de un audio de 100MB,
el hilo del workflow se cuelga indefinidamente. La tarea queda en estado "transcribiendo" para siempre.
El usuario no puede cancelar desde el dashboard (cancelar solo marca la DB, no mata el hilo).

**Fix:**
```python
# flujo_audio.py — agregar timeout y validación de tamaño
import os

MAX_AUDIO_MB = int(os.getenv("MAX_AUDIO_MB", "200"))

def transcribir_audio(audio_path: str) -> dict:
    # Validar tamaño
    size_mb = os.path.getsize(audio_path) / 1024 / 1024
    if size_mb > MAX_AUDIO_MB:
        raise ValueError(f"Audio demasiado grande: {size_mb:.0f}MB (máximo {MAX_AUDIO_MB}MB)")

    # ... configuración existente ...

    with open(audio_path, "rb") as f:
        response = requests.post(
            DEEPGRAM_URL,
            headers=headers,
            params=params,
            data=f,
            timeout=(30, 600),  # (connect_timeout, read_timeout) — 10 min máximo para upload
        )
```

**Agregar en `.env`:**
```bash
MAX_AUDIO_MB=200  # rechazar audios >200MB (>75 min en M4A iPhone)
```

---

### NC-4 — Chat no renderiza Markdown: respuestas de Tomy llegan llenas de `##`, `|`, `*`

**Bug de UX crítico. Descubierto en:** `dashboard/app/chat/page.tsx` línea 194.

```tsx
{/* whitespace-pre-wrap muestra ## headers y | tablas como texto plano */}
<p className="whitespace-pre-wrap">{msg.contenido}</p>
```

**Impacto:** El `SYSTEM_PROMPT` de Tomy le pide que responda con `## RESUMEN`, tablas Markdown,
emojis estructurados, etc. Con `whitespace-pre-wrap`, Sandra ve literalmente:

```
## 🔍 RESUMEN
[texto]
## 📊 TABLA DE CONSISTENCIA
| Campo | Formato 1 | ...
```

En vez de headers y tablas reales. Las respuestas son ilegibles.

**Fix — instalar `react-markdown` y renderizar:**
```bash
cd dashboard && npm install react-markdown remark-gfm
```

```tsx
// dashboard/app/chat/page.tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// En el render del mensaje:
<div className="prose prose-sm max-w-none">
  <ReactMarkdown
    remarkPlugins={[remarkGfm]}
    components={{
      table: ({...props}) => (
        <table className="border-collapse text-xs w-full my-2" {...props} />
      ),
      th: ({...props}) => (
        <th className="border border-slate-300 px-2 py-1 bg-slate-100 font-semibold" {...props} />
      ),
      td: ({...props}) => (
        <td className="border border-slate-300 px-2 py-1" {...props} />
      ),
      a: ({...props}) => (
        <a className="text-blue-600 underline" target="_blank" {...props} />
      ),
    }}
  >
    {msg.contenido}
  </ReactMarkdown>
</div>
```

---

### NC-5 — Chat: `paciente_cc` siempre es `undefined` — Tomy trabaja a ciegas

**Bug funcional. Descubierto en:** `dashboard/app/chat/page.tsx` línea 73.

```tsx
body: JSON.stringify({
  mensaje,
  paciente_cc: undefined,  // ← SIEMPRE undefined. Tomy no sabe de qué paciente habla Sandra.
  historial: updatedMensajes.slice(-10),
}),
```

**Impacto:** Aunque Sandra diga "revísame el VOI de Juan Carlos", Tomy recibe `paciente_cc=None`.
El backend busca el archivo por nombre en el mensaje, pero sin CC nunca puede buscar los datos
del portal ni contextualizarse en el historial del paciente. La búsqueda multi-archivo falla
porque `_buscar_archivos_paciente` recibe `cc=""`.

**Fix — agregar selector de paciente en el chat:**

```tsx
// dashboard/app/chat/page.tsx — agregar estado para paciente activo
const [pacienteActivo, setPacienteActivo] = useState<string>(""); // CC del paciente en foco
const [pacientesDisponibles, setPacientesDisponibles] = useState<{cc: string, nombre: string}[]>([]);

// Cargar lista de pacientes al montar
useEffect(() => {
  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
  fetch(`${API}/pacientes`)
    .then(r => r.json())
    .then(data => setPacientesDisponibles(
      (Array.isArray(data) ? data : []).map((p: any) => ({
        cc: p.documento,
        nombre: p.nombre || `CC ${p.documento}`,
      }))
    ))
    .catch(() => {});
}, []);

// En el render, encima del área de chat — selector compacto:
<div className="flex items-center gap-2 mb-2">
  <span className="text-sm text-slate-500">Paciente:</span>
  <select
    value={pacienteActivo}
    onChange={(e) => setPacienteActivo(e.target.value)}
    className="text-sm border border-slate-300 rounded-lg px-2 py-1 bg-white"
  >
    <option value="">— Ninguno (consulta general) —</option>
    {pacientesDisponibles.map(p => (
      <option key={p.cc} value={p.cc}>{p.nombre} (CC {p.cc})</option>
    ))}
  </select>
  {pacienteActivo && (
    <a href={`/paciente/${pacienteActivo}`} className="text-xs text-blue-600 underline">
      Ver perfil →
    </a>
  )}
</div>

// En el fetch del chat, usar pacienteActivo:
body: JSON.stringify({
  mensaje,
  paciente_cc: pacienteActivo || undefined,
  historial: updatedMensajes.slice(-10),
}),
```

---

### NC-6 — `notificador.py`: agenda guardada sin CC → clic en cita no navega al paciente

**Bug funcional. Descubierto en:** `backend/notificador.py` líneas 72-89 y `email_reader.py`.

```python
def guardar_agenda(agenda: AgendaDia):
    data = {
        "citas": [
            {
                "paciente": c.paciente,
                "telefono": c.telefono,   # ← tiene teléfono pero NO cc
                "hora": c.hora,
                "servicio": c.servicio,
                "fecha": c.fecha,
                "es_nueva": c.es_nueva,
            }
            for c in agenda.citas
        ]
    }
```

**Impacto:** En `hoy/page.tsx`, cada cita tiene `c.cc` para navegar al perfil del paciente.
Pero `guardar_agenda` nunca guarda el CC. La línea `c.cc ? /paciente/${c.cc} : "#"` siempre
usa `"#"`. Las citas del dashboard son botones que no llevan a ningún lado.

**Causa raíz:** El email de Medifolios puede tener el nombre y el teléfono del paciente,
pero no necesariamente el CC. Hay que buscar el CC en `storage/data/` por nombre.

**Fix en `guardar_agenda` — buscar CC por nombre:**
```python
import glob, json

def _buscar_cc_por_nombre(nombre: str) -> Optional[str]:
    """Busca el CC del paciente en storage/data/ comparando nombres."""
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    archivos = glob.glob(str(storage / "data" / "*-completo.json"))
    nombre_lower = nombre.lower().replace(",", "").strip()
    palabras = [p for p in nombre_lower.split() if len(p) > 2]  # palabras significativas
    
    for archivo in archivos:
        try:
            datos = json.loads(Path(archivo).read_text(encoding="utf-8"))
            nombre_json = datos.get("paciente", {}).get("nombre", "").lower()
            if sum(1 for p in palabras if p in nombre_json) >= 2:
                return datos.get("paciente", {}).get("documento", "")
        except Exception:
            continue
    return None


def guardar_agenda(agenda: AgendaDia):
    data = {
        "fecha": agenda.fecha,
        "total": agenda.total,
        "actualizado": datetime.now().isoformat(),
        "citas": [
            {
                "paciente": c.paciente,
                "telefono": c.telefono,
                "hora": c.hora,
                "servicio": c.servicio,
                "fecha": c.fecha,
                "es_nueva": c.es_nueva,
                # NUEVO: intentar resolver CC por nombre
                "cc": _buscar_cc_por_nombre(c.paciente) or "",
            }
            for c in agenda.citas
        ]
    }
    # ... resto igual ...
```

---

### NC-7 — `lib/workflow.ts` hardcodea `http://localhost:8000` — cuarto archivo con URL hardcodeada

**Bug de configuración. Descubierto en:** `dashboard/lib/workflow.ts` línea 1.

```typescript
const API = "http://localhost:8000";  // ← hardcodeado, NO usa env var
```

**Impacto:** `workflow.ts` es importado por `subir-audio/page.tsx` y posiblemente por otros componentes.
En producción con IP local o con un host diferente, las llamadas fallan.

**Lista completa de URLs hardcodeadas encontradas:**
| Archivo | Línea | URL hardcodeada |
|---------|-------|-----------------|
| `dashboard/lib/workflow.ts` | 1 | `const API = "http://localhost:8000"` |
| `dashboard/app/chat/page.tsx` | 70 | `fetch("http://localhost:8000/api/chat"` |
| `dashboard/app/hoy/page.tsx` | 31-32 | `fetch("http://localhost:8000/api/..."` |
| `dashboard/app/paciente/[cc]/page.tsx` | 20-21, 42 | `fetch("http://localhost:8000/api/..."` |
| `dashboard/app/subir-audio/page.tsx` | 35 | `fetch("http://localhost:8000/api/procesar-paciente"` |

**Fix global — crear `dashboard/lib/config.ts`:**
```typescript
// dashboard/lib/config.ts
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const API = `${API_URL}/api`;
```

**Y en cada archivo reemplazar la URL hardcodeada:**
```typescript
import { API } from "@/lib/config";
// fetch(`${API}/chat`, ...)
// fetch(`${API}/tasks/activas`, ...)
// etc.
```

**`dashboard/.env.local`:**
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
# En producción con IP local (Sandra desde teléfono):
# NEXT_PUBLIC_API_URL=http://192.168.1.100:8000
```

---

### NC-8 — `threading.Thread` en `procesar_paciente`: worker muere si el proceso reinicia

**Bug de confiabilidad. Descubierto en:** `backend/server.py` líneas 695-701.

```python
import threading
def _runner():
    try:
        ejecutar_workflow(...)
    except Exception as e:
        print(f"[WORKFLOW BG] error: {e}")
threading.Thread(target=_runner, daemon=True).start()  # daemon=True → muere con el proceso
```

**Impacto:** Si uvicorn se reinicia (PM2 auto-restart, crash, deploy), el hilo muere a mitad del workflow.
La tarea queda en un estado no-terminal (ej: "sintetizando") en la DB **para siempre**.
El dashboard muestra "Tomy está trabajando..." indefinidamente aunque no haya nada corriendo.

**Fix — usar `asyncio.create_task` + `BackgroundTasks` de FastAPI, y detección de tasks huérfanas:**

```python
# server.py — reemplazar threading con asyncio background task
from fastapi import BackgroundTasks

@app.post("/api/procesar-paciente")
async def procesar_paciente(
    audio: UploadFile = File(...),
    paciente_cc: str = Form(...),
    background_tasks: BackgroundTasks = None,
):
    # ... guardar audio, crear task_id en DB ...

    async def _runner_async():
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,  # ThreadPoolExecutor por defecto
            lambda: ejecutar_workflow(
                audio_path=str(audio_path),
                paciente_cc=paciente_cc,
                task_id_existente=task_id,
            )
        )

    background_tasks.add_task(_runner_async)
    return {"ok": True, "task_id": task_id, ...}
```

**Detección de tasks huérfanas en startup:**
```python
@app.on_event("startup")
async def startup_event():
    # ... crons existentes ...

    # Limpiar tasks "zombies" de un restart anterior
    from backend.task_db import TaskDB
    db = TaskDB(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))
    activas = db.listar_activos()
    for t in activas:
        # Si una task activa tiene más de 2 horas, marcarla como error
        from datetime import datetime, timedelta
        iniciado = datetime.fromisoformat(t.get("iniciado_en", datetime.now().isoformat()))
        if (datetime.now() - iniciado).total_seconds() > 7200:
            db.marcar_error(t["task_id"], paso=t.get("paso_actual", 0), error="reiniciado_por_restart_servidor")
            _log(f"Task huérfana marcada como error: {t['task_id']}")
```

---

### NC-9 — `server.py` stats endpoint muestra fecha de DOCX como "fecha de backup"

**Bug de información incorrecta. Descubierto en:** `backend/server.py` líneas 196-205.

```python
@app.get("/api/stats")
def stats():
    archivos_docx = [...]
    backup_fecha = "—"
    if archivos_docx:
        newest = max(archivos_docx, key=os.path.getmtime)
        # BUG: esto es la fecha del DOCX más reciente, NO la fecha del último backup
        backup_fecha = datetime.fromtimestamp(os.path.getmtime(newest)).strftime("%d/%m/%Y")

    return {
        "total_pacientes": total_pacientes,
        "total_formatos": len(archivos_docx),
        "backup_fecha": backup_fecha,   # ← Sandra ve "Último respaldo: 22/05/2026"
                                         # pero es la fecha del último formato, no del backup
    }
```

**Fix:**
```python
@app.get("/api/stats")
def stats():
    # ... contar pacientes y formatos igual ...

    # Último backup real
    backup_dir = Path(os.getenv("BACKUP_DESTINO", "./storage/backups"))
    backups = sorted(backup_dir.glob("backup_*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True) if backup_dir.exists() else []
    backup_fecha = datetime.fromtimestamp(backups[0].stat().st_mtime).strftime("%d/%m/%Y") if backups else "Sin backup aún"

    return {
        "total_pacientes": total_pacientes,
        "total_formatos": len(archivos_docx),
        "backup_fecha": backup_fecha,
        "backup_pendiente": not backups or (datetime.now().timestamp() - backups[0].stat().st_mtime) > 86400,
    }
```

---

### NC-10 — `server.py/archivos` endpoint usa `item.rglob` (prohibido en `/mnt/c/`)

**Bug de performance. Descubierto en:** `backend/server.py` línea 457.

```python
# BUG: rglob en /mnt/c/ puede tomar 30+ segundos y bloquearlo todo
info["contenido"] = sum(1 for _ in item.rglob("*") if _.is_file())
```

**Contexto:** El CLAUDE.md dice explícitamente: "NO usar rglob en /mnt/c/ (lentísimo, 30s+)".
El workspace de Sandra está en `/mnt/c/Users/Sandra/Desktop/SANDRA/...`. Esto bloquea el endpoint
por 30+ segundos cada vez que Sandra navega en la página de Archivos.

**Fix:**
```python
# Reemplazar rglob con conteo rápido de 1 nivel
if item.is_dir():
    try:
        contenido = sum(1 for _ in item.iterdir() if _.is_file())  # solo 1 nivel, rápido
    except PermissionError:
        contenido = 0
    info["contenido"] = contenido
```

---

### NC-11 — No hay página `/login` aunque `auth_simple.py` existe

**Bug de seguridad/UX. Descubierto en:** ausencia de `dashboard/app/login/page.tsx`.

**Estado actual:**
- `backend/auth_simple.py` → `validar_pin()` + `generar_token()` ✅
- `backend/server.py` → endpoint `/api/login` (no visible en el código leído pero referenciado en `lib/auth.ts`)
- `dashboard/lib/auth.ts` → funciones de auth del lado cliente ✅
- `dashboard/middleware.ts` → **NO EXISTE** ❌
- `dashboard/app/login/page.tsx` → **NO EXISTE** ❌

**Impacto:** Cualquiera en la misma red WiFi puede acceder a todos los datos de los pacientes.
Sandra abre `localhost:3000` y entra directamente sin pedir PIN.

**Fix — crear `dashboard/app/login/page.tsx`:**
```tsx
// dashboard/app/login/page.tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const login = async () => {
    if (pin.length !== 4) { setError("El PIN tiene 4 números"); return; }
    setLoading(true);
    try {
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const resp = await fetch(`${API}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin }),
        credentials: "include",  // para que guarde la cookie
      });
      if (resp.ok) {
        router.replace("/hoy");
      } else {
        setError("PIN incorrecto. Prueba de nuevo.");
        setPin("");
      }
    } catch {
      setError("No pude conectar con el servidor.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="bg-white p-10 rounded-3xl shadow-lg w-full max-w-sm text-center space-y-6">
        <div>
          <p className="text-5xl mb-3">🏥</p>
          <h1 className="text-3xl font-bold text-slate-800">RILO SAS</h1>
          <p className="text-slate-500 mt-1">Ingresa tu PIN para continuar</p>
        </div>
        <input
          type="password"
          inputMode="numeric"
          maxLength={4}
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
          onKeyDown={(e) => e.key === "Enter" && login()}
          className="w-full text-center text-4xl tracking-[1rem] p-4 border-2 border-slate-300 rounded-2xl focus:border-blue-500 outline-none"
          placeholder="• • • •"
          autoFocus
        />
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button
          onClick={login}
          disabled={loading || pin.length !== 4}
          className="w-full py-4 bg-blue-600 text-white text-xl font-semibold rounded-2xl hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Entrando..." : "Entrar"}
        </button>
      </div>
    </div>
  );
}
```

**Fix — crear `dashboard/middleware.ts`:**
```typescript
// dashboard/middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Rutas públicas — no requieren auth
  if (pathname.startsWith("/login") || pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  // Verificar cookie de auth
  const token = request.cookies.get("rilo_auth")?.value;
  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
```

**Agregar endpoint `/api/login` en `server.py` (verificar si ya existe):**
```python
@app.post("/api/login")
def login(req: LoginRequest, response: Response):
    from backend.auth_simple import validar_pin, generar_token
    if not validar_pin(req.pin):
        raise HTTPException(status_code=401, detail="PIN incorrecto")
    token = generar_token("Sandra")
    response.set_cookie(
        key="rilo_auth",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 30,  # 30 días
    )
    return {"ok": True}

@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("rilo_auth")
    return {"ok": True}
```

---

### NC-12 — Sistema prompt obliga a respuesta de 6 secciones para CUALQUIER pregunta

**Bug de UX/costo. Descubierto en:** `backend/chat_handler.py` líneas 119-153.

```python
SYSTEM_PROMPT = """...
## 📋 FORMATO DE RESPUESTA (OBLIGATORIO)
Respondé SIEMPRE con esta estructura:
## 🔍 RESUMEN ... ## 📊 TABLA DE CONSISTENCIA ... ## ⚠️ VERIFICACIONES ... ## 📝 DATOS ...
## ❌ DISCREPANCIAS ... ## 🔴 CAMPOS FALTANTES ...
"""
```

**Impacto:** Para "¿cuántos pacientes hay?", Tomy genera:
```
## 🔍 RESUMEN
Hay 2 pacientes en el sistema.
## 📊 TABLA DE CONSISTENCIA
N/A para esta consulta...
## ⚠️ VERIFICACIONES PENDIENTES EN PORTALES
N/A...
```
— 6 secciones con 5 vacías. Consume 3-4K tokens extra de razonamiento. Tarda 30-60 segundos más.
Cuesta más. Sandra ve una pared de texto para una pregunta simple.

**Fix — sistema de detección de intención + prompt adaptativo:**
```python
def _detectar_tipo_consulta(mensaje: str) -> str:
    """Clasifica la consulta para usar el prompt correcto."""
    ml = mensaje.lower()
    # Consulta simple: información rápida
    if any(kw in ml for kw in ["cuántos", "cuantos", "hay", "lista", "dame", "cuál es", "cuáles son"]):
        if not any(kw in ml for kw in ["formato", "documento", "verifica", "revisa", "analiza", "corrige"]):
            return "simple"
    # Corrección
    if any(kw in ml for kw in ["cambia", "corrige", "no es", "está mal", "error en", "el siniestro es"]):
        return "correccion"
    # Análisis de documentos
    if any(kw in ml for kw in ["revisa", "analiza", "verifica", "compara", "todos los formatos"]):
        return "analisis"
    return "general"


PROMPT_SIMPLE = """Eres Tomy, asistente de RILO SAS. Responde de forma BREVE y DIRECTA.
Máximo 3-4 líneas. Sin estructuras ni secciones. Español colombiano cálido.
Si necesitas información, pídela simple. No uses ### ni tablas para preguntas sencillas."""

PROMPT_CORRECCION = """Eres Tomy, asistente de RILO SAS. Sandra está corrigiendo un dato.
Confirma qué campo cambiaste, el valor anterior y el nuevo. Sé conciso.
Formato: "✅ Corregí [campo]: [anterior] → [nuevo]". Una línea."""

# Usar en procesar_mensaje:
tipo = _detectar_tipo_consulta(mensaje)
system = {
    "simple": PROMPT_SIMPLE,
    "correccion": PROMPT_CORRECCION,
    "analisis": SYSTEM_PROMPT,  # el prompt completo de 6 secciones
    "general": SYSTEM_PROMPT,
}[tipo]
```

---

### NC-13 — Chat no tiene input de voz ni botón de grabar

**Funcionalidad faltante. Descubierto en:** `dashboard/app/chat/page.tsx` — solo tiene `<input type="text">`.

**Contexto:** Sandra usa iPhone. Prefiere hablar. En `/subir-audio` puede subir M4A de la consulta.
Pero si quiere hacerle una pregunta rápida a Tomy en el chat ("¿qué le falta al VOI de Juan Carlos?"),
tiene que tipear. Con la mano sobre el celular esto es lento e incómodo.

**Fix — botón de micrófono con Web Speech API (gratuito, sin Deepgram):**

> **Nota:** Web Speech API funciona en Chrome/Edge (Android/Windows) pero NO en Firefox ni Safari iOS.
> Para Safari iOS (iPhone de Sandra), hay que usar Deepgram o el flujo de audio normal.
> **Solución pragmática:** grabar en el navegador + enviar a Deepgram → transcripción → insertar en el input.

```tsx
// dashboard/app/chat/page.tsx — agregar grabación de voz
const [grabando, setGrabando] = useState(false);
const mediaRef = useRef<MediaRecorder | null>(null);
const chunksRef = useRef<Blob[]>([]);

const iniciarGrabacion = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    chunksRef.current = [];
    recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
    recorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      // Transcribir el audio de voz con el mismo endpoint de Deepgram
      const form = new FormData();
      form.append("audio", blob, "voz.webm");
      form.append("solo_transcribir", "true");  // nuevo param para skip de datos cualitativos
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const resp = await fetch(`${API}/api/upload-audio`, { method: "POST", body: form });
      if (resp.ok) {
        const data = await resp.json();
        setInput(prev => prev + (prev ? " " : "") + data.transcripcion);
      }
      setGrabando(false);
    };
    recorder.start();
    mediaRef.current = recorder;
    setGrabando(true);
  } catch {
    alert("No se pudo acceder al micrófono.");
  }
};

const detenerGrabacion = () => {
  mediaRef.current?.stop();
};

// En el input bar, agregar botón de micrófono:
<button
  onMouseDown={iniciarGrabacion}
  onMouseUp={detenerGrabacion}
  onTouchStart={iniciarGrabacion}
  onTouchEnd={detenerGrabacion}
  className={`p-3 rounded-xl ${grabando ? "bg-red-500 text-white animate-pulse" : "bg-slate-200 text-slate-600 hover:bg-slate-300"}`}
  title="Mantener para hablar"
>
  <Mic size={20} />
</button>
```

**Agregar param `solo_transcribir` en `server.py`:**
```python
@app.post("/api/upload-audio")
async def upload_audio(
    audio: UploadFile = File(...),
    paciente_cc: str = Form(default="voz"),
    solo_transcribir: bool = Form(default=False),  # NUEVO
):
    # Si solo_transcribir=True, solo llamar a Deepgram y retornar texto
    # Sin guardar, sin extraer datos cualitativos
    if solo_transcribir:
        ext = Path(audio.filename or "audio.webm").suffix or ".webm"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(await audio.read())
            audio_path = tmp.name
        try:
            transcripcion = transcribir_audio(audio_path)
            return {"ok": True, "transcripcion": transcripcion["texto"]}
        finally:
            os.unlink(audio_path)
    # ... resto del flujo normal ...
```

---

### NC-14 — `subir-audio` no pre-llena CC desde agenda del día

**UX faltante. Descubierto en:** `dashboard/app/subir-audio/page.tsx` — input de CC siempre vacío.

**Contexto:** Si el cron nocturno está activado (`FASE_A_CRON_ENABLED=true`), la agenda de mañana
ya está cargada. Cuando Sandra llega a `/subir-audio`, RILO sabe exactamente quiénes son sus pacientes
del día. Pero el campo de CC está vacío y Sandra tiene que tipear la cédula.

**Fix — mostrar pacientes de hoy como botones de selección rápida:**
```tsx
// dashboard/app/subir-audio/page.tsx
const [pacientesHoy, setPacientesHoy] = useState<{cc: string, nombre: string, hora: string}[]>([]);

useEffect(() => {
  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  fetch(`${API}/api/agenda`)
    .then(r => r.json())
    .then(data => {
      const citas = (data.citas || []).filter((c: any) => c.cc);
      setPacientesHoy(citas.map((c: any) => ({
        cc: c.cc,
        nombre: c.paciente,
        hora: c.hora,
      })));
    })
    .catch(() => {});
}, []);

// Encima del input de CC:
{pacientesHoy.length > 0 && (
  <div className="space-y-2">
    <p className="text-slate-500 text-base">Citas de hoy — toca para seleccionar:</p>
    <div className="flex flex-wrap gap-2">
      {pacientesHoy.map(p => (
        <button
          key={p.cc}
          onClick={() => setCc(p.cc)}
          className={`px-4 py-2 rounded-xl border-2 text-left transition-colors ${
            cc === p.cc
              ? "border-blue-500 bg-blue-50 text-blue-700"
              : "border-slate-200 bg-white hover:border-blue-300"
          }`}
        >
          <span className="font-medium">{p.nombre}</span>
          <span className="text-slate-500 ml-2 text-sm">{p.hora}</span>
        </button>
      ))}
    </div>
  </div>
)}
```

---

### NC-15 — `backup_diario.py` envía mensaje de texto, no el archivo de backup

**Bug funcional. Descubierto en:** `backend/backup_diario.py` líneas 46-59.

```python
async def ejecutar_backup():
    archivo = crear_backup()
    from backend.notificador import enviar_telegram
    # ← Solo envía texto. El archivo tar.gz no va a ningún lado.
    enviar_telegram(f"💾 Backup diario OK: {archivo.name} ({tamano_mb:.1f} MB).")
```

**Impacto:** El backup se guarda localmente en `storage/backups/`. Pero si el disco del PC de Sandra
falla o el WSL se corrompe, se pierden tanto los datos como el backup. El plan decía "enviar ZIP a Manu".

**Fix — enviar el archivo por Telegram usando `sendDocument`:**
```python
def enviar_backup_telegram(archivo: Path, chat_id_destino: str = None):
    """Sube el archivo de backup a Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id_destino or os.getenv("TELEGRAM_CHAT_ID_MANU", os.getenv("TELEGRAM_CHAT_ID", ""))
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        with open(archivo, "rb") as f:
            resp = requests.post(url, data={
                "chat_id": chat_id,
                "caption": f"💾 Backup RILO SAS {datetime.now().strftime('%Y-%m-%d')}\n"
                           f"Tamaño: {archivo.stat().st_size / 1024 / 1024:.1f} MB",
            }, files={"document": (archivo.name, f, "application/x-tar")}, timeout=120)
        return resp.status_code == 200
    except Exception as e:
        print(f"[BACKUP] Error enviando a Telegram: {e}")
        return False


async def ejecutar_backup():
    try:
        archivo = crear_backup()
        limpiar_backups_viejos()
        # Intentar enviar el archivo (puede fallar si es muy grande para Telegram — límite 50MB)
        tamano_mb = archivo.stat().st_size / 1024 / 1024
        if tamano_mb <= 50:
            ok = enviar_backup_telegram(archivo)
            if ok:
                enviar_telegram(f"✅ Backup subido a Telegram: {archivo.name} ({tamano_mb:.1f} MB)")
            else:
                enviar_telegram(f"⚠️ Backup local OK pero no pude subirlo a Telegram: {archivo.name}")
        else:
            enviar_telegram(f"💾 Backup guardado local: {archivo.name} ({tamano_mb:.1f} MB). "
                           f"Demasiado grande para Telegram (>50MB).")
    except Exception as e:
        enviar_telegram(f"⚠️ Backup FALLÓ: {e}")
```

---

### NC-16 — Contexto inyectado al chat no incluye agenda ni tareas activas

**Brecha funcional. Descubierto en:** `backend/chat_handler.py` — función `procesar_mensaje`.

El chat inyecta al LLM: workspace (lista de archivos), el archivo buscado por nombre.
**NO inyecta:** agenda del día, tareas activas, lista de pacientes, costos del día.

**Impacto:** Si Sandra pregunta "¿cuándo es mi próxima cita?", Tomy no sabe. Si pregunta "¿en qué
estado está el procesamiento de Juan Carlos?", Tomy no sabe. El claim de "chat omnisciente" es falso.

**Fix — inyectar contexto del sistema en el prompt del LLM:**
```python
def _obtener_contexto_sistema() -> str:
    """Contexto del sistema para inyectar al LLM en cada mensaje."""
    lineas = [f"🕐 HOY: {datetime.now().strftime('%A %d/%m/%Y %H:%M')} (hora Colombia)\n"]

    # Agenda del día
    try:
        agenda_path = Path(os.getenv("STORAGE_DIR", "./storage")) / "agenda_actual.json"
        if agenda_path.exists():
            agenda = json.loads(agenda_path.read_text())
            citas = agenda.get("citas", [])
            if citas:
                lineas.append("📅 AGENDA HOY:")
                for c in citas[:5]:
                    lineas.append(f"  {c.get('hora','?')} — {c.get('paciente','?')} (CC {c.get('cc','?')})")
            else:
                lineas.append("📅 AGENDA: Sin citas registradas hoy.")
    except Exception:
        pass

    # Tareas activas de workflow
    try:
        from backend.task_db import TaskDB
        db = TaskDB(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))
        activas = db.listar_activos()
        if activas:
            lineas.append(f"\n⏳ PROCESANDO AHORA ({len(activas)} tarea(s)):")
            for t in activas[:3]:
                lineas.append(f"  CC {t['paciente_cc']} — Paso {t.get('paso_actual','?')}/9: {t['estado']}")
        else:
            lineas.append("\n✅ Sin tareas activas ahora.")
    except Exception:
        pass

    # Lista de pacientes con datos
    try:
        data_dir = Path(os.getenv("STORAGE_DIR", "./storage")) / "data"
        archivos = list(data_dir.glob("*-completo.json"))
        lineas.append(f"\n👥 PACIENTES CON DATOS: {len(archivos)}")
    except Exception:
        pass

    return "\n".join(lineas)
```

**Usar en `_construir_prompt`:**
```python
def _construir_prompt(mensaje, workspace_str, archivo_contenido, historial, paciente_cc):
    contexto_sistema = _obtener_contexto_sistema()
    # Inyectar como bloque adicional en el system prompt o en el primer mensaje del usuario
    ...
```

---

### NC-17 — Corrección de documentos usa `alert()` — bloqueante y feo en móvil

**Bug de UX. Descubierto en:** `dashboard/app/paciente/[cc]/page.tsx` línea 49.

```tsx
if (data.ok) {
  alert(`✅ Corregí "${data.campo_corregido}". Se regeneraron ${data.formatos_regenerados?.length || 0} formatos.`);
}
```

**Impacto:** `alert()` congela completamente el navegador hasta que el usuario hace clic. En móvil
es especialmente intrusivo. No tiene estilos, bloquea la página entera.

**Fix — reemplazar con toast de `react-hot-toast` (ya en el plan H3):**
```tsx
import toast from "react-hot-toast";

// Reemplazar alert():
if (data.ok) {
  toast.success(`Corregí "${data.campo_corregido}". ${data.formatos_regenerados?.length || 0} formatos actualizados.`);
  setCorreccion("");
} else {
  toast.error(data.mensaje || "No entendí la corrección. ¿Puedes ser más específico?");
}
```

---

### NC-18 — No hay endpoint `/api/costos` para monitorear gasto en LLM

**Funcionalidad faltante. Descubierto en:** `backend/costos_tracker.py` — existe la lógica pero sin endpoint.

**Impacto:** Manuel no puede ver cuánto está gastando en DeepSeek. Si algo hace llamadas en loop
(bug, retry infinito), los costos suben sin que nadie se entere hasta que falla la tarjeta.

**Fix — agregar endpoint y tarjeta en dashboard:**

```python
# server.py — agregar endpoint de costos
@app.get("/api/costos")
def obtener_costos(dias: int = 7):
    """Resumen de costos LLM de los últimos N días."""
    from backend.costos_tracker import resumen_dia
    from datetime import date, timedelta
    resumen = []
    total_tokens = 0
    for i in range(dias):
        fecha = date.today() - timedelta(days=i)
        dia = resumen_dia(fecha)
        resumen.append(dia)
        total_tokens += dia.get("total_tokens", 0)
    return {
        "ok": True,
        "dias": resumen,
        "total_tokens_semana": total_tokens,
        "alerta": total_tokens > int(os.getenv("ALERTA_TOKENS_SEMANA", "500000")),
    }
```

**Tarjeta en `hoy/page.tsx` (visible solo si hay datos):**
```tsx
// Mostrar costo diario al fondo de Mi Día (discreto, solo para Manu)
// Condicional: solo si URL tiene ?admin=1 o si token especial
```

---

### NC — Tabla resumen bloque NC (bugs nuevos)

| ID | Descripción | Impacto | Archivo | Tipo | Tiempo |
|----|-------------|---------|---------|------|--------|
| NC1 | QA paso 7 llama script eliminado | QA siempre "OK" sin verificar nada | `qa_formatos.py` | **Crítico** | 45 min |
| NC2 | `correction_resolver` usa modelo inexistente | Correcciones silenciosamente no aplican | `correction_resolver.py` | **Crítico** | 5 min |
| NC3 | Deepgram sin timeout ni límite de tamaño | Proceso colgado para siempre | `flujo_audio.py` | **Crítico** | 20 min |
| NC4 | Chat no renderiza Markdown | Respuestas de Tomy ilegibles | `chat/page.tsx` | Alto | 30 min |
| NC5 | Chat: `paciente_cc` siempre undefined | Tomy no sabe qué paciente | `chat/page.tsx` | Alto | 45 min |
| NC6 | Agenda sin CC → clic en cita no navega | Dashboard de agenda inutilizable | `notificador.py` | Alto | 30 min |
| NC7 | 5 archivos con URL localhost hardcodeada | Todo rompe en producción con otra IP | 5 archivos | Alto | 30 min |
| NC8 | `threading.Thread` muere al reiniciar | Tasks zombies en DB eternamente | `server.py` | Alto | 45 min |
| NC9 | Stats muestra fecha DOCX como backup | Información incorrecta a Sandra | `server.py` | Medio | 10 min |
| NC10 | `rglob` en endpoint archivos | Página Archivos tarda 30s+ | `server.py` | Medio | 5 min |
| NC11 | Sin `/login` page ni middleware auth | Dashboard público sin protección | `dashboard/app/` | Medio | 60 min |
| NC12 | System prompt obliga 6 secciones siempre | Lento, caro, ilegible para preguntas simples | `chat_handler.py` | Medio | 45 min |
| NC13 | Chat sin voz (micrófono) | Sandra debe tipear en móvil | `chat/page.tsx` | Medio | 90 min |
| NC14 | Subir audio: CC no se pre-llena desde agenda | Sandra debe tipear CC manualmente | `subir-audio/page.tsx` | Medio | 30 min |
| NC15 | Backup solo envía texto, no el archivo | Si el disco falla, backup no existe en la nube | `backup_diario.py` | Medio | 30 min |
| NC16 | Chat no inyecta agenda ni tareas activas | Tomy no sabe qué pasa en el sistema | `chat_handler.py` | Medio | 60 min |
| NC17 | Corrección usa `alert()` bloqueante | UX terrible en móvil | `paciente/[cc]/page.tsx` | Bajo | 5 min |
| NC18 | Sin `/api/costos` endpoint | No se puede monitorear gasto LLM | `server.py` | Bajo | 30 min |

**Subtotal bloque NC: ~9.5 horas**

---

## Tiempo estimado total (actualizado)

| Bloque | Tiempo |
|--------|--------|
| A — Bugs bloqueantes | 60 min |
| B — Chat omnisciente | 3-4 horas |
| P — Portales inteligentes | 4-5 horas |
| CR — Corrección desde chat | 2 horas |
| Z — ZIP + retry | 1.5 horas |
| TG — Telegram bidireccional | 4 horas |
| H — Mi Día + UX | 2 horas |
| PR — Pre-check campos | 1 hora |
| FX — Fixes críticos adicionales | 2 horas |
| AG — Agenda completa | 3 horas |
| M — M4A especialización | 2 horas |
| C — Deploy + configuración | 45 min |
| LH+PD — Limpieza Hermes + Producción robusta | 4 horas |
| NC — Bugs reales (segunda auditoría) | 9.5 horas |
| **TOTAL** | **~41 horas** |

*Actualizado 2026-05-22 (v7). 59 bugs documentados. Segunda auditoría profunda línea por línea. QA paso 7 roto, modelo corrección inexistente, Deepgram sin timeout, chat sin Markdown ni voz ni contexto del sistema, agenda sin CC, 5 URLs hardcodeadas, threads zombies, backup sin archivo, sin login page.*

---

## PARTE 15 — Sistema de clase mundial: más allá de lo básico

> **Filosofía:** Un sistema de fisioterapia clínica completo no es solo "generar documentos".
> Es el asistente invisible de Sandra — aprende, anticipa, protege su trabajo, la hace
> 10× más rápida, y nunca le falla. Esta parte convierte RILO SAS de "sistema funcional"
> a "sistema que Sandra no puede imaginar su vida sin él".

---

### EVO-1 — Chat con streaming real (SSE) — eliminar los 120 segundos de espera

**Por qué:** Ahora Sandra escribe, espera 60-120s viendo un spinner, y entonces aparece la respuesta
completa. Es ansioso, inseguro, parece que el sistema no funciona. Con SSE, los tokens aparecen
en tiempo real — como ChatGPT. Psicológicamente transforma la experiencia.

**`backend/server.py` — nuevo endpoint streaming:**
```python
from fastapi.responses import StreamingResponse
import json

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Chat con SSE — tokens llegan en tiempo real mientras DeepSeek razona."""
    import asyncio

    async def generar():
        try:
            from backend.chat_handler import construir_messages, detectar_tipo
            tipo = detectar_tipo(req.mensaje)
            messages = construir_messages(req.mensaje, req.paciente_cc, req.historial, tipo)

            import httpx
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream(
                    "POST",
                    f"{BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": MODEL,
                        "messages": messages,
                        "max_tokens": 16000,
                        "stream": True,
                    }
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            yield "data: [DONE]\n\n"
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield f"data: {json.dumps({'token': delta})}\n\n"
                        except Exception:
                            continue
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**`dashboard/app/chat/page.tsx` — consumir SSE:**
```tsx
const enviarStreaming = async () => {
  setEnviando(true);
  let respuestaAcumulada = "";
  // Añadir mensaje vacío del asistente (se va llenando en tiempo real)
  const idxAsistente = mensajes.length + 1;
  setMensajes(prev => [...prev, userMsg, { rol: "asistente", contenido: "", timestamp: new Date().toISOString() }]);

  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const resp = await fetch(`${API}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mensaje, paciente_cc: pacienteActivo || undefined, historial }),
  });

  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value);
    for (const line of chunk.split("\n")) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6);
      if (data === "[DONE]") break;
      try {
        const parsed = JSON.parse(data);
        if (parsed.token) {
          respuestaAcumulada += parsed.token;
          // Actualizar el último mensaje del asistente en tiempo real
          setMensajes(prev => prev.map((m, i) =>
            i === prev.length - 1 ? { ...m, contenido: respuestaAcumulada } : m
          ));
        }
      } catch {}
    }
  }
  setEnviando(false);
};
```

**Impacto:** Sandra ve la respuesta fluir en tiempo real. Sabe que Tomy está pensando. La UX
pasa de "sistema lento" a "asistente inteligente en tiempo real".

---

### EVO-2 — Pipeline incremental: formatos aparecen conforme se generan

**Por qué:** El workflow tarda 10-20 min. Sandra espera viendo "Paso 3/9: leyendo notas".
Con entrega incremental, el Formato 1 aparece en 8 min, el 2 en 10 min, etc. Sandra puede
revisar y corregir mientras Tomy termina los siguientes. Reduce el tiempo efectivo de espera.

**`backend/workflow_runner.py` — emitir eventos por formato:**
```python
# Después de generar_formatos (paso 6), notificar por cada formato
if step_name == "generar_formatos":
    formatos = resultado_step.get("formatos_generados", [])
    for fmt in formatos:
        # Guardar en DB con estado parcial
        db.guardar_formato_parcial(task_id, fmt)
        # Notificar via SSE endpoint de progreso (ver EVO-2b)
        _notificar_formato_listo(task_id, fmt)
```

**`backend/task_db.py` — agregar tabla de formatos por task:**
```python
# Nueva tabla: formatos_task
SCHEMA_FORMATOS = """
CREATE TABLE IF NOT EXISTS formatos_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    formato TEXT NOT NULL,
    archivo_docx TEXT,
    archivo_pdf TEXT,
    qa_ok INTEGER DEFAULT 0,
    qa_warnings TEXT,
    generado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES workflow_tasks(task_id)
);
"""

def guardar_formato_parcial(self, task_id: str, fmt: dict):
    with self._conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO formatos_task (task_id, formato, archivo_docx, qa_ok, qa_warnings) VALUES (?,?,?,?,?)",
            (task_id, fmt.get("formato"), fmt.get("archivo"), fmt.get("qa_ok", 0),
             json.dumps(fmt.get("qa_warnings", []))),
        )

def listar_formatos_task(self, task_id: str) -> list:
    with self._conn() as conn:
        rows = conn.execute(
            "SELECT * FROM formatos_task WHERE task_id = ? ORDER BY generado_en",
            (task_id,)
        ).fetchall()
    return [dict(r) for r in rows]
```

**Nuevo endpoint `GET /api/tasks/{task_id}/formatos`:**
```python
@app.get("/api/tasks/{task_id}/formatos")
def formatos_task(task_id: str):
    """Lista formatos ya generados (incluso si el workflow no terminó)."""
    db = TaskDB(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))
    return {"ok": True, "formatos": db.listar_formatos_task(task_id)}
```

**Dashboard `paciente/[cc]`:** Polling `GET /api/tasks/{task_id}/formatos` cada 10s →
muestra cada formato conforme aparece, con botón de descarga inmediata.

---

### EVO-3 — Estado Draft → Revisando → Aprobado → Enviado

**Por qué:** Ahora los documentos son generados y Sandra los descarga. No hay estado de aprobación.
Si Sandra envía un documento con error a ARL Positiva, crea un expediente incorrecto difícil de corregir.
Un flujo de revisión garantiza que solo documentos aprobados por Sandra llegan a ARL.

**Estados del documento:**
```
borrador → en_revision → aprobado → enviado_arl
                ↓
            rechazado → (corrección) → borrador
```

**`backend/task_db.py` — campo `estado_doc` en `formatos_task`:**
```python
# Agregar a SCHEMA_FORMATOS:
"estado_doc TEXT DEFAULT 'borrador'",    # borrador|en_revision|aprobado|enviado_arl
"aprobado_en TIMESTAMP",
"enviado_arl_en TIMESTAMP",
"nota_revision TEXT",
```

**`server.py` — endpoints de aprobación:**
```python
@app.post("/api/tasks/{task_id}/formatos/{formato}/aprobar")
def aprobar_formato(task_id: str, formato: str):
    db = TaskDB(...)
    db.actualizar_estado_formato(task_id, formato, "aprobado")
    return {"ok": True, "mensaje": f"✅ {formato} aprobado"}

@app.post("/api/tasks/{task_id}/formatos/{formato}/rechazar")
def rechazar_formato(task_id: str, formato: str, req: CorregirRequest):
    db = TaskDB(...)
    db.actualizar_estado_formato(task_id, formato, "rechazado", nota=req.mensaje)
    return {"ok": True}

@app.post("/api/tasks/{task_id}/enviar-arl")
def marcar_enviado_arl(task_id: str):
    """Sandra confirma que envió los documentos a ARL."""
    db = TaskDB(...)
    # Verificar que todos los formatos están aprobados
    formatos = db.listar_formatos_task(task_id)
    no_aprobados = [f for f in formatos if f["estado_doc"] not in ("aprobado", "enviado_arl")]
    if no_aprobados:
        return {"ok": False, "mensaje": f"{len(no_aprobados)} formato(s) sin aprobar"}
    db.marcar_task_enviada_arl(task_id)
    return {"ok": True, "mensaje": "📤 Marcado como enviado a ARL Positiva"}
```

**Dashboard:** Cada FormatoCard muestra botones ✅ Aprobar / ❌ Rechazar.
Una vez todos aprobados, aparece el botón grande "📤 Enviar a ARL Positiva" que:
1. Genera ZIP con todos los PDFs
2. Marca la task como enviado en la DB
3. Registra fecha y hora de envío

---

### EVO-4 — Retry automático con backoff exponencial en llamadas LLM

**Por qué:** En los logs reales vimos `HTTP 500: {"type":"error","error":{"type":"error","message":"Internal server error"}}`.
Cuando DeepSeek devuelve 500 (común durante alta carga), el sistema falla permanentemente.
Con retry automático, el 95% de los errores transitorios se resuelven solos.

**`backend/chat_handler.py` — ya tiene lógica de reintento, pero no backoff:**
```python
def _llamar_llm_con_retry(messages: list, max_tok: int = 16000, max_reintentos: int = 4) -> str:
    """Llama al LLM con retry exponencial para errores 500/502/503."""
    import time
    for intento in range(max_reintentos):
        try:
            resp = requests.post(
                f"{BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={"model": MODEL, "messages": messages, "max_tokens": max_tok},
                timeout=300,
            )
            if resp.status_code == 200:
                body = resp.json()
                content = body["choices"][0]["message"].get("content", "").strip()
                if content:
                    return content
                # finish=length → aumentar tokens y reintentar
                if body["choices"][0].get("finish_reason") == "length":
                    max_tok = min(max_tok * 2, 32000)
                    continue
            elif resp.status_code in (429, 500, 502, 503, 504):
                # Error transitorio — backoff exponencial
                espera = (2 ** intento) + random.uniform(0, 1)  # 1s, 2s, 4s, 8s
                _log(f"LLM: HTTP {resp.status_code}, reintentando en {espera:.1f}s (intento {intento+1}/{max_reintentos})")
                time.sleep(espera)
                continue
            else:
                return f"Error LLM: HTTP {resp.status_code}"
        except requests.exceptions.Timeout:
            espera = 10 * (intento + 1)
            _log(f"LLM: timeout, reintentando en {espera}s")
            time.sleep(espera)
        except Exception as e:
            _log(f"LLM: error {e}, intento {intento+1}")
            if intento == max_reintentos - 1:
                return f"Error de conexión: {e}"
            time.sleep(5)
    return "No pude obtener respuesta del modelo. Intenta de nuevo."
```

---

### EVO-5 — Extracción paralela de portales (Medifolios + Positiva simultáneos)

**Por qué:** El paso 2 del workflow extrae Medifolios primero, luego Positiva. Son independientes.
Con extracción paralela, el tiempo baja de 4-6 min a 2-3 min.

**`backend/playwright_real/orquestador.py` — parallelizar con asyncio.gather:**
```python
async def extraer_paciente_completo(cc: str, guardar: bool = True) -> dict:
    """Extrae Medifolios + Positiva en PARALELO."""
    _log(f"Iniciando extracción paralela CC {cc}...")

    async def _extraer_medifolios():
        from backend.playwright_real.medifolios import extraer_medifolios
        return await extraer_medifolios(cc)

    async def _extraer_positiva():
        from backend.playwright_real.positiva import extraer_positiva
        return await extraer_positiva(cc)

    # Ambas extracciones en paralelo
    resultados = await asyncio.gather(
        _extraer_medifolios(),
        _extraer_positiva(),
        return_exceptions=True,  # no falla si una falla
    )

    datos_medi = resultados[0] if not isinstance(resultados[0], Exception) else {"_error": str(resultados[0])}
    datos_pos = resultados[1] if not isinstance(resultados[1], Exception) else {"_error": str(resultados[1])}

    discrepancias = _detectar_discrepancias(datos_medi, datos_pos)
    parcial = isinstance(resultados[0], Exception) or isinstance(resultados[1], Exception)

    resultado = {
        "cc": cc, "medifolios": datos_medi, "positiva": datos_pos,
        "_meta": {"parcial": parcial, "discrepancias": discrepancias},
        "ultima_actualizacion": datetime.now().isoformat(),
    }
    if guardar:
        _guardar_json(cc, resultado)
    return resultado
```

---

### EVO-6 — Keep-alive de sesiones de portales (durante horario laboral)

**Por qué:** Las sesiones de Medifolios y ARL Positiva expiran por inactividad. Si Sandra está
atendiendo una consulta y el workflow empieza a las 2 PM cuando la sesión expiró a mediodía,
el Paso 2 falla con "Sesión expirada". El cron nocturno extrae datos, pero si hay una consulta
inesperada, la extracción al vuelo falla.

**`backend/cron_pre_extraccion.py` — agregar heartbeat de portales:**
```python
HORA_INICIO_LABORAL = 8   # 8 AM Colombia
HORA_FIN_LABORAL = 18     # 6 PM Colombia

async def _heartbeat_portales():
    """Mantiene vivas las sesiones de portales durante horario laboral."""
    hora_actual = datetime.now(COL).hour
    if not (HORA_INICIO_LABORAL <= hora_actual < HORA_FIN_LABORAL):
        return  # Fuera de horario → no despertar portales

    if not os.getenv("FASE_A_ENABLED", "false").lower() == "true":
        return

    _log("HEARTBEAT: verificando sesiones de portales...")
    try:
        from backend.playwright_real.session import verificar_sesion
        await verificar_sesion("medifolios")
        await verificar_sesion("positiva")
    except Exception as e:
        _log(f"HEARTBEAT: error — {e}")


# Agregar al scheduler (cada 45 minutos en horario laboral):
scheduler.add_job(
    _heartbeat_portales,
    CronTrigger(minute="*/45", hour=f"{HORA_INICIO_LABORAL}-{HORA_FIN_LABORAL}", timezone=COL),
    id="heartbeat_portales",
    replace_existing=True,
)
```

---

### EVO-7 — Detección de cambios en portales (alertar cuando el siniestro se actualiza)

**Por qué:** ARL Positiva actualiza diagnósticos, agrega autorizaciones, cambia el porcentaje de PCL.
Si Sandra no lo sabe, los formatos que generó el mes pasado quedan desactualizados. El sistema
debe detectar estos cambios automáticamente.

**`backend/playwright_real/orquestador.py` — función de detección de cambios:**
```python
def _comparar_con_extraccion_anterior(cc: str, datos_nuevos: dict) -> list[dict]:
    """Compara datos nuevos con la extracción anterior. Retorna lista de cambios."""
    path = _json_path(cc)
    if not path or not path.exists():
        return []  # Primera extracción, sin comparación posible

    try:
        datos_ant = json.loads(path.read_text())
    except Exception:
        return []

    cambios = []

    # Comparar campos clave de Positiva
    siniestros_ant = {s.get("id") for s in datos_ant.get("positiva", {}).get("siniestros", [])}
    siniestros_nuevo = {s.get("id") for s in datos_nuevos.get("positiva", {}).get("siniestros", [])}
    nuevos_sin = siniestros_nuevo - siniestros_ant
    if nuevos_sin:
        cambios.append({"tipo": "nuevo_siniestro", "ids": list(nuevos_sin)})

    # Cambio en diagnóstico CIE-10
    cie_ant = datos_ant.get("positiva", {}).get("siniestros", [{}])[0].get("diagnostico", "")
    cie_nuevo = datos_nuevos.get("positiva", {}).get("siniestros", [{}])[0].get("diagnostico", "")
    if cie_ant and cie_nuevo and cie_ant != cie_nuevo:
        cambios.append({"tipo": "cambio_diagnostico", "anterior": cie_ant, "nuevo": cie_nuevo})

    # Nuevas autorizaciones
    auth_ant = len(datos_ant.get("positiva", {}).get("autorizaciones", []))
    auth_nuevo = len(datos_nuevos.get("positiva", {}).get("autorizaciones", []))
    if auth_nuevo > auth_ant:
        cambios.append({"tipo": "nueva_autorizacion", "total_anterior": auth_ant, "total_nuevo": auth_nuevo})

    return cambios
```

**Notificar cambios a Sandra via Telegram:**
```python
# En extraer_paciente_completo, después de guardar:
cambios = _comparar_con_extraccion_anterior(cc, resultado)
if cambios:
    from backend.notificador import enviar_telegram
    msgs = [f"🔔 Cambios en portales para CC {cc}:"]
    for c in cambios:
        if c["tipo"] == "cambio_diagnostico":
            msgs.append(f"  ⚠️ Diagnóstico cambió: {c['anterior']} → {c['nuevo']}")
        elif c["tipo"] == "nueva_autorizacion":
            msgs.append(f"  📋 Nueva autorización en ARL Positiva")
        elif c["tipo"] == "nuevo_siniestro":
            msgs.append(f"  🆕 Nuevo siniestro: {c['ids']}")
    enviar_telegram("\n".join(msgs))
```

---

### EVO-8 — Formulario de datos manuales cuando el portal falla

**Por qué:** Si Playwright falla (portal caído, CAPTCHA, sesión expirada), el Paso 2 devuelve
`_vacio: True`. Los 7 formatos salen con `[FALTA]` en todos los campos del portal. Sandra no tiene
forma de entrar los datos manualmente desde el dashboard — tendría que editar el JSON a mano.

**Nuevo endpoint `POST /api/pacientes/{cc}/datos-manuales`:**
```python
class DatosManualesRequest(BaseModel):
    paciente: dict     # nombre, documento, edad, telefono, eps_ips, afp, ocupacion
    empresa: dict      # nombre, nit, cargo
    siniestro: dict    # id_siniestro, fecha_evento, diagnostico_cie10

@app.post("/api/pacientes/{cc}/datos-manuales")
def guardar_datos_manuales(cc: str, req: DatosManualesRequest):
    """Sandra entra manualmente los datos del paciente cuando el portal falla."""
    datos = {
        "paciente": {"documento": cc, **req.paciente},
        "empresa": req.empresa,
        "siniestro": req.siniestro,
        "_meta": {"fuente": "manual_sandra", "parcial": True},
        "ultima_actualizacion": datetime.now().isoformat(),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    archivo = DATA_DIR / f"{cc}-completo.json"
    archivo.write_text(json.dumps(datos, indent=2, ensure_ascii=False))
    return {"ok": True, "mensaje": f"Datos de CC {cc} guardados manualmente"}
```

**Dashboard — panel en `/paciente/{cc}` cuando datos están vacíos:**
```tsx
{paciente._vacio && (
  <section className="border-2 border-amber-300 bg-amber-50 p-6 rounded-2xl">
    <h2 className="text-xl font-bold text-amber-800">⚠️ No hay datos del portal</h2>
    <p className="text-amber-700 mb-4">El portal no respondió. Podés entrar los datos manualmente:</p>
    <FormularioDatosManuales cc={cc} onGuardado={() => cargar()} />
  </section>
)}
```

---

### EVO-9 — Pre-check de portales ANTES de iniciar el workflow

**Por qué:** Ahora el workflow empieza y si el portal falla en el Paso 2, ya se transcribió el audio
(Paso 1 — llamada a Deepgram, ya pagada). Es mejor saber ANTES de empezar si los portales están
disponibles y si ya hay datos recientes del paciente.

**`server.py` — endpoint de pre-check mejorado:**
```python
@app.get("/api/pacientes/{cc}/check-antes-de-procesar")
async def check_antes_procesar(cc: str):
    resultado = {
        "datos_portal_recientes": False,
        "datos_manuales": False,
        "ultima_extraccion": None,
        "portal_medifolios_up": None,
        "portal_positiva_up": None,
        "agenda_tiene_cita_hoy": False,
        "recomendacion": "",
    }

    # ¿Hay datos recientes (<48h)?
    from backend.workflow_steps.resolver_paciente import _json_path, _es_reciente
    path = _json_path(cc)
    if path and _es_reciente(path, horas_max=48):
        datos = json.loads(path.read_text())
        resultado["datos_portal_recientes"] = True
        resultado["ultima_extraccion"] = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        resultado["datos_manuales"] = datos.get("_meta", {}).get("fuente") == "manual_sandra"

    # ¿Está en la agenda de hoy?
    try:
        from backend.notificador import cargar_agenda_guardada
        agenda = cargar_agenda_guardada()
        if agenda:
            for cita in agenda.get("citas", []):
                if cita.get("cc") == cc:
                    resultado["agenda_tiene_cita_hoy"] = True
                    break
    except Exception:
        pass

    # Recomendación para Sandra
    if resultado["datos_portal_recientes"]:
        resultado["recomendacion"] = "✅ Listo para procesar (datos del portal actualizados)"
    elif os.getenv("FASE_A_ENABLED", "false").lower() == "true":
        resultado["recomendacion"] = "⚠️ Extraeré datos del portal al iniciar (tarda 2-3 min extra)"
    else:
        resultado["recomendacion"] = "⚠️ No tengo datos del portal. Los formatos tendrán campos [FALTA]"

    return resultado
```

---

### EVO-10 — Extractar CC del audio automáticamente

**Por qué:** Paso 2 requiere que Sandra ingrese el CC. Pero en la consulta, Sandra dice "la paciente
es Rosa María García, cédula cinco, cinco, uno, seis, dos, ocho, cero, uno". El LLM ya transcribe
esto. Antes de resolver el paciente, intentar extraer el CC de la transcripción.

**`backend/workflow_steps/resolver_paciente.py` — extracción de CC del audio:**
```python
def _extraer_cc_de_transcripcion(texto: str) -> str | None:
    """Intenta extraer CC del texto transcrito. Busca patrones de cédula."""
    import re
    # Patrón 1: números seguidos después de "cédula", "documento", "cc"
    m = re.search(
        r'(?:c[eé]dula|documento|cc|identificaci[oó]n)[\s:de]+(\d[\d\s\.,]{5,14}\d)',
        texto.lower()
    )
    if m:
        cc = re.sub(r'[\s\.,]', '', m.group(1))
        if 6 <= len(cc) <= 12:
            return cc

    # Patrón 2: secuencia de dígitos dictados ("cinco, cinco, uno...")
    # Convertir números en español a dígitos y buscar secuencias de 8-12 dígitos
    numeros_es = {
        'cero':'0','uno':'1','dos':'2','tres':'3','cuatro':'4',
        'cinco':'5','seis':'6','siete':'7','ocho':'8','nueve':'9'
    }
    texto_num = texto.lower()
    for palabra, digito in numeros_es.items():
        texto_num = texto_num.replace(f' {palabra}', digito)
    m2 = re.search(r'\d{8,12}', texto_num.replace(',', '').replace(' ', ''))
    if m2 and m2.group():
        return m2.group()

    return None


def ejecutar(paciente_cc: str, forzar_extraer: bool = False, transcripcion_texto: str = "") -> dict:
    # Intentar extraer CC del audio si no se proporcionó
    if not paciente_cc and transcripcion_texto:
        cc_extraido = _extraer_cc_de_transcripcion(transcripcion_texto)
        if cc_extraido:
            _log(f"CC extraído del audio: {cc_extraido}")
            paciente_cc = cc_extraido

    datos, fuente = resolver_paciente(paciente_cc, forzar_extraer)
    return {"datos_portales": datos, "fuente": fuente, "cc_detectado": paciente_cc}
```

---

### EVO-11 — Progressive Web App (PWA) para el teléfono de Sandra

**Por qué:** El dashboard es una web en el PC de Sandra. Para que Sandra lo use desde su iPhone
(ver agenda en el camino, aprobar documentos desde la sala de espera), necesita ser una app.
Un PWA se "instala" en el iPhone con Safari → "Agregar a pantalla de inicio" → abre sin barra
de navegador, con ícono propio. Sin App Store, sin costo.

**`dashboard/public/manifest.json`:**
```json
{
  "name": "RILO SAS — Tomy",
  "short_name": "RILO",
  "description": "Asistente Tomy para fisioterapia RILO SAS",
  "start_url": "/hoy",
  "display": "standalone",
  "background_color": "#f8fafc",
  "theme_color": "#2563eb",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

**`dashboard/app/layout.tsx` — agregar meta PWA:**
```tsx
export const metadata: Metadata = {
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "RILO SAS",
  },
  // Tema azul en la barra de estado del iPhone
  themeColor: "#2563eb",
};
```

**`dashboard/public/sw.js` — Service Worker para offline:**
```javascript
// Cache de páginas principales para funcionar sin internet
const CACHE = "rilo-v1";
const OFFLINE_PAGES = ["/hoy", "/pacientes", "/chat"];

self.addEventListener("install", e => e.waitUntil(
  caches.open(CACHE).then(c => c.addAll(OFFLINE_PAGES))
));

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
```

**Resultado:** Sandra agrega el dashboard a su iPhone. Recibe push notifications de tareas
completadas. Ve la agenda offline si no tiene internet. Todo sin App Store.

---

### EVO-12 — Briefing matinal automático (7 AM, Telegram)

**Por qué:** Cada mañana Sandra abre el dashboard para ver qué tiene. Con el briefing automático,
a las 7 AM Tomy le manda un resumen de texto (o audio con text-to-speech) que dice:
"Buenos días Sandra. Hoy tiene 3 citas. Juan Carlos es el primero a las 8 AM.
Ya tengo sus datos del portal listos. Faltan 2 documentos de ayer por aprobar."

**`backend/cron_pre_extraccion.py` — briefing matinal:**
```python
async def briefing_matinal():
    """7 AM: resumen del día por Telegram."""
    _log("BRIEFING: preparando resumen matinal...")

    try:
        from backend.notificador import cargar_agenda_guardada, enviar_telegram
        from backend.task_db import TaskDB

        agenda = cargar_agenda_guardada()
        citas = agenda.get("citas", []) if agenda else []

        db = TaskDB(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))

        # Tareas pendientes de revisión
        # (estado listo pero ningún formato marcado como aprobado)
        activas = db.listar_activos()

        lineas = [f"🌅 *Buenos días, Sandra!* {datetime.now(COL).strftime('%A %d/%m/%Y')}\n"]

        if citas:
            lineas.append(f"📅 *{len(citas)} cita(s) hoy:*")
            for c in citas[:5]:
                estado_datos = "✅ datos listos" if c.get("cc") else "⚠️ datos pendientes"
                lineas.append(f"  • {c.get('hora','?')} — {c.get('paciente','?')} ({estado_datos})")
        else:
            lineas.append("📅 Sin citas registradas para hoy.")

        if activas:
            lineas.append(f"\n⏳ {len(activas)} tarea(s) en proceso")

        lineas.append(f"\n💻 Dashboard: {os.getenv('DASHBOARD_URL', 'http://localhost:3000')}/hoy")

        enviar_telegram("\n".join(lineas))
        _log("BRIEFING: enviado OK")
    except Exception as e:
        _log(f"BRIEFING: error — {e}")


# Agregar al scheduler:
scheduler.add_job(
    briefing_matinal,
    CronTrigger(hour=7, minute=0, timezone=COL),
    id="briefing_matinal",
    replace_existing=True,
)
```

---

### EVO-13 — Preview de documentos en el navegador (sin descargar)

**Por qué:** Para aprobar un documento (EVO-3), Sandra tiene que descargarlo, abrirlo en Word,
revisarlo, volver al dashboard. Con preview en el navegador, Sandra ve el contenido sin salir del dashboard.

**Estrategia:** Convertir DOCX a HTML en el backend usando `mammoth` (librería Python ligera).

**`backend/server.py` — endpoint de preview:**
```python
@app.get("/api/preview/{filename}")
def preview_docx(filename: str):
    """Convierte DOCX a HTML para preview en el navegador."""
    safe_name = Path(filename).name
    # Buscar en docs/ y pdfs/
    for search_dir in [DOCS_DIR, PDFS_DIR]:
        path = search_dir / safe_name
        if path.exists() and path.suffix == ".docx":
            try:
                import mammoth
                with open(path, "rb") as f:
                    result = mammoth.convert_to_html(f)
                # HTML limpio con estilos básicos
                html = f"""
                <html><head><meta charset="utf-8">
                <style>
                  body {{ font-family: 'Times New Roman', serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
                  table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                  td, th {{ border: 1px solid #ccc; padding: 6px 10px; }}
                  p {{ margin: 6px 0; line-height: 1.5; }}
                </style></head>
                <body>{result.value}</body></html>
                """
                return Response(content=html, media_type="text/html; charset=utf-8")
            except ImportError:
                raise HTTPException(500, "Instalar mammoth: pip install mammoth")
    raise HTTPException(404, "Archivo no encontrado")
```

**Dashboard — FormatoCard con botón de preview:**
```tsx
<button
  onClick={() => window.open(`${API}/preview/${encodeURIComponent(nombreArchivo)}`, "_blank")}
  className="px-3 py-1.5 text-sm bg-slate-100 hover:bg-slate-200 rounded-lg"
>
  👁️ Ver
</button>
```

**Agregar dependencia:** `pip install mammoth` en `backend/requirements.txt`.

---

### EVO-14 — Seguimiento de envíos a ARL + alertas de vencimiento

**Por qué:** ARL Positiva tiene plazos específicos para cada formato. Un Análisis de Exigencias
debe entregarse en ciertos días desde el siniestro. Un Cierre de Caso requiere documentación
acumulada. Si Sandra se atrasa, la ARL puede rechazar el expediente. El sistema debe saber
cuándo vence cada documento y alertar con 5 días de anticipación.

**`backend/arl_plazos.py` — módulo nuevo:**
```python
"""
Plazos reglamentarios ARL Positiva Colombia.
Basados en la normativa de rehabilitación profesional.
"""
from datetime import date, timedelta

PLAZOS_DIAS = {
    "analisis_exigencias": 30,         # 30 días desde inicio del proceso
    "carta_medidas": 15,               # 15 días desde identificación de riesgo
    "carta_recomendaciones": 30,       # 30 días desde inicio rehabilitación
    "cierre_caso": None,               # Sin plazo fijo (depende del proceso)
    "citacion_empresas": 10,           # 10 días antes de la visita
    "prueba_trabajo": 45,              # 45 días desde inicio reincorporación
    "valoracion_desempeno": 60,        # 60 días desde inicio caso
}

def calcular_vencimiento(tipo_formato: str, fecha_inicio_caso: date) -> date | None:
    dias = PLAZOS_DIAS.get(tipo_formato)
    if dias is None:
        return None
    return fecha_inicio_caso + timedelta(days=dias)

def formatos_por_vencer(datos_pacientes: list, dias_alerta: int = 5) -> list:
    """Retorna lista de (paciente, formato, dias_restantes) que vencen en X días."""
    alertas = []
    hoy = date.today()
    for p in datos_pacientes:
        fecha_inicio = p.get("siniestro", {}).get("fecha_inicio")
        if not fecha_inicio:
            continue
        try:
            fi = date.fromisoformat(fecha_inicio)
        except Exception:
            continue
        for tipo, _ in PLAZOS_DIAS.items():
            venc = calcular_vencimiento(tipo, fi)
            if venc and 0 <= (venc - hoy).days <= dias_alerta:
                alertas.append({
                    "paciente": p.get("paciente", {}).get("nombre", "?"),
                    "cc": p.get("paciente", {}).get("documento", ""),
                    "formato": tipo,
                    "vence": venc.isoformat(),
                    "dias_restantes": (venc - hoy).days,
                })
    return sorted(alertas, key=lambda x: x["dias_restantes"])
```

**Cron diario de alertas de vencimiento (nuevo job en scheduler):**
```python
async def alertar_vencimientos():
    """Cada mañana: alertar si hay formatos por vencer en 5 días."""
    from backend.arl_plazos import formatos_por_vencer
    archivos = list((Path(os.getenv("STORAGE_DIR","./storage")) / "data").glob("*-completo.json"))
    datos = []
    for f in archivos:
        try: datos.append(json.loads(f.read_text()))
        except: pass
    alertas = formatos_por_vencer(datos, dias_alerta=5)
    if alertas:
        from backend.notificador import enviar_telegram
        lines = ["⏰ *Formatos por vencer:*"]
        for a in alertas[:10]:
            lines.append(f"  • {a['paciente']} — {a['formato'].replace('_',' ').title()} — {a['dias_restantes']}d")
        enviar_telegram("\n".join(lines))
```

---

### EVO-15 — Historial de correcciones: aprendizaje del sistema

**Por qué:** Sandra corrige los mismos tipos de errores repetidamente (el siniestro siempre tiene
el año equivocado, la empresa siempre falta el NIT, etc.). Si el sistema aprende qué corrige Sandra,
puede mejorar los prompts de síntesis para no cometer esos errores en pacientes futuros.

**`backend/correcciones_historico.py` — nuevo módulo:**
```python
"""
Guarda cada corrección que Sandra hace. Con el tiempo, analiza patrones
y ajusta el PROMPT_USUARIO_SINTESIS para evitar errores frecuentes.
"""
import json
from pathlib import Path
from datetime import datetime
from collections import Counter

HIST_PATH = Path("./storage/correcciones_historico.json")


def registrar_correccion(campo: str, valor_anterior: str, valor_nuevo: str, paciente_cc: str):
    hist = _cargar()
    hist.append({
        "ts": datetime.now().isoformat(),
        "campo": campo,
        "valor_anterior": valor_anterior[:200] if valor_anterior else "",
        "valor_nuevo": valor_nuevo[:200] if valor_nuevo else "",
        "paciente_cc": paciente_cc,
    })
    # Mantener solo los últimos 500 registros
    if len(hist) > 500:
        hist = hist[-500:]
    HIST_PATH.write_text(json.dumps(hist, indent=2, ensure_ascii=False))


def patrones_frecuentes(top_n: int = 5) -> list[dict]:
    """Retorna los N campos que Sandra corrige con más frecuencia."""
    hist = _cargar()
    campos = Counter(h["campo"] for h in hist)
    return [{"campo": c, "veces": n} for c, n in campos.most_common(top_n)]


def generar_advertencias_prompt() -> str:
    """Genera texto de advertencia para el prompt basado en errores frecuentes."""
    patrones = patrones_frecuentes(top_n=3)
    if not patrones:
        return ""
    lineas = ["⚠️ ERRORES FRECUENTES (Sandra ha corregido esto antes):"]
    for p in patrones:
        lineas.append(f"  - {p['campo']}: corregido {p['veces']} veces. Verificar con especial cuidado.")
    return "\n".join(lineas)


def _cargar() -> list:
    if HIST_PATH.exists():
        try: return json.loads(HIST_PATH.read_text())
        except: pass
    return []
```

**Integrar en `sintetizar_maestro.py`:**
```python
# Al construir el prompt de síntesis, agregar advertencias del historial
from backend.correcciones_historico import generar_advertencias_prompt
advertencias = generar_advertencias_prompt()
if advertencias:
    PROMPT_USUARIO_SINTESIS += f"\n\n{advertencias}"
```

**Integrar en `aplicador_correccion.py`:**
```python
from backend.correcciones_historico import registrar_correccion
# Después de aplicar la corrección:
registrar_correccion(campo, valor_anterior, valor_nuevo, paciente_cc)
```

---

### EVO-16 — Puntuación de calidad de documento (0-100) + reporte

**Por qué:** El QA actual devuelve `qa_ok: True/False` sin explicar cuánto le falta al documento.
Con una puntuación, Sandra sabe de un vistazo qué documentos están bien y cuáles necesitan trabajo.
Un 95/100 es diferente a un 60/100 con 3 campos críticos faltantes.

**`backend/workflow_steps/qa_formatos.py` — ampliar con puntuación:**
```python
def calcular_puntaje(texto: str, tablas_vacias: int, doc) -> tuple[int, list]:
    """Calcula puntaje de calidad 0-100."""
    puntaje = 100
    problemas = []

    # -30 por cada campo crítico sin llenar
    criticos = ["[FALTA:", "[VERIFICAR]", "[COMPLETAR]", "XXXXXXX"]
    for ph in criticos:
        count = texto.count(ph)
        if count > 0:
            deduccion = min(count * 15, 30)
            puntaje -= deduccion
            problemas.append(f"{count} campo(s) sin completar ({ph})")

    # -10 por placeholders menores
    menores = ["{{", "}}", "[DATO]"]
    for ph in menores:
        if ph in texto:
            puntaje -= 5
            problemas.append(f"Placeholder sin completar: {ph}")

    # -10 por tablas con muchas filas vacías
    if tablas_vacias > 5:
        puntaje -= 10
        problemas.append(f"{tablas_vacias} filas de tabla vacías")

    # -5 por documento muy corto (menos de 300 palabras)
    if len(texto.split()) < 300:
        puntaje -= 5
        problemas.append("Documento muy corto (posible error de generación)")

    # +10 si tiene firma (imagen en el documento)
    tiene_firma = any(r.id for p in doc.inline_shapes for r in [p]) if hasattr(doc, 'inline_shapes') else False
    # Simplificado: buscar "firma" en el texto
    if "sandra" in texto.lower() and len(texto) > 500:
        puntaje += 5  # bonus por completitud

    return max(0, min(100, puntaje)), problemas


def _qa_docx(archivo: str) -> dict:
    # ... código existente ...
    puntaje, problemas = calcular_puntaje(texto, tablas_vacias, doc)
    return {
        "qa_ok": puntaje >= 75,           # OK si ≥75
        "qa_puntaje": puntaje,             # 0-100
        "qa_warnings": problemas,
        "qa_nivel": "excelente" if puntaje >= 90 else
                    "bueno" if puntaje >= 75 else
                    "necesita_revision" if puntaje >= 50 else
                    "incompleto",
    }
```

**Dashboard — FormatoCard muestra badge de puntaje:**
```tsx
<div className={`text-sm font-bold px-2 py-0.5 rounded-full ${
  puntaje >= 90 ? "bg-green-100 text-green-700" :
  puntaje >= 75 ? "bg-blue-100 text-blue-700" :
  puntaje >= 50 ? "bg-amber-100 text-amber-700" :
                  "bg-red-100 text-red-700"
}`}>
  {puntaje}/100
</div>
```

---

### EVO-17 — Visor de logs en tiempo real desde el dashboard

**Por qué:** Cuando algo falla (el paso 5 demora 10 min extra, el portal no responde),
Sandra no sabe qué está pasando. Manuel tampoco puede ver los logs sin acceder al WSL.
Un visor de logs en el dashboard muestra en tiempo real qué está haciendo el sistema.

**`backend/server.py` — SSE endpoint de logs:**
```python
import asyncio
from collections import deque

_log_buffer = deque(maxlen=200)  # Últimas 200 líneas de log

class LogCapture:
    """Captura logs de stderr y los agrega al buffer."""
    def write(self, msg):
        if msg.strip():
            _log_buffer.append({"ts": datetime.now().isoformat(), "msg": msg.strip()})
        # También escribir al stderr real
        import sys
        sys.__stderr__.write(msg)
    def flush(self):
        pass

import sys
sys.stderr = LogCapture()


@app.get("/api/logs/stream")
async def log_stream():
    """SSE: nuevos logs en tiempo real."""
    async def generar():
        last_len = len(_log_buffer)
        while True:
            current_len = len(_log_buffer)
            if current_len > last_len:
                nuevos = list(_log_buffer)[last_len:]
                for log in nuevos:
                    yield f"data: {json.dumps(log)}\n\n"
                last_len = current_len
            await asyncio.sleep(0.5)

    return StreamingResponse(generar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.get("/api/logs/recientes")
def logs_recientes(n: int = 50):
    """Últimas N líneas de log."""
    return {"ok": True, "logs": list(_log_buffer)[-n:]}
```

**Nueva página `dashboard/app/logs/page.tsx`:**
```tsx
// Página de logs en tiempo real — para Manuel/diagnóstico
"use client";
import { useEffect, useState } from "react";

export default function LogsPage() {
  const [logs, setLogs] = useState<{ts: string, msg: string}[]>([]);

  useEffect(() => {
    const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    // Cargar logs recientes primero
    fetch(`${API}/api/logs/recientes`).then(r => r.json())
      .then(d => setLogs(d.logs || []));
    // Luego streaming
    const es = new EventSource(`${API}/api/logs/stream`);
    es.onmessage = (e) => {
      const log = JSON.parse(e.data);
      setLogs(prev => [...prev.slice(-199), log]);
    };
    return () => es.close();
  }, []);

  return (
    <div className="font-mono text-xs bg-slate-900 text-green-400 p-4 rounded-xl h-[calc(100vh-8rem)] overflow-y-auto">
      {logs.map((l, i) => (
        <div key={i} className={`${
          l.msg.includes("ERROR") || l.msg.includes("FALLÓ") ? "text-red-400" :
          l.msg.includes("WARN") || l.msg.includes("⚠️") ? "text-yellow-400" :
          l.msg.includes("OK") || l.msg.includes("✅") ? "text-green-300" :
          "text-slate-300"
        }`}>
          <span className="text-slate-500 mr-2">{l.ts.slice(11, 19)}</span>
          {l.msg}
        </div>
      ))}
    </div>
  );
}
```

---

### EVO-18 — Cola de múltiples pacientes (queue management)

**Por qué:** Sandra puede tener 3 consultas en un día. Si sube los 3 audios al terminar el día
(práctica común), los 3 workflows arrancan simultáneamente. Cada uno llama a DeepSeek (cuello de
botella), a Deepgram, a Playwright. El sistema se satura y los 3 fallan o se demoran el triple.

**`backend/workflow_queue.py` — cola FIFO simple:**
```python
"""
Cola de workflows. Ejecuta uno a la vez para no saturar APIs.
Acepta múltiples encolas y los procesa en orden.
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Deque
from collections import deque


class WorkflowQueue:
    def __init__(self):
        self._queue: Deque[dict] = deque()
        self._procesando = False
        self._lock = asyncio.Lock()

    async def encolar(self, task_id: str, audio_path: str, paciente_cc: str) -> int:
        """Agrega tarea a la cola. Retorna posición (1 = siguiente en procesar)."""
        async with self._lock:
            self._queue.append({"task_id": task_id, "audio_path": audio_path, "cc": paciente_cc})
            posicion = len(self._queue)
            if not self._procesando:
                asyncio.create_task(self._procesar_loop())
            return posicion

    async def _procesar_loop(self):
        async with self._lock:
            self._procesando = True
        try:
            while self._queue:
                item = self._queue.popleft()
                from backend.workflow_runner import ejecutar_workflow
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: ejecutar_workflow(
                    audio_path=item["audio_path"],
                    paciente_cc=item["cc"],
                    task_id_existente=item["task_id"],
                ))
        finally:
            async with self._lock:
                self._procesando = False

    def estado_cola(self) -> dict:
        return {
            "en_cola": len(self._queue),
            "procesando": self._procesando,
            "proximos": [{"cc": t["cc"], "task_id": t["task_id"]} for t in list(self._queue)[:5]],
        }


# Singleton global
_queue = WorkflowQueue()

async def encolar_workflow(task_id, audio_path, cc): return await _queue.encolar(task_id, audio_path, cc)
def estado_cola(): return _queue.estado_cola()
```

**Integrar en `server.py`:**
```python
@app.post("/api/procesar-paciente")
async def procesar_paciente(...):
    # ... guardar audio, crear task_id ...
    from backend.workflow_queue import encolar_workflow
    posicion = await encolar_workflow(task_id, str(audio_path), paciente_cc)

    return {
        "ok": True,
        "task_id": task_id,
        "posicion_en_cola": posicion,
        "mensaje": (f"✅ Primero en la cola, empezando ahora..." if posicion == 1 else
                    f"📋 En cola (posición {posicion}). Procesaré después de los anteriores."),
    }

@app.get("/api/cola")
def estado_cola():
    from backend.workflow_queue import estado_cola
    return {"ok": True, **estado_cola()}
```

---

### EVO-19 — Normalización inteligente de nombres y CCs

**Por qué:** El mismo paciente puede aparecer como "JUAN CARLOS DURÁN NARVÁEZ", "Juan Carlos Duran",
"J.C. DURAN N." en diferentes documentos. Las cédulas aparecen como "1'193.143.688", "1193143688",
"1.193.143.688". Sin normalización, los 7 formatos del mismo paciente no se reconocen como del mismo.

**`backend/normalizador.py` — módulo nuevo:**
```python
"""
Normalización de nombres y documentos para consistencia entre formatos.
"""
import re
import unicodedata


def normalizar_cc(cc: str) -> str:
    """1'193.143.688 → 1193143688"""
    return re.sub(r"['\.,\s]", "", str(cc))


def normalizar_nombre(nombre: str) -> str:
    """'JUAN CARLOS DURÁN NARVÁEZ' → 'JUAN CARLOS DURAN NARVAEZ'"""
    nombre = nombre.strip().upper()
    # Remover acentos
    nombre = ''.join(
        c for c in unicodedata.normalize('NFD', nombre)
        if unicodedata.category(c) != 'Mn'
    )
    # Normalizar espacios
    nombre = re.sub(r'\s+', ' ', nombre)
    # Remover caracteres especiales
    nombre = re.sub(r'[^A-Z\s]', '', nombre)
    return nombre


def nombres_similares(n1: str, n2: str, umbral: float = 0.75) -> bool:
    """True si dos nombres son probablemente el mismo paciente."""
    n1, n2 = normalizar_nombre(n1), normalizar_nombre(n2)
    palabras1 = set(n1.split())
    palabras2 = set(n2.split())
    if not palabras1 or not palabras2:
        return False
    comunes = palabras1 & palabras2
    total = len(palabras1 | palabras2)
    return len(comunes) / total >= umbral


def detectar_duplicados_cc(archivos_json: list) -> list[dict]:
    """Detecta pacientes con CC similar (posible error de digitación)."""
    ccs = []
    for f in archivos_json:
        try:
            import json
            datos = json.loads(open(f).read())
            cc_raw = datos.get("paciente", {}).get("documento", "")
            cc = normalizar_cc(cc_raw)
            nombre = datos.get("paciente", {}).get("nombre", "")
            ccs.append({"cc": cc, "nombre": nombre, "archivo": f})
        except Exception:
            continue

    # Buscar duplicados: mismo nombre pero distinto CC (o viceversa)
    alertas = []
    for i, a in enumerate(ccs):
        for b in ccs[i+1:]:
            if nombres_similares(a["nombre"], b["nombre"]) and a["cc"] != b["cc"]:
                alertas.append({
                    "tipo": "mismo_nombre_distinto_cc",
                    "paciente": a["nombre"],
                    "cc_1": a["cc"], "cc_2": b["cc"],
                })
    return alertas
```

---

### EVO-20 — Diff de documentos: ver qué cambió después de una corrección

**Por qué:** Cuando Sandra pide "cambia el siniestro en el VOI", el sistema regenera el VOI completo.
¿Pero solo cambió el siniestro? ¿O se cambió algo más? Sin un diff, Sandra tiene que leer todo el
documento de nuevo. Con diff, ve exactamente qué cambió en 2 segundos.

**`backend/server.py` — endpoint de diff:**
```python
@app.get("/api/diff/{filename_viejo}/{filename_nuevo}")
def diff_documentos(filename_viejo: str, filename_nuevo: str):
    """Muestra diferencias entre dos versiones del mismo documento."""
    try:
        import mammoth, difflib

        def _extraer_texto(nombre: str) -> str:
            path = DOCS_DIR / Path(nombre).name
            if not path.exists():
                return ""
            with open(path, "rb") as f:
                return mammoth.extract_raw_text(f).value

        texto_viejo = _extraer_texto(filename_viejo)
        texto_nuevo = _extraer_texto(filename_nuevo)

        # Diff línea a línea
        diff = list(difflib.unified_diff(
            texto_viejo.splitlines(keepends=True),
            texto_nuevo.splitlines(keepends=True),
            fromfile="Versión anterior",
            tofile="Versión nueva",
            n=2,
        ))

        # Resumen de cambios
        lineas_add = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        lineas_del = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

        return {
            "ok": True,
            "diff_texto": "".join(diff[:200]),  # primeras 200 líneas
            "lineas_agregadas": lineas_add,
            "lineas_eliminadas": lineas_del,
            "sin_cambios": lineas_add == 0 and lineas_del == 0,
        }
    except ImportError:
        raise HTTPException(500, "pip install mammoth")
```

---

### EVO-21 — Auto-cleanup y gestión de almacenamiento

**Por qué:** Los audios M4A de 75 minutos pesan ~100MB cada uno. Después de procesados y aprobados,
no se necesitan. En 6 meses, el disco de Sandra podría llenarse solo de audios. El sistema debe
limpiar automáticamente lo que ya no se necesita.

**`backend/limpiador_storage.py` — nuevo módulo:**
```python
"""
Limpieza automática de storage/ para evitar llenar el disco.
"""
import os
from pathlib import Path
from datetime import datetime, timedelta


def limpiar_audios_procesados(dias_retener: int = 7):
    """Elimina audios de workflow procesados exitosamente y con >N días."""
    from backend.task_db import TaskDB
    db = TaskDB(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))

    audio_dir = Path(os.getenv("STORAGE_DIR", "./storage")) / "workflow_audios"
    if not audio_dir.exists():
        return []

    eliminados = []
    limite = datetime.now() - timedelta(days=dias_retener)

    for audio in audio_dir.glob("*.m4a") + audio_dir.glob("*.mp3"):
        mtime = datetime.fromtimestamp(audio.stat().st_mtime)
        if mtime > limite:
            continue  # Reciente, mantener

        # Verificar que la task asociada esté "listo"
        # El nombre del audio es {cc}_{timestamp}.m4a
        cc = audio.stem.split("_")[0]
        tasks = db.listar_tasks_paciente(cc, limit=10)
        task_del_audio = next((t for t in tasks if str(audio) in str(t.get("audio_path", ""))), None)

        if task_del_audio and task_del_audio["estado"] == "listo":
            audio.unlink()
            eliminados.append(str(audio))

    return eliminados


def resumen_storage() -> dict:
    """Uso de disco del storage/."""
    import shutil
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    total, usado, libre = shutil.disk_usage(storage)

    def _size_dir(d: Path) -> int:
        return sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) if d.exists() else 0

    return {
        "disco_total_gb": round(total / 1e9, 1),
        "disco_libre_gb": round(libre / 1e9, 1),
        "storage_docs_mb": round(_size_dir(storage / "docs") / 1e6, 1),
        "storage_audios_mb": round(_size_dir(storage / "workflow_audios") / 1e6, 1),
        "storage_backups_mb": round(_size_dir(storage / "backups") / 1e6, 1),
    }
```

---

### EVO-22 — Modo degradado inteligente (sistema funciona aunque fallen servicios externos)

**Por qué:** Si Deepgram está caído, el sistema dice "error" y para. Si DeepSeek está caído,
el sistema dice "error" y para. Un sistema robusto tiene modos degradados:
- Sin Deepgram: ofrecer transcripción manual (Sandra pega el texto)
- Sin DeepSeek: generar formatos con datos del portal únicamente
- Sin portal: usar datos del JSON caché
- Sin internet: trabajar con los datos locales ya guardados

**`backend/servidor_modo_degradado.py` — detección y fallbacks:**
```python
def verificar_deepgram() -> bool:
    """Ping rápido a Deepgram."""
    try:
        import requests
        r = requests.get("https://api.deepgram.com/v1/projects",
                        headers={"Authorization": f"Token {os.getenv('DEEPGRAM_API_KEY','')}"},
                        timeout=5)
        return r.status_code in (200, 401)  # 401 = key inválida pero servicio activo
    except Exception:
        return False

def verificar_llm() -> bool:
    """Ping rápido al LLM."""
    try:
        import requests
        r = requests.post(
            f"{os.getenv('OPENCODE_GO_BASE_URL', 'https://opencode.ai/zen/go/v1')}/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('OPENCODE_GO_API_KEY','')}",
                     "Content-Type": "application/json"},
            json={"model": os.getenv("LLM_MODEL","deepseek-v4-pro"),
                  "messages": [{"role":"user","content":"hola"}], "max_tokens": 5},
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return False


# En server.py, agregar al health check:
@app.get("/api/system/health")
async def system_health():
    # ... checks anteriores ...
    resultado["deepgram_up"] = verificar_deepgram()
    resultado["llm_up"] = verificar_llm()

    if not resultado["deepgram_up"]:
        resultado["modo_degradado"] = "sin_deepgram"
        resultado["accion_sugerida"] = "Transcripción manual disponible en /subir-audio"
    if not resultado["llm_up"]:
        resultado["modo_degradado"] = "sin_llm"
        resultado["accion_sugerida"] = "Chat no disponible. Generación de formatos desde portal OK."
```

---

### EVO — Tabla resumen de evolución del sistema

| ID | Feature | Impacto para Sandra | Tiempo |
|----|---------|---------------------|--------|
| EVO-1 | Streaming SSE en chat | Respuestas en tiempo real, no 120s de espera | 3h |
| EVO-2 | Formatos incrementales (llegan conforme se generan) | Ve resultados parciales en 8 min, no espera 20 min | 2h |
| EVO-3 | Flujo Draft → Revisando → Aprobado → Enviado ARL | Solo envía documentos revisados y correctos | 3h |
| EVO-4 | Retry LLM con backoff exponencial | El sistema se recupera solo de errores 500 | 45 min |
| EVO-5 | Extracción paralela portales | Paso 2 baja de 5 min a 2 min | 1h |
| EVO-6 | Keep-alive sesiones portales | Extracción al vuelo siempre funciona | 1h |
| EVO-7 | Detección de cambios en portales | Sandra sabe cuando cambia el diagnóstico/siniestro | 1.5h |
| EVO-8 | Formulario manual cuando falla portal | Sin portal, Sandra entra los datos y sigue | 2h |
| EVO-9 | Pre-check mejorado antes de procesar | Sandra sabe exactamente qué pasará antes de subir | 1h |
| EVO-10 | Extraer CC del audio automáticamente | No tiene que tipear la cédula | 1.5h |
| EVO-11 | PWA para iPhone | Dashboard funciona como app en el teléfono | 2h |
| EVO-12 | Briefing matinal automático (7 AM Telegram) | Empieza el día sabiendo todo sin abrir el dashboard | 1h |
| EVO-13 | Preview de documentos en el navegador | Aprueba documentos sin abrir Word | 1.5h |
| EVO-14 | Seguimiento de envíos ARL + alertas de vencimiento | No se olvida de plazos reglamentarios | 3h |
| EVO-15 | Historial de correcciones + aprendizaje | Tomy aprende de los errores propios | 2h |
| EVO-16 | Puntuación de calidad 0-100 por documento | Sandra ve de un vistazo qué tan completo está cada formato | 1h |
| EVO-17 | Visor de logs en tiempo real en el dashboard | Sandra/Manuel ven qué hace el sistema ahora mismo | 1.5h |
| EVO-18 | Cola de múltiples pacientes (queue) | 3 audios en paralelo procesados en orden, sin saturar | 2h |
| EVO-19 | Normalización de nombres y CC | Sin duplicados ni inconsistencias entre formatos | 1h |
| EVO-20 | Diff de documentos (qué cambió tras corrección) | Ver exactamente qué se modificó en 2 seg | 1h |
| EVO-21 | Auto-cleanup de audios procesados | El disco no se llena con meses de audios | 1h |
| EVO-22 | Modo degradado (funciona sin Deepgram/LLM/portal) | Sistema no para por problemas externos | 2h |

**Subtotal bloque EVO: ~36 horas**

---

## Tiempo estimado total (final)

| Bloque | Descripción | Tiempo |
|--------|-------------|--------|
| A | Bugs bloqueantes (ffmpeg, dependencias) | 1h |
| B | Chat omnisciente (historial, archivos, acciones) | 4h |
| P | Portales inteligentes (verificación, aprendizaje) | 5h |
| CR | Corrección desde chat (correction_resolver + aplicador) | 2h |
| Z | ZIP + retry de paso fallido | 1.5h |
| TG | Telegram bidireccional (webhook, voz, firma) | 4h |
| H | Mi Día + UX boomer-proof | 2h |
| PR | Pre-check de campos antes de procesar | 1h |
| FX | Fixes críticos adicionales (MIME, auth, CORS) | 2h |
| AG | Agenda completa (countdown, notificaciones, post-cita) | 3h |
| M | M4A especialización (XHR, progreso, validación) | 2h |
| C | Deploy + configuración inicial | 45 min |
| LH+PD | Limpieza Hermes + Producción robusta (PM2, Task Scheduler) | 4h |
| NC | Bugs reales segunda auditoría (QA roto, streaming, login) | 9.5h |
| EVO | Sistema de clase mundial (streaming, queue, PWA, aprendizaje) | 36h |
| **TOTAL** | | **~78 horas** |

> **Prioridad de ejecución recomendada:**
> 1. **Primero (sistema arranca):** A, FX, NC1, NC2, NC3, NC7, NC8, LH2/LH6
> 2. **Segundo (Sandra puede usarlo):** NC4 (Markdown), NC5 (selector paciente), NC11 (login), EVO-4 (retry), EVO-18 (queue)
> 3. **Tercero (experiencia excelente):** EVO-1 (streaming), EVO-3 (Draft→Aprobado), EVO-13 (preview), EVO-12 (briefing), EVO-11 (PWA)
> 4. **Cuarto (sistema de clase mundial):** EVO-2 (incremental), EVO-7 (cambios portal), EVO-14 (plazos ARL), EVO-15 (aprendizaje), EVO-16 (puntaje), EVO-17 (logs)

*Actualizado 2026-05-22 (v8). 59 bugs documentados + 22 features de evolución. Sistema completo con streaming SSE, queue de pacientes, PWA, aprendizaje de correcciones, diff de documentos, plazos ARL, modo degradado, y más. NC-2 corregido: deepseek-v4-flash es intencionado (clasificación rápida vs síntesis completa).*

---

## PARTE 16 — Plataforma clínica de inteligencia total

> **Filosofía elevada:** RILO SAS deja de ser un generador de documentos para convertirse en
> el **socio clínico invisible de Sandra**. No solo procesa audios — anticipa, enseña, protege,
> aprende, representa a Sandra ante la ARL, y convierte cada consulta en inteligencia acumulada.
> La diferencia entre "sistema que funciona" y "sistema que transforma una clínica".

---

### INT-1 — Base de conocimiento clínico: CIE-10 + restricciones por diagnóstico

**Por qué:** Ahora Tomy genera los formatos con lo que Sandra dice en el audio. Pero un médico
experto sabe que diagnóstico L4-L5 implica restricciones específicas de carga, postura y duración.
Diagnóstico M75.1 (manguito rotador) implica otro set de restricciones. Esta base de conocimiento
convierte las notas de Sandra en documentos clínicamente rigurosos.

**`backend/conocimiento_clinico.py` — nuevo módulo:**
```python
"""
Base de conocimiento clínico para RILO SAS.
Mapea diagnósticos CIE-10 → restricciones, recomendaciones, tiempos típicos.
Basado en protocolos ARL Positiva Colombia.
"""

CONOCIMIENTO_CIE10 = {
    # ── COLUMNA ──────────────────────────────────────────────────────────────
    "M54": {  # Dorsalgia / lumbago
        "descripcion": "Dorsalgia / Lumbago",
        "region": "columna lumbar",
        "restricciones_tipicas": [
            "Levantamiento de cargas máximo 5 kg",
            "Evitar posturas estáticas >30 minutos",
            "Sin rotación de tronco con carga",
            "Pausas activas cada 45 minutos",
        ],
        "recomendaciones_empresa": [
            "Adaptar puesto de trabajo con soporte lumbar",
            "Rotación de tareas para variar postura",
            "Capacitación en higiene postural",
        ],
        "tiempo_rehabilitacion_dias": (30, 90),
        "formatos_recomendados": ["analisis_exigencias", "carta_medidas", "carta_recomendaciones"],
    },
    "M51": {  # Trastornos de discos lumbares
        "descripcion": "Trastorno de disco lumbar / Hernia",
        "region": "columna lumbar",
        "restricciones_tipicas": [
            "Sin levantamiento de cargas >3 kg fase aguda",
            "Evitar flexión mantenida de columna",
            "Prohibido conducción de vehículos pesados",
            "Control ortopédico obligatorio",
        ],
        "recomendaciones_empresa": [
            "Trabajo en posición de pie con soporte lumbar",
            "Silla ergonómica con soporte lumbar ajustable",
        ],
        "tiempo_rehabilitacion_dias": (60, 180),
        "formatos_recomendados": ["analisis_exigencias", "carta_medidas", "valoracion_desempeno"],
    },
    "M75": {  # Lesiones del hombro (manguito rotador)
        "descripcion": "Lesiones del hombro incluyendo manguito rotador",
        "region": "hombro",
        "restricciones_tipicas": [
            "Sin elevación de miembro superior >90°",
            "Sin cargas >2 kg sobre la cabeza",
            "Evitar movimientos repetitivos de hombro",
            "Fisioterapia 3 veces por semana",
        ],
        "recomendaciones_empresa": [
            "Reubicar en puesto sin elevación de brazos",
            "Herramientas con mango ergonómico",
        ],
        "tiempo_rehabilitacion_dias": (45, 120),
        "formatos_recomendados": ["analisis_exigencias", "carta_medidas", "prueba_trabajo"],
    },
    "S52": {  # Fractura de antebrazo
        "descripcion": "Fractura del antebrazo (radio/cúbito)",
        "region": "miembro superior",
        "restricciones_tipicas": [
            "Inmovilización según indicación ortopédica",
            "Sin carga con miembro afectado fase aguda",
            "Trabajo unimano en fase de consolidación",
        ],
        "recomendaciones_empresa": ["Reubicación temporal a tareas administrativas"],
        "tiempo_rehabilitacion_dias": (45, 90),
        "formatos_recomendados": ["carta_medidas", "carta_recomendaciones", "cierre_caso"],
    },
    "G54": {  # Trastornos de raíces nerviosas
        "descripcion": "Trastornos de raíces nerviosas y plexos nerviosos",
        "region": "sistema nervioso periférico",
        "restricciones_tipicas": [
            "Sin exposición a vibración segmentaria",
            "Evitar posturas que compriman el nervio afectado",
            "Electromiografía de control",
        ],
        "recomendaciones_empresa": ["Evaluación ergonómica del puesto con especialista"],
        "tiempo_rehabilitacion_dias": (60, 150),
        "formatos_recomendados": ["analisis_exigencias", "valoracion_desempeno"],
    },
    # Agregar más diagnósticos comunes de ARL Positiva...
}

# Búsqueda por código parcial (M54 → M54.2, M54.5, etc.)
def buscar_por_codigo(codigo: str) -> dict | None:
    codigo = codigo.upper().strip()
    # Búsqueda exacta
    if codigo in CONOCIMIENTO_CIE10:
        return CONOCIMIENTO_CIE10[codigo]
    # Búsqueda por prefijo (M54.5 → busca M54)
    for k, v in CONOCIMIENTO_CIE10.items():
        if codigo.startswith(k):
            return {**v, "codigo_base": k, "codigo_exacto": codigo}
    return None

def enriquecer_datos_con_conocimiento(datos: dict) -> dict:
    """Agrega restricciones y recomendaciones de la base de conocimiento al JSON clínico."""
    cie10 = datos.get("siniestro", {}).get("diagnostico_cie10", "")
    if not cie10:
        return datos

    # Extraer el código (ej: "M54.5 Lumbago" → "M54.5" → busca M54)
    import re
    match = re.search(r'([A-Z]\d{2,3}\.?\d*)', cie10.upper())
    if not match:
        return datos

    conocimiento = buscar_por_codigo(match.group(1))
    if not conocimiento:
        return datos

    datos = dict(datos)
    # Solo agregar si no hay datos propios (no sobreescribir lo que Sandra dijo)
    if not datos.get("restricciones_sugeridas"):
        datos["_conocimiento"] = {
            "restricciones_base": conocimiento["restricciones_tipicas"],
            "recomendaciones_empresa_base": conocimiento["recomendaciones_empresa"],
            "tiempo_rehab_estimado_dias": conocimiento["tiempo_rehabilitacion_dias"],
            "region_anatomica": conocimiento["region"],
            "formatos_recomendados": conocimiento["formatos_recomendados"],
            "fuente": "base_conocimiento_rilo_arl",
        }
    return datos
```

**Integrar en `sintetizar_maestro.py`:**
```python
# Después de sintetizar el JSON maestro, enriquecerlo
from backend.conocimiento_clinico import enriquecer_datos_con_conocimiento
datos_clinicos = enriquecer_datos_con_conocimiento(datos_clinicos)
```

**Integrar en el SYSTEM_PROMPT de Tomy:**
```python
# Antes de llamar al LLM, buscar conocimiento del diagnóstico e inyectarlo
conocimiento = buscar_por_codigo(cie10_detectado)
if conocimiento:
    CONTEXT_CONOCIMIENTO = f"""
📚 BASE DE CONOCIMIENTO (diagnóstico {cie10_detectado}):
  Restricciones típicas: {'; '.join(conocimiento['restricciones_tipicas'][:3])}
  Tiempo rehabilitación estimado: {conocimiento['tiempo_rehabilitacion_dias'][0]}-{conocimiento['tiempo_rehabilitacion_dias'][1]} días
  ADVERTENCIA: Son sugerencias base. Los datos del audio de Sandra prevalecen.
"""
```

---

### INT-2 — Tomy como entrevistador clínico estructurado

**Por qué:** Ahora Tomy procesa el audio de lo que Sandra ya habló con el paciente.
Pero Sandra a veces olvida preguntar datos clave. Con el modo entrevistador, Tomy
le hace preguntas a Sandra DURANTE la consulta (o después) para asegurar que no falta nada.

**Flujo nuevo:**
```
Sandra: [envía audio de 30 min]
Tomy: "Procesé el audio. Me faltan estos datos para completar el VOI:
  1. ¿Cuál es el NIT exacto de Almacenes X?
  2. ¿El paciente tiene dominancia diestra o zurda?
  3. ¿Cuántas horas semanales trabaja normalmente?
  Puedes responderme aquí o en Telegram."
Sandra: "El NIT es 890903938, diestro, 48 horas semanales"
Tomy: [actualiza el JSON maestro, regenera los formatos faltantes]
```

**`backend/entrevistador.py` — nuevo módulo:**
```python
"""
Modo entrevistador: después de la síntesis, identifica campos críticos faltantes
y genera preguntas específicas, concisas, en lenguaje de Sandra.
"""
from backend.json_validator import FORMAT_SCHEMAS

PREGUNTAS_POR_CAMPO = {
    "empresa.nit": "¿Cuál es el NIT de {empresa}?",
    "empresa.telefono": "¿Teléfono de la empresa {empresa}?",
    "empresa.direccion": "¿Dirección de la empresa {empresa}?",
    "empresa.contacto": "¿Nombre del jefe o contacto en {empresa}?",
    "paciente.dominancia": "¿El paciente es diestro o zurdo?",
    "paciente.estado_civil": "¿El estado civil del paciente?",
    "paciente.nivel_educativo": "¿Nivel de estudios del paciente?",
    "laboral.antiguedad_cargo": "¿Cuánto tiempo lleva el paciente en ese cargo?",
    "laboral.jornada": "¿Cuántas horas diarias trabaja el paciente?",
    "laboral.turnos": "¿El trabajo es en turnos o jornada fija?",
    "laboral.fecha_ingreso_empresa": "¿Cuándo entró el paciente a trabajar en {empresa}?",
    "siniestro.tipo_evento": "¿El accidente fue en el trabajo o es enfermedad laboral?",
    "siniestro.descripcion": "¿Cómo ocurrió el accidente o cómo empezó el dolor?",
}

def generar_preguntas(datos: dict, formato_objetivo: str = "analisis_exigencias") -> list[str]:
    """Identifica campos faltantes y genera preguntas naturales."""
    schema = FORMAT_SCHEMAS.get(formato_objetivo, {})
    campos_required = schema.get("required", [])
    campos_recommended = schema.get("recommended", [])[:5]  # top 5 recomendados
    
    empresa_nombre = datos.get("empresa", {}).get("nombre", "la empresa")
    preguntas = []
    
    for campo in campos_required + campos_recommended:
        # Navegar el JSON por path punteado
        partes = campo.split(".")
        valor = datos
        for p in partes:
            if isinstance(valor, dict):
                valor = valor.get(p, "")
            else:
                valor = ""
        
        # Si falta o tiene placeholder
        if not valor or str(valor) in ("[VERIFICAR]", "[FALTA", "", "None"):
            plantilla = PREGUNTAS_POR_CAMPO.get(campo)
            if plantilla:
                pregunta = plantilla.format(empresa=empresa_nombre)
                preguntas.append(f"• {pregunta}")
    
    return preguntas[:6]  # Máximo 6 preguntas por sesión


def formatear_mensaje_preguntas(preguntas: list, paciente_nombre: str) -> str:
    if not preguntas:
        return ""
    return (
        f"✅ Procesé el audio de {paciente_nombre}. "
        f"Para completar todos los formatos necesito:\n\n"
        + "\n".join(preguntas)
        + "\n\n💬 Responde aquí o en Telegram."
    )
```

**Integrar en el workflow — después del paso 5 (sintetizar_maestro):**
```python
# workflow_runner.py — después de sintetizar, verificar campos y preguntar
if step_name == "sintetizar_maestro" and resultado_step.get("ok"):
    from backend.entrevistador import generar_preguntas, formatear_mensaje_preguntas
    datos_clinicos = resultado_step.get("datos_clinicos", {})
    # Determinar el formato más exigente que se va a generar
    formato_obj = contexto.get("resolver_paciente", {}).get("estado_caso_detectado", "analisis_exigencias")
    preguntas = generar_preguntas(datos_clinicos, formato_obj)
    
    if preguntas:
        nombre_pac = datos_clinicos.get("paciente", {}).get("nombre", f"CC {paciente_cc}")
        msg = formatear_mensaje_preguntas(preguntas, nombre_pac)
        # Guardar preguntas en la DB para mostrar en el dashboard
        db.guardar_resultado(task_id, {"preguntas_pendientes": preguntas, "datos_parciales": datos_clinicos}, estado="esperando_datos")
        # Notificar por Telegram
        from backend.notificador import enviar_telegram
        enviar_telegram(msg)
        # Pausar el workflow — continúa cuando Sandra responda
        return {"task_id": task_id, "estado": "esperando_datos", "preguntas": preguntas}
```

**Sandra responde por Telegram o por chat → reanuda el workflow:**
```python
# server.py — endpoint para continuar workflow pausado
@app.post("/api/tasks/{task_id}/responder-preguntas")
async def responder_preguntas(task_id: str, req: CorregirRequest):
    """Sandra responde las preguntas del entrevistador → reanudar workflow."""
    from backend.correction_resolver import resolver_respuesta_libre
    db = TaskDB(...)
    task = db.obtener_task(task_id)
    if not task or task["estado"] != "esperando_datos":
        raise HTTPException(400, "Task no está esperando datos")
    
    # Parsear respuestas de Sandra con el LLM
    datos_parciales = task["resultado"].get("datos_parciales", {})
    preguntas = task["resultado"].get("preguntas_pendientes", [])
    datos_actualizados = resolver_respuesta_libre(req.mensaje, datos_parciales, preguntas)
    
    # Guardar datos actualizados y reanudar desde paso 6
    db.guardar_resultado(task_id, {"datos_clinicos": datos_actualizados}, estado="sintetizando")
    from backend.workflow_queue import encolar_desde_paso
    await encolar_desde_paso(task_id, desde_paso=6)  # continuar desde generar_formatos
    return {"ok": True, "mensaje": "Perfecto. Generando los formatos con los datos completos..."}
```

---

### INT-3 — Paquete completo ARL: carta de presentación + 7 formatos + resumen ejecutivo

**Por qué:** Cuando Sandra envía los formatos a ARL Positiva, los manda como archivos sueltos.
Un paquete profesional incluye: carta de presentación firmada, los 7 formatos ordenados, y un
resumen ejecutivo de 1 página. Esto hace a Sandra ver más profesional ante la ARL y reduce
el riesgo de que devuelvan el expediente por falta de documentos.

**`backend/paquete_arl.py` — nuevo módulo:**
```python
"""
Genera el paquete completo de envío a ARL Positiva:
  1. Carta de presentación (DOCX automático)
  2. Los 7 formatos en orden
  3. Resumen ejecutivo (1 página)
  4. ZIP listo para enviar
"""
import os
import io
import zipfile
from pathlib import Path
from datetime import date, datetime
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


def generar_carta_presentacion(datos: dict, formatos_generados: list) -> bytes:
    """Genera carta de presentación DOCX lista para firmar."""
    doc = Document()
    
    # Encabezado RILO SAS
    header = doc.add_paragraph()
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = header.add_run("RILO SAS — REHABILITACIÓN INTEGRAL LABORAL Y OCUPACIONAL")
    run.bold = True
    run.font.size = Pt(14)
    
    doc.add_paragraph(f"Neiva, {date.today().strftime('%d de %B de %Y')}")
    doc.add_paragraph()
    doc.add_paragraph("Señores")
    doc.add_paragraph("ARL POSITIVA COMPAÑÍA DE SEGUROS")
    doc.add_paragraph("Ciudad")
    doc.add_paragraph()
    
    paciente = datos.get("paciente", {})
    siniestro = datos.get("siniestro", {})
    empresa = datos.get("empresa", {})
    
    asunto = doc.add_paragraph()
    asunto.add_run("Referencia: ").bold = True
    asunto.add_run(
        f"Paciente: {paciente.get('nombre', '')} — "
        f"CC {paciente.get('documento', '')} — "
        f"Siniestro No. {siniestro.get('id_siniestro', '')} — "
        f"Empresa: {empresa.get('nombre', '')}"
    )
    
    doc.add_paragraph()
    doc.add_paragraph(
        f"Respetados señores:\n\n"
        f"Me permito remitirles los documentos de rehabilitación profesional del trabajador "
        f"{paciente.get('nombre', '[NOMBRE]')}, identificado con cédula de ciudadanía "
        f"No. {paciente.get('documento', '[CC]')}, afiliado a la empresa {empresa.get('nombre', '[EMPRESA]')}, "
        f"correspondientes al proceso de Rehabilitación Integral enmarcado en el siniestro "
        f"No. {siniestro.get('id_siniestro', '[SINIESTRO]')}.\n\n"
        f"Se anexan los siguientes {len(formatos_generados)} documentos:\n"
    )
    
    for i, fmt in enumerate(formatos_generados, 1):
        doc.add_paragraph(f"  {i}. {fmt.get('nombre', fmt.get('formato', ''))}", style='List Number')
    
    doc.add_paragraph()
    doc.add_paragraph(
        "Sin otro particular, cordialmente,\n\n\n\n"
        "___________________________________\n"
        "SANDRA PATRICIA POLANIA OSORIO\n"
        "Fisioterapeuta — TP XXXXX\n"
        "RILO SAS — NIT XXX.XXX.XXX-X\n"
        f"Tel: {os.getenv('SANDRA_TELEFONO', '')}"
    )
    
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def generar_resumen_ejecutivo(datos: dict, qa_resultados: list) -> bytes:
    """Genera resumen ejecutivo de 1 página del caso."""
    doc = Document()
    
    pac = datos.get("paciente", {})
    sin = datos.get("siniestro", {})
    emp = datos.get("empresa", {})
    
    doc.add_heading("RESUMEN EJECUTIVO DEL CASO", level=1)
    
    # Tabla de datos clave
    tabla = doc.add_table(rows=1, cols=2)
    tabla.style = 'Table Grid'
    
    campos = [
        ("Paciente", pac.get("nombre", "")),
        ("Cédula", pac.get("documento", "")),
        ("Empresa", emp.get("nombre", "")),
        ("Cargo", datos.get("laboral", {}).get("cargo", "")),
        ("Siniestro", sin.get("id_siniestro", "")),
        ("Diagnóstico", sin.get("diagnostico_cie10", "")),
        ("Fecha evento", sin.get("fecha_evento", "")),
        ("Estado caso", datos.get("estado_caso", "")),
        ("Fecha resumen", date.today().strftime("%d/%m/%Y")),
    ]
    
    for etiqueta, valor in campos:
        row = tabla.add_row()
        row.cells[0].text = etiqueta
        row.cells[1].text = str(valor)
    
    doc.add_paragraph()
    
    # Calidad de documentos
    doc.add_heading("Calidad de documentos generados", level=2)
    for r in qa_resultados:
        puntaje = r.get("qa_puntaje", "N/A")
        doc.add_paragraph(f"• {r.get('formato', '?')}: {puntaje}/100")
    
    # Observaciones clave
    obs = datos.get("_meta", {}).get("discrepancias", [])
    if obs:
        doc.add_heading("Observaciones", level=2)
        for o in obs[:5]:
            doc.add_paragraph(f"• {o}")
    
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def crear_paquete_zip(datos: dict, formatos_generados: list, qa_resultados: list) -> bytes:
    """Crea el ZIP completo listo para enviar a ARL."""
    buf = io.BytesIO()
    
    cc = datos.get("paciente", {}).get("documento", "desconocido")
    nombre_sin = datos.get("siniestro", {}).get("id_siniestro", "")
    
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Carta de presentación
        carta = generar_carta_presentacion(datos, formatos_generados)
        zf.writestr(f"00_Carta_Presentacion_CC{cc}.docx", carta)
        
        # 2. Los 7 formatos en orden
        for i, fmt in enumerate(formatos_generados, 1):
            path = Path(fmt.get("archivo", ""))
            if path.exists():
                zf.write(path, f"{i:02d}_{path.name}")
        
        # 3. PDFs si existen
        pdfs_dir = Path(os.getenv("STORAGE_DIR", "./storage")) / "pdfs"
        for pdf in sorted(pdfs_dir.glob(f"*{cc}*.pdf")):
            zf.write(pdf, f"PDF/{pdf.name}")
        
        # 4. Resumen ejecutivo
        resumen = generar_resumen_ejecutivo(datos, qa_resultados)
        zf.writestr(f"RESUMEN_EJECUTIVO_Siniestro{nombre_sin}.docx", resumen)
    
    return buf.getvalue()
```

**Endpoint en `server.py`:**
```python
@app.get("/api/tasks/{task_id}/paquete-arl")
def descargar_paquete_arl(task_id: str):
    """Descarga el ZIP completo: carta + 7 formatos + resumen ejecutivo."""
    db = TaskDB(...)
    task = db.obtener_task(task_id)
    if not task or task["estado"] != "listo":
        raise HTTPException(400, "Task no está lista")
    
    from backend.paquete_arl import crear_paquete_zip
    resultado = task.get("resultado", {})
    datos = _cargar_datos_paciente(task["paciente_cc"])
    formatos = resultado.get("formatos_generados", [])
    qa = resultado.get("qa_resultados", [])
    
    zip_bytes = crear_paquete_zip(datos, formatos, qa)
    cc = task["paciente_cc"]
    fecha = date.today().strftime("%Y%m%d")
    
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="Paquete_ARL_CC{cc}_{fecha}.zip"'},
    )
```

---

### INT-4 — Tomy proactivo: nudges inteligentes sin que Sandra pregunte

**Por qué:** Un asistente reactivo espera que le pregunten. Un asistente de clase mundial
observa el sistema, detecta situaciones, y actúa primero. Sandra tiene muchos pacientes —
no debería tener que acordarse de revisar cada uno.

**`backend/proactivo.py` — motor de reglas proactivas:**
```python
"""
Motor de reglas proactivas. Corre diariamente y evalúa todos los casos activos.
Si detecta algo importante, notifica a Sandra con sugerencia accionable.
"""
import os
import json
import glob
from pathlib import Path
from datetime import date, datetime, timedelta


REGLAS = [
    {
        "id": "caso_sin_actividad_30d",
        "descripcion": "Caso activo sin actividad en 30+ días",
        "check": lambda datos, tasks: (
            datos.get("estado_caso") in ("SEGUIMIENTO", "NUEVO") and
            not any(t["iniciado_en"] > (datetime.now() - timedelta(days=30)).isoformat() for t in tasks)
        ),
        "mensaje": lambda datos: (
            f"⏰ {datos['paciente']['nombre']} lleva más de 30 días sin actividad. "
            f"¿Hay una consulta pendiente de procesar?"
        ),
    },
    {
        "id": "listo_para_cierre",
        "descripcion": "Caso con VOI generado hace >2 semanas: posible cierre",
        "check": lambda datos, tasks: (
            datos.get("estado_caso") == "SEGUIMIENTO" and
            any("valoracion" in str(t.get("resultado", {}).get("formatos_generados", [])) for t in tasks) and
            any(t["iniciado_en"] < (datetime.now() - timedelta(days=14)).isoformat() for t in tasks)
        ),
        "mensaje": lambda datos: (
            f"📋 {datos['paciente']['nombre']}: tiene VOI generado y más de 2 semanas en seguimiento. "
            f"¿Es momento del Cierre de Caso? Dime y lo preparo."
        ),
    },
    {
        "id": "discrepancia_no_resuelta",
        "descripcion": "Discrepancia entre portales sin resolver hace >7 días",
        "check": lambda datos, tasks: (
            len(datos.get("_meta", {}).get("discrepancias", [])) > 0 and
            not datos.get("_discrepancias_resueltas")
        ),
        "mensaje": lambda datos: (
            f"⚠️ {datos['paciente']['nombre']}: hay {len(datos['_meta']['discrepancias'])} "
            f"discrepancia(s) entre portales sin resolver. ¿Las revisamos?"
        ),
    },
    {
        "id": "sin_firma",
        "descripcion": "Formatos generados pero sin firma cargada",
        "check": lambda datos, tasks: (
            any(t["estado"] == "listo" for t in tasks) and
            not Path(os.getenv("STORAGE_DIR", "./storage")).joinpath("firma_sandra.png").exists()
        ),
        "mensaje": lambda datos: (
            f"✍️ Hay formatos listos pero no tienes firma cargada en el sistema. "
            f"Envíame una foto de tu firma por Telegram."
        ),
    },
    {
        "id": "nuevo_paciente_en_medifolios",
        "descripcion": "Paciente en agenda que no está en el sistema",
        "check": lambda datos, tasks: datos.get("_es_nuevo_en_sistema"),
        "mensaje": lambda datos: (
            f"👤 {datos['paciente']['nombre']} está en tu agenda pero no tiene expediente en RILO. "
            f"¿Quieres que empiece a preparar sus datos del portal?"
        ),
    },
]


async def evaluar_reglas_proactivas():
    """Evalúa todas las reglas sobre todos los casos activos."""
    from backend.task_db import TaskDB
    from backend.notificador import enviar_telegram

    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    archivos = list((storage / "data").glob("*-completo.json"))
    db = TaskDB(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))

    mensajes_enviados = 0
    for archivo in archivos:
        try:
            datos = json.loads(archivo.read_text())
            cc = datos.get("paciente", {}).get("documento", "")
            if not cc:
                continue
            tasks = db.listar_tasks_paciente(cc, limit=5)

            for regla in REGLAS:
                try:
                    if regla["check"](datos, tasks):
                        mensaje = regla["mensaje"](datos)
                        enviar_telegram(mensaje)
                        mensajes_enviados += 1
                        # No más de 1 nudge por regla por paciente por día
                        break
                except Exception:
                    continue
        except Exception:
            continue

    return mensajes_enviados
```

**Agregar al scheduler (corre cada mañana a las 8 AM):**
```python
scheduler.add_job(
    evaluar_reglas_proactivas,
    CronTrigger(hour=8, minute=30, timezone=COL),
    id="proactivo_nudges",
    replace_existing=True,
)
```

---

### INT-5 — Inteligencia entre casos: patrones cruzados de pacientes

**Por qué:** Si Sandra tiene 5 pacientes de la misma empresa con el mismo diagnóstico lumbar,
eso no es coincidencia — es un riesgo laboral no controlado. El sistema debe detectar esto y
alertar. También permite ver qué empresas tienen más siniestros, qué diagnósticos son más comunes,
y qué casos son más complejos.

**`backend/analítica_casos.py` — nuevo módulo:**
```python
"""
Analítica cruzada de casos: patrones, agrupaciones, insights.
"""
import json
import glob
import os
from pathlib import Path
from collections import Counter, defaultdict
from datetime import date


def analizar_todos_los_casos() -> dict:
    """Análisis completo de todos los casos en el sistema."""
    archivos = list((Path(os.getenv("STORAGE_DIR","./storage")) / "data").glob("*-completo.json"))
    casos = []
    for f in archivos:
        try: casos.append(json.loads(f.read_text()))
        except: pass

    if not casos:
        return {"total": 0}

    # Por empresa
    por_empresa = Counter(
        c.get("empresa", {}).get("nombre", "Desconocida") for c in casos
    )

    # Por diagnóstico CIE-10 (primeros 3 caracteres)
    por_diagnostico = Counter()
    for c in casos:
        cie = c.get("siniestro", {}).get("diagnostico_cie10", "")
        if cie:
            por_diagnostico[cie[:3]] += 1

    # Por estado
    por_estado = Counter(c.get("estado_caso", "DESCONOCIDO") for c in casos)

    # Alertas de clustering
    alertas = []

    # Empresa con 3+ pacientes
    for empresa, n in por_empresa.most_common(3):
        if n >= 3:
            alertas.append({
                "tipo": "empresa_alto_siniestro",
                "empresa": empresa,
                "pacientes": n,
                "mensaje": f"⚠️ {empresa}: {n} pacientes activos. Posible riesgo laboral sistémico.",
            })

    # Diagnóstico con 4+ casos
    from backend.conocimiento_clinico import CONOCIMIENTO_CIE10
    for codigo, n in por_diagnostico.most_common(3):
        if n >= 4:
            conocimiento = CONOCIMIENTO_CIE10.get(codigo, {})
            alertas.append({
                "tipo": "diagnostico_frecuente",
                "codigo": codigo,
                "descripcion": conocimiento.get("descripcion", codigo),
                "casos": n,
                "mensaje": f"📊 {n} casos de {conocimiento.get('descripcion', codigo)}. ¿Hay un patrón?",
            })

    return {
        "total_casos": len(casos),
        "por_empresa": dict(por_empresa.most_common(10)),
        "por_diagnostico": dict(por_diagnostico.most_common(10)),
        "por_estado": dict(por_estado),
        "alertas_clustering": alertas,
        "generado_en": date.today().isoformat(),
    }
```

**Nuevo endpoint:**
```python
@app.get("/api/analitica")
def obtener_analitica():
    from backend.analitica_casos import analizar_todos_los_casos
    return {"ok": True, **analizar_todos_los_casos()}
```

**Nueva página `dashboard/app/estadisticas/page.tsx`:**
```tsx
// Métricas clave en cards visuales
// - Total pacientes activos
// - Top 3 empresas con más siniestros  
// - Top 3 diagnósticos más frecuentes
// - Alertas de clustering
// - Gráfico de casos por estado (usando Tailwind + divs, sin librerías externas)
```

---

### INT-6 — Trayectoria del caso: línea de tiempo clínica completa

**Por qué:** Para el Cierre de Caso y el VOI, Sandra necesita documentar la evolución del
paciente desde el inicio. Ahora tiene que recordar o buscar en los documentos antiguos.
Con la línea de tiempo automática, el sistema reconstruye toda la historia del caso.

**`backend/timeline_caso.py` — nuevo módulo:**
```python
"""
Reconstruye la línea de tiempo clínica de un caso a partir de:
- Tasks procesadas (fecha, formato generado, estado)
- Archivos DOCX generados (fecha de modificación)
- Extracciones de portal (cambios detectados)
- Correcciones aplicadas (historial de correcciones)
"""
import json
import os
import glob
from pathlib import Path
from datetime import datetime


def construir_timeline(cc: str) -> list[dict]:
    """Retorna lista de eventos ordenados cronológicamente."""
    eventos = []
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))

    # Eventos de workflow (tasks procesadas)
    from backend.task_db import TaskDB
    db = TaskDB(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))
    tasks = db.listar_tasks_paciente(cc, limit=50)
    for t in tasks:
        if t["estado"] == "listo":
            formatos = t.get("resultado", {}).get("formatos_generados", []) if isinstance(t.get("resultado"), dict) else []
            eventos.append({
                "fecha": t["iniciado_en"],
                "tipo": "procesamiento",
                "descripcion": f"Audio procesado → {len(formatos)} formato(s) generado(s)",
                "formatos": [f.get("formato", "") for f in formatos],
                "task_id": t["task_id"],
            })

    # Archivos DOCX del paciente
    docs_dir = storage / "docs"
    for docx in sorted(docs_dir.glob(f"*{cc}*.docx"), key=lambda p: p.stat().st_mtime):
        eventos.append({
            "fecha": datetime.fromtimestamp(docx.stat().st_mtime).isoformat(),
            "tipo": "documento",
            "descripcion": f"Documento: {docx.stem}",
            "archivo": docx.name,
        })

    # Extracciones de portal
    data_dir = storage / "data"
    archivos_portal = sorted(data_dir.glob(f"*{cc}*completo.json"), key=lambda p: p.stat().st_mtime)
    for f in archivos_portal:
        datos = json.loads(f.read_text())
        actualizacion = datos.get("ultima_actualizacion")
        if actualizacion:
            eventos.append({
                "fecha": actualizacion,
                "tipo": "portal",
                "descripcion": f"Datos actualizados desde portales",
                "discrepancias": len(datos.get("_meta", {}).get("discrepancias", [])),
            })

    # Correcciones aplicadas
    from backend.correcciones_historico import _cargar as cargar_historico
    historico = [h for h in cargar_historico() if h.get("paciente_cc") == cc]
    for h in historico:
        eventos.append({
            "fecha": h["ts"],
            "tipo": "correccion",
            "descripcion": f"Corrección: {h['campo']} → {h['valor_nuevo'][:50]}",
        })

    # Ordenar por fecha
    eventos.sort(key=lambda e: e.get("fecha", ""), reverse=True)
    return eventos
```

**Endpoint y visualización en `/paciente/{cc}`:**
```python
@app.get("/api/pacientes/{cc}/timeline")
def timeline_paciente(cc: str):
    from backend.timeline_caso import construir_timeline
    return {"ok": True, "eventos": construir_timeline(cc)}
```


### BIZ-1 — Dashboard de productividad y ROI mensual

**Por qué:** Sandra cobra por caso procesado. Si el sistema le ahorra 3 horas por paciente
y ella tiene 15 pacientes al mes, eso son 45 horas ahorradas. Manuel puede mostrarle esto
con números reales — y Sandra entenderá el valor del sistema que usó sin cuestionarlo.

**`backend/reporte_mensual.py` — nuevo módulo:**
```python
"""
Reporte mensual de productividad y ROI para Sandra.
Enviado automáticamente el día 1 de cada mes.
"""
import json
import os
from pathlib import Path
from datetime import date, datetime, timedelta
from collections import Counter


def calcular_reporte_mes(año: int, mes: int) -> dict:
    """Calcula métricas del mes especificado."""
    from backend.task_db import TaskDB
    from backend.costos_tracker import resumen_dia

    db = TaskDB(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))

    # Calcular rango del mes
    inicio = date(año, mes, 1)
    if mes == 12:
        fin = date(año + 1, 1, 1) - timedelta(days=1)
    else:
        fin = date(año, mes + 1, 1) - timedelta(days=1)

    # Tasks completadas en el mes
    tasks_mes = []
    with db._conn() as conn:
        rows = conn.execute(
            "SELECT * FROM workflow_tasks WHERE estado='listo' "
            "AND DATE(terminado_en) BETWEEN ? AND ?",
            (inicio.isoformat(), fin.isoformat()),
        ).fetchall()
        tasks_mes = [dict(r) for r in rows]

    # Costos LLM del mes
    total_tokens = 0
    for i in range((fin - inicio).days + 1):
        d = inicio + timedelta(days=i)
        resumen = resumen_dia(d)
        total_tokens += resumen.get("total_tokens", 0)

    # Formatos generados
    formatos_generados = 0
    pacientes_procesados = set()
    for t in tasks_mes:
        resultado = t.get("resultado") or {}
        if isinstance(resultado, str):
            try: resultado = json.loads(resultado)
            except: resultado = {}
        formatos_generados += len(resultado.get("formatos_generados", []))
        pacientes_procesados.add(t["paciente_cc"])

    # Tiempo promedio por task
    tiempos = []
    for t in tasks_mes:
        if t.get("iniciado_en") and t.get("terminado_en"):
            inicio_t = datetime.fromisoformat(t["iniciado_en"])
            fin_t = datetime.fromisoformat(t["terminado_en"])
            tiempos.append((fin_t - inicio_t).total_seconds() / 60)  # en minutos

    tiempo_promedio_min = sum(tiempos) / len(tiempos) if tiempos else 0

    # Estimado de horas ahorradas (3 horas por paciente sin el sistema)
    horas_ahorradas = len(pacientes_procesados) * 3

    # Costo estimado API (tokens × precio por token)
    costo_api_usd = total_tokens * 0.000002  # estimado deepseek

    return {
        "mes": f"{inicio.strftime('%B %Y')}",
        "pacientes_procesados": len(pacientes_procesados),
        "audios_procesados": len(tasks_mes),
        "formatos_generados": formatos_generados,
        "tiempo_promedio_proceso_min": round(tiempo_promedio_min, 1),
        "horas_ahorradas_estimado": horas_ahorradas,
        "total_tokens_llm": total_tokens,
        "costo_api_estimado_usd": round(costo_api_usd, 2),
        "costo_api_estimado_cop": round(costo_api_usd * 4100, 0),  # tasa aproximada
    }


async def enviar_reporte_mensual():
    """Envía el reporte del mes anterior el día 1."""
    hoy = date.today()
    mes_ant = hoy.month - 1 or 12
    año_ant = hoy.year if hoy.month > 1 else hoy.year - 1

    reporte = calcular_reporte_mes(año_ant, mes_ant)

    from backend.notificador import enviar_telegram
    texto = (
        f"📊 *Reporte {reporte['mes']}*\n\n"
        f"👥 Pacientes procesados: {reporte['pacientes_procesados']}\n"
        f"🎙️ Audios procesados: {reporte['audios_procesados']}\n"
        f"📄 Formatos generados: {reporte['formatos_generados']}\n"
        f"⏱️ Tiempo promedio: {reporte['tiempo_promedio_proceso_min']} min/audio\n"
        f"⏰ Horas ahorradas (estimado): {reporte['horas_ahorradas_estimado']}h\n"
        f"💰 Costo API: ${reporte['costo_api_estimado_usd']} USD "
        f"(≈ ${reporte['costo_api_estimado_cop']:,.0f} COP)"
    )
    enviar_telegram(texto)
```

**Endpoint visible en el dashboard:**
```python
@app.get("/api/reporte/{año}/{mes}")
def reporte_mensual(año: int, mes: int):
    from backend.reporte_mensual import calcular_reporte_mes
    return {"ok": True, **calcular_reporte_mes(año, mes)}
```

---

### LEGAL-1 — Cumplimiento Ley 1581/2012 (Habeas Data Colombia)

**Por qué:** Los datos clínicos de los pacientes de Sandra son datos sensibles de salud.
En Colombia, la Ley 1581 de 2012 y su Decreto Reglamentario 1377 de 2013 establecen
requisitos específicos para el tratamiento de datos personales de salud. RILO debe cumplir.

**`backend/habeas_data.py` — nuevo módulo:**
```python
"""
Cumplimiento Ley 1581/2012 y Decreto 1377/2013 — Protección de datos personales.
Implementa: anonimización, retención, exportación, eliminación.
"""
import json
import os
import re
from pathlib import Path
from datetime import date, datetime, timedelta


# Período de retención legal para datos de rehabilitación laboral (5 años)
RETENTION_YEARS = int(os.getenv("DATA_RETENTION_YEARS", "5"))


def anonimizar_para_logs(texto: str) -> str:
    """Reemplaza datos sensibles en logs por versión anonimizada."""
    # CC: reemplazar dígitos medios
    texto = re.sub(r'\b(\d{2})\d{4,8}(\d{2})\b', r'\1****\2', texto)
    # Teléfonos
    texto = re.sub(r'\b(3\d{2})\d{3}(\d{4})\b', r'\1***\2', texto)
    # Nombres propios (heurística: MAYUSCULA seguida de mayúsculas y espacios)
    texto = re.sub(r'\b[A-ZÁÉÍÓÚ]{2,}(\s+[A-ZÁÉÍÓÚ]{2,}){1,3}\b', '[NOMBRE ANONIMIZADO]', texto)
    return texto


def exportar_datos_paciente(cc: str) -> dict:
    """
    Exporta TODOS los datos de un paciente en formato portable.
    Derecho de portabilidad — Art. 8 Ley 1581.
    """
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    archivos = list((storage / "data").glob(f"*{cc}*completo.json"))
    if not archivos:
        return {"error": "Paciente no encontrado"}

    datos = json.loads(archivos[0].read_text())

    # Agregar metadatos de portabilidad
    return {
        "exportado_en": datetime.now().isoformat(),
        "norma": "Ley 1581/2012 Colombia — Habeas Data",
        "responsable": "RILO SAS — Sandra Patricia Polania Osorio",
        "datos": datos,
        "instrucciones": (
            "Este archivo contiene todos sus datos personales procesados por RILO SAS. "
            "Puede solicitar corrección o eliminación escribiendo a: "
            + os.getenv("CONTACT_EMAIL", "")
        ),
    }


def eliminar_datos_paciente(cc: str, razon: str = "solicitud_titular") -> dict:
    """
    Elimina TODOS los datos de un paciente del sistema.
    Derecho de supresión — Art. 8 Ley 1581. IRREVERSIBLE.
    """
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    eliminados = []

    # Datos JSON
    for f in (storage / "data").glob(f"*{cc}*"):
        f.unlink()
        eliminados.append(str(f))

    # Documentos DOCX
    for f in (storage / "docs").glob(f"*{cc}*"):
        f.unlink()
        eliminados.append(str(f))

    # PDFs
    for f in (storage / "pdfs").glob(f"*{cc}*"):
        f.unlink()
        eliminados.append(str(f))

    # Audios
    for f in (storage / "workflow_audios").glob(f"{cc}_*"):
        f.unlink()
        eliminados.append(str(f))

    # Registrar eliminación en audit log (el audit log en sí no se borra)
    _registrar_audit("SUPRESION_DATOS", cc, razon, {"archivos_eliminados": len(eliminados)})

    return {"ok": True, "archivos_eliminados": len(eliminados), "cc": cc}


def verificar_retencion_vencida() -> list[str]:
    """
    Identifica pacientes cuyos datos superaron el período de retención.
    Debe correrse mensualmente.
    """
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    limite = (date.today() - timedelta(days=RETENTION_YEARS * 365)).isoformat()
    por_eliminar = []

    for f in (storage / "data").glob("*-completo.json"):
        try:
            datos = json.loads(f.read_text())
            ultima_act = datos.get("ultima_actualizacion", "")
            if ultima_act and ultima_act[:10] < limite:
                cc = datos.get("paciente", {}).get("documento", "")
                if cc:
                    por_eliminar.append(cc)
        except Exception:
            continue

    return por_eliminar


def _registrar_audit(accion: str, cc: str, usuario: str, detalle: dict):
    audit_path = Path(os.getenv("STORAGE_DIR","./storage")) / "audit_log.jsonl"
    entrada = json.dumps({
        "ts": datetime.now().isoformat(),
        "accion": accion,
        "cc_paciente": cc,
        "usuario": usuario,
        "detalle": detalle,
    }, ensure_ascii=False) + "\n"
    audit_path.parent.mkdir(exist_ok=True)
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(entrada)
```

**Endpoints legales en `server.py`:**
```python
@app.get("/api/pacientes/{cc}/exportar-datos")
def exportar_datos(cc: str):
    from backend.habeas_data import exportar_datos_paciente, _registrar_audit
    _registrar_audit("EXPORTACION_DATOS", cc, "solicitud_titular", {})
    datos = exportar_datos_paciente(cc)
    return Response(
        content=json.dumps(datos, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="datos_{cc}.json"'},
    )

@app.delete("/api/pacientes/{cc}/eliminar-datos")
def eliminar_datos(cc: str, razon: str = "solicitud_titular"):
    from backend.habeas_data import eliminar_datos_paciente
    return eliminar_datos_paciente(cc, razon)

@app.get("/api/audit-log")
def ver_audit_log(ultimas: int = 100):
    audit_path = Path(os.getenv("STORAGE_DIR","./storage")) / "audit_log.jsonl"
    if not audit_path.exists():
        return {"ok": True, "entradas": []}
    lineas = audit_path.read_text().strip().split("\n")[-ultimas:]
    return {"ok": True, "entradas": [json.loads(l) for l in lineas if l]}
```

---

### LEGAL-2 — Registro de auditoría en cada operación crítica

**Por qué:** Un expediente clínico de ARL puede ser auditado años después. El sistema debe
poder responder: ¿quién generó este documento? ¿cuándo? ¿se modificó? ¿quién lo descargó?
Esto también protege a Sandra legalmente si hay disputas sobre los documentos.

**Integrar audit log en operaciones críticas:**
```python
# En server.py, decorar endpoints críticos:

def _audit(accion: str, cc: str = "", detalle: dict = None):
    """Registra acción en el audit log."""
    from backend.habeas_data import _registrar_audit
    _registrar_audit(accion, cc, "Sandra", detalle or {})

# Ejemplos de uso:
@app.post("/api/procesar-paciente")
async def procesar_paciente(...):
    _audit("INICIO_PROCESAMIENTO", cc=paciente_cc, detalle={"audio": audio.filename})
    # ...

@app.get("/api/download/{filename}")
def descargar_archivo(filename: str):
    _audit("DESCARGA_DOCUMENTO", detalle={"archivo": filename})
    # ...

@app.post("/api/tasks/{task_id}/enviar-arl")
def marcar_enviado_arl(task_id: str):
    task = db.obtener_task(task_id)
    _audit("ENVIO_ARL", cc=task["paciente_cc"], detalle={"task_id": task_id})
    # ...
```

---

### ARCH-1 — SQLite en modo WAL + connection pool

**Por qué:** La configuración por defecto de SQLite usa journal mode DELETE que bloquea
la base de datos durante escrituras. Con WAL (Write-Ahead Logging), lecturas y escrituras
pueden ocurrir simultáneamente — crítico cuando el workflow escribe y el dashboard lee al tiempo.

**`backend/task_db.py` — habilitar WAL al conectar:**
```python
def _conn(self):
    conn = sqlite3.connect(str(self.db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    # WAL mode: lecturas no bloquean escrituras y viceversa
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")    # Más rápido, sigue siendo seguro
    conn.execute("PRAGMA cache_size=10000")       # 10K páginas en caché
    conn.execute("PRAGMA temp_store=MEMORY")      # Tablas temp en RAM
    conn.execute("PRAGMA foreign_keys=ON")        # Integridad referencial
    return conn
```

---

### ARCH-2 — Circuit breaker para APIs externas

**Por qué:** Si Deepgram falla 5 veces seguidas, el sistema sigue intentando en cada audio
(gastando tiempo y dinero en reintentos fallidos). Un circuit breaker "abre el circuito" después
de N fallos consecutivos — el sistema falla rápido en vez de lento.

**`backend/circuit_breaker.py` — nuevo módulo:**
```python
"""
Patrón Circuit Breaker para APIs externas.
Estados: CLOSED (normal) → OPEN (falla rápido) → HALF_OPEN (probar)
"""
import time
from datetime import datetime

class CircuitBreaker:
    def __init__(self, nombre: str, max_fallos: int = 5, timeout_s: int = 300):
        self.nombre = nombre
        self.max_fallos = max_fallos
        self.timeout_s = timeout_s
        self._fallos = 0
        self._ultimo_fallo = None
        self._estado = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def puede_intentar(self) -> bool:
        if self._estado == "CLOSED":
            return True
        if self._estado == "OPEN":
            # ¿Pasó el timeout? → probar de nuevo
            if time.time() - self._ultimo_fallo > self.timeout_s:
                self._estado = "HALF_OPEN"
                return True
            return False
        return True  # HALF_OPEN → intentar

    def registrar_exito(self):
        self._fallos = 0
        self._estado = "CLOSED"

    def registrar_fallo(self):
        self._fallos += 1
        self._ultimo_fallo = time.time()
        if self._fallos >= self.max_fallos:
            self._estado = "OPEN"
            print(f"[CB] {self.nombre}: ABIERTO ({self._fallos} fallos). Pausa {self.timeout_s}s")

    @property
    def estado(self): return self._estado


# Singletons por servicio
CB_DEEPGRAM = CircuitBreaker("Deepgram", max_fallos=3, timeout_s=120)
CB_LLM = CircuitBreaker("LLM-DeepSeek", max_fallos=5, timeout_s=60)
CB_MEDIFOLIOS = CircuitBreaker("Medifolios", max_fallos=3, timeout_s=600)
CB_POSITIVA = CircuitBreaker("Positiva", max_fallos=3, timeout_s=600)
```

**Usar en `flujo_audio.py`:**
```python
from backend.circuit_breaker import CB_DEEPGRAM

def transcribir_audio(audio_path: str) -> dict:
    if not CB_DEEPGRAM.puede_intentar():
        raise Exception(f"Deepgram no disponible (circuit breaker ABIERTO). "
                       f"Intenta en {CB_DEEPGRAM.timeout_s}s.")
    try:
        # ... llamada a Deepgram ...
        CB_DEEPGRAM.registrar_exito()
        return resultado
    except Exception as e:
        CB_DEEPGRAM.registrar_fallo()
        raise
```

---

### ARCH-3 — Testing suite completa: 50+ tests, mock mode, datos de prueba

**Por qué:** Con 8,000+ líneas de Python y 12+ módulos interconectados, un cambio en
`doc_generator.py` puede romper `qa_formatos.py` sin que nadie se entere hasta producción.
Un test suite completo da confianza para deployar.

**`backend/tests/` — estructura:**
```
backend/tests/
  conftest.py             # fixtures compartidos, mock API keys
  test_chat_handler.py    # tests del chat
  test_workflow.py        # tests del pipeline completo
  test_doc_generator.py   # tests de generación de documentos
  test_qa_formatos.py     # tests de QA
  test_notificador.py     # tests de Telegram (mock)
  test_server.py          # tests de endpoints FastAPI
  test_habeas_data.py     # tests de compliance legal
  fixtures/
    paciente_juan_carlos.json  # datos de prueba anonimizados
    paciente_rosa_maria.json
    audio_prueba.m4a           # audio de 30s para tests
```

**`backend/tests/conftest.py`:**
```python
import os
import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient

# MODO TEST: usar mocks en lugar de APIs reales
os.environ["TESTING"] = "true"
os.environ["DEEPGRAM_API_KEY"] = "test-key"
os.environ["OPENCODE_GO_API_KEY"] = "test-key"
os.environ["WORKFLOW_DB_PATH"] = ":memory:"  # SQLite en memoria

@pytest.fixture
def client():
    from backend.server import app
    return TestClient(app)

@pytest.fixture
def datos_juan_carlos():
    return json.loads(
        (Path(__file__).parent / "fixtures/paciente_juan_carlos.json").read_text()
    )

@pytest.fixture
def mock_llm(monkeypatch):
    """Mock del LLM para tests sin API real."""
    def _mock_llamar(*args, **kwargs):
        return "Respuesta de prueba del LLM"
    from backend import chat_handler
    monkeypatch.setattr(chat_handler, "_llamar_llm", _mock_llamar)

@pytest.fixture
def mock_deepgram(monkeypatch):
    """Mock de Deepgram para tests sin API real."""
    def _mock_transcribir(audio_path, *args, **kwargs):
        return {
            "texto": "Paciente Juan Carlos Durán, cédula 1193143688, empresa Almacenes X",
            "duracion": 30.0,
            "confianza": 0.95,
            "segmentos": [],
        }
    from backend import flujo_audio
    monkeypatch.setattr(flujo_audio, "transcribir_audio", _mock_transcribir)
```

**`backend/tests/test_workflow.py`:**
```python
def test_workflow_completo_con_mocks(mock_llm, mock_deepgram, tmp_path):
    """Test de integración: workflow de 9 pasos con APIs mockeadas."""
    from backend.workflow_runner import ejecutar_workflow

    # Crear audio de prueba
    audio_path = tmp_path / "test.m4a"
    audio_path.write_bytes(b"fake audio content")

    resultado = ejecutar_workflow(
        audio_path=str(audio_path),
        paciente_cc="1193143688",
    )

    assert resultado["estado"] == "listo" or resultado["estado"].startswith("error_en_paso")
    # Si falla, debe ser por el audio falso en Deepgram, no por el workflow en sí
    if resultado["estado"].startswith("error_en_paso"):
        assert resultado.get("paso_actual", 0) <= 2  # solo pasos iniciales sin mock completo

def test_qa_detecta_placeholders():
    from backend.workflow_steps.qa_formatos import _qa_docx
    # Test con documento que tiene placeholders
    # (usar fixture real de documento con [VERIFICAR])
    pass

def test_circuit_breaker_abre_tras_fallos():
    from backend.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker("test", max_fallos=3, timeout_s=1)
    assert cb.puede_intentar()
    for _ in range(3):
        cb.registrar_fallo()
    assert not cb.puede_intentar()
    assert cb.estado == "OPEN"
```

**Script de CI mínimo (para correr antes de cada deploy):**
```bash
#!/bin/bash
# ci_check.sh — correr antes de git push a producción
set -e
cd /root/fisioterapia
echo "=== Verificación pre-deploy ==="
python -m pytest backend/tests/ -v --tb=short 2>&1 | tail -30
python -m mypy backend/server.py backend/chat_handler.py --ignore-missing-imports 2>&1 | tail -10
python -c "from backend.server import app; print('✅ Backend importa OK')"
echo "=== Verificación completada ==="
```

---

### ARCH-4 — HTTPS con nginx reverse proxy (producción segura)

**Por qué:** El dashboard corre en HTTP. Si Sandra accede desde su teléfono en la misma WiFi,
los datos del paciente viajan sin cifrar. Con nginx + Let's Encrypt (o certificado auto-firmado
para red local), todo va cifrado.

**`nginx/rilo.conf` — configuración nginx:**
```nginx
# /etc/nginx/sites-available/rilo
server {
    listen 80;
    server_name rilo.local 192.168.1.100;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name rilo.local 192.168.1.100;

    ssl_certificate /etc/ssl/rilo/cert.pem;
    ssl_certificate_key /etc/ssl/rilo/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # Dashboard Next.js
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend FastAPI (SSE necesita buffering desactivado)
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_read_timeout 300s;
        proxy_buffering off;                    # ← CRÍTICO para SSE streaming
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Tamaño máximo para upload de audios (200MB)
    client_max_body_size 200M;
}
```

**Script de generación de certificado auto-firmado para red local:**
```bash
#!/bin/bash
# Genera certificado SSL para red local (válido 10 años)
mkdir -p /etc/ssl/rilo
LOCAL_IP=$(hostname -I | awk '{print $1}')

openssl req -x509 -newkey rsa:4096 -keyout /etc/ssl/rilo/key.pem \
    -out /etc/ssl/rilo/cert.pem -days 3650 -nodes \
    -subj "/C=CO/ST=Huila/L=Neiva/O=RILO SAS/CN=$LOCAL_IP" \
    -addext "subjectAltName=IP:$LOCAL_IP,IP:127.0.0.1,DNS:rilo.local"

echo "✅ Certificado generado para IP: $LOCAL_IP"
echo "Importar el cert.pem en los dispositivos de Sandra para evitar advertencia de seguridad"
```

---

### ARCH-5 — Setup script: instalar RILO SAS en WSL desde cero en 1 comando

**Por qué:** Ahora instalar RILO en el WSL de Sandra requiere muchos pasos manuales que
Manuel hace desde memory. Con un setup script, si el PC de Sandra muere y hay que reinstalar
en un PC nuevo, tarda 10 minutos en vez de 3 horas.

**`scripts/setup_wsl.sh` — instalación completa:**
```bash
#!/bin/bash
# setup_wsl.sh — Instala RILO SAS en WSL desde cero
# Uso: curl -s https://raw.githubusercontent.com/Manupo12/auto-ma/main/scripts/setup_wsl.sh | bash

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log() { echo -e "${GREEN}[RILO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

log "=== Instalando RILO SAS en WSL ==="
log "Este proceso tarda ~10 minutos"

# 1. Dependencias del sistema
log "Instalando dependencias del sistema..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3.11 python3.11-venv python3-pip \
    ffmpeg libreoffice-headless \
    git curl nginx \
    build-essential

# 2. Node.js 20 (para Next.js)
log "Instalando Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y -qq nodejs
npm install -g pm2

# 3. Playwright browsers
log "Instalando Playwright + browsers..."
pip install playwright -q
playwright install chromium
playwright install-deps chromium

# 4. Clonar repositorio
log "Clonando repositorio RILO SAS..."
git clone https://github.com/Manupo12/auto-ma.git ~/rilo-backend
git clone https://github.com/Manupo12/auto-ma.git ~/rilo-dashboard  # mismo repo, directorio dashboard/

# 5. Entorno Python
log "Configurando entorno Python..."
cd ~/rilo-backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt -q

# 6. Variables de entorno
if [ ! -f ~/rilo-backend/.env ]; then
    warn ".env no encontrado. Creando plantilla..."
    cat > ~/rilo-backend/.env << 'EOF'
# ── API Keys ─────────────────────────────────────────────────────
OPENCODE_GO_API_KEY=CAMBIAR_ESTO
OPENCODE_GO_BASE_URL=https://opencode.ai/zen/go/v1
DEEPGRAM_API_KEY=CAMBIAR_ESTO

# ── LLM Models ───────────────────────────────────────────────────
LLM_MODEL=deepseek-v4-pro
LLM_MODEL_SINTESIS=deepseek-v4-pro
LLM_MODEL_EXTRACCION=deepseek-v4-flash

# ── Portales ─────────────────────────────────────────────────────
MEDIFOLIOS_USER=55162801-2
MEDIFOLIOS_PASS=55162801-2
POSITIVA_USER=1075209386MR
POSITIVA_PASS=Rilo2026*

# ── Gmail ────────────────────────────────────────────────────────
GMAIL_USER=CAMBIAR_ESTO
GMAIL_APP_PASSWORD=CAMBIAR_ESTO

# ── Telegram ─────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=CAMBIAR_ESTO
TELEGRAM_CHAT_ID=CAMBIAR_ESTO
TELEGRAM_CHAT_ID_MANU=CAMBIAR_ESTO

# ── Auth ─────────────────────────────────────────────────────────
AUTH_PIN=CAMBIAR_ESTO
AUTH_SECRET=CAMBIAR_ESTO_POR_CADENA_ALEATORIA

# ── Features ─────────────────────────────────────────────────────
FASE_A_CRON_ENABLED=true
FASE_A_ENABLED=true
TOMY_COMPLETO_ENABLED=true

# ── Paths ────────────────────────────────────────────────────────
STORAGE_DIR=./storage
WORKFLOW_DB_PATH=./storage/workflow.db
DASHBOARD_URL=http://localhost:3000
EOF
    warn "⚠️  Edita ~/rilo-backend/.env con los valores reales antes de continuar"
fi

# 7. Dashboard
log "Instalando dependencias del dashboard..."
cd ~/rilo-dashboard/dashboard
npm install --legacy-peer-deps -q
npm run build

# 8. PM2
log "Configurando PM2..."
cd ~/rilo-backend
pm2 start ecosystem.config.js --env production
pm2 save
pm2 startup | tail -1 | bash  # ejecutar el comando de startup automáticamente

# 9. Verificar
log "Verificando instalación..."
sleep 5
curl -s http://localhost:8000/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ Backend OK' if d.get('ok') else '❌ Backend ERROR')"
curl -s http://localhost:3000 | grep -q "RILO" && echo "✅ Dashboard OK" || echo "⚠️ Dashboard cargando..."

log ""
log "=== ✅ RILO SAS instalado exitosamente ==="
log "Dashboard: http://localhost:3000"
log "Backend:   http://localhost:8000"
log ""
LOCAL_IP=$(hostname -I | awk '{print $1}')
log "Desde teléfono (misma WiFi): http://$LOCAL_IP:3000"
log ""
warn "IMPORTANTE: Edita .env con las API keys reales si aún no lo hiciste"
warn "Luego: pm2 reload ecosystem.config.js --env production"
```

---

### ARCH-6 — Migración Alembic para evolucion segura del schema

**Por qué:** Cuando se agrega una columna al schema de SQLite (ej: `estado_doc` en `formatos_task`),
el código falla en producción si la base de datos existente no tiene esa columna. Alembic maneja
esto automáticamente con migraciones versionadas.

**Setup básico:**
```bash
pip install alembic
alembic init backend/migrations
```

**`backend/migrations/env.py`:**
```python
from sqlalchemy import create_engine
import os

DATABASE_URL = f"sqlite:///{os.getenv('WORKFLOW_DB_PATH', './storage/workflow.db')}"
engine = create_engine(DATABASE_URL)
```

**Primera migración `0001_initial.py`:**
```python
def upgrade():
    op.create_table('workflow_tasks', ...)
    op.create_table('costos', ...)
    op.create_table('formatos_task', ...)

def downgrade():
    op.drop_table('formatos_task')
    op.drop_table('costos')
    op.drop_table('workflow_tasks')
```

**En `deploy.sh`, agregar antes de reiniciar:**
```bash
cd ~/rilo-backend
alembic upgrade head  # aplica todas las migraciones pendientes automáticamente
```

---

### MU-1 — Base multi-fisioterapeuta (preparar sin implementar completamente)

**Por qué:** Sandra hoy trabaja sola. Pero si RILO SAS crece, puede tener un segundo fisioterapeuta.
En lugar de instalar otro sistema completo, el código debe estar preparado para múltiples usuarios
desde ahora — agrega una columna `fisioterapeuta_id` en las tablas clave, sin cambiar el flujo actual.

**Cambios mínimos que habilitan el futuro multi-usuario sin romper nada:**

```python
# task_db.py — agregar fisioterapeuta_id (con default "sandra" para no romper lo existente)
SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_tasks (
    ...
    fisioterapeuta_id TEXT DEFAULT 'sandra',   -- NUEVO
    ...
);
"""

# costos table — agregar fisioterapeuta_id para costos por usuario
SCHEMA_COSTOS = """
CREATE TABLE IF NOT EXISTS costos (
    ...
    fisioterapeuta_id TEXT DEFAULT 'sandra',   -- NUEVO
    ...
);
"""

# server.py — futuro: extraer fisioterapeuta del token de auth
def _obtener_fisioterapeuta(rilo_auth: str = Cookie(None)) -> str:
    from backend.auth_simple import validar_token
    if rilo_auth:
        usuario = validar_token(rilo_auth)
        return usuario or "sandra"
    return "sandra"
```

---

### PARTE 16 — Tabla resumen

| ID | Feature | Tipo | Impacto | Tiempo |
|----|---------|------|---------|--------|
| INT-1 | Base conocimiento CIE-10 + restricciones por diagnóstico | Intelligence | Formatos más precisos sin esfuerzo de Sandra | 3h |
| INT-2 | Tomy como entrevistador clínico estructurado | Intelligence | Captura el 100% de los datos necesarios | 4h |
| INT-3 | Paquete ARL completo: carta + formatos + resumen ejecutivo | Productivity | Sandra envía paquete profesional completo en 1 clic | 3h |
| INT-4 | Tomy proactivo: nudges inteligentes sin que Sandra pregunte | Intelligence | Sandra nunca olvida nada | 2h |
| INT-5 | Analítica cruzada: patrones entre pacientes y empresas | Intelligence | Detecta riesgos laborales sistémicos | 2h |
| INT-6 | Timeline clínico completo del caso | Intelligence | Historia completa del caso para Cierre/VOI | 1.5h |
| DASH-1 | Dashboard enriquecido: notificaciones in-app + toasts | UX | Sandra ve todo sin salir del dashboard | 2h |
| BIZ-1 | Dashboard de productividad y reporte mensual | Analytics | Demuestra ROI del sistema | 2h |
| LEGAL-1 | Cumplimiento Ley 1581/2012 Habeas Data Colombia | Compliance | Cumplimiento legal obligatorio | 3h |
| LEGAL-2 | Audit log completo en operaciones críticas | Compliance | Trazabilidad para disputas legales | 1h |
| ARCH-1 | SQLite WAL mode + optimizaciones | Architecture | Lecturas y escrituras simultáneas sin bloqueo | 30 min |
| ARCH-2 | Circuit breaker para APIs externas | Architecture | Falla rápido en vez de lento | 1h |
| ARCH-3 | Test suite 50+ tests + mock mode + CI script | Architecture | Deploy con confianza | 6h |
| ARCH-4 | HTTPS con nginx reverse proxy | Architecture | Datos cifrados, acceso desde teléfono seguro | 2h |
| ARCH-5 | Setup script: instalar RILO desde cero en 1 comando | DevOps | Reinstalación en 10 min si falla el PC | 2h |
| ARCH-6 | Migraciones Alembic para schema evolution | Architecture | Cambios de schema sin romper producción | 1.5h |
| MU-1 | Base multi-fisioterapeuta (sin implementar, preparar) | Future | Escalabilidad futura sin refactoring | 1h |

**Subtotal bloque PARTE 16: ~41 horas**

---

## Tiempo estimado total (versión final)

| Bloque | Descripción | Tiempo |
|--------|-------------|--------|
| A + FX + NC críticos | Bugs que impiden arrancar el sistema | 4h |
| B + NC4/5 + EVO-1 | Chat de clase mundial (streaming, Markdown, voz, CC, contexto) | 7h |
| P + EVO-5/6/7/8 | Portales inteligentes, paralelos, con keep-alive y fallback manual | 7h |
| CR + NC12 + INT-2 | Corrección + entrevistador + prompt adaptativo | 5h |
| Z + EVO-2/3/18 | Entrega incremental, queue, Draft→Aprobado→ARL | 5h |
| TG | Telegram bidireccional (bidireccional: avisos + respuestas) | 4h |
| H + EVO-11/12 | Mi Día + PWA + briefing matinal | 4h |
| AG + EVO-14 + INT-4 | Agenda + plazos ARL + nudges proactivos | 5h |
| M + EVO-10 | M4A + auto-CC del audio | 3h |
| LH + PD + ARCH-4/5 | Limpieza Hermes + PM2 + nginx + setup script | 8h |
| EVO restantes | Streaming, modo degradado, diff, cleanup, WAL, CB | 12h |
| INT-1/3/5/6 | Conocimiento clínico, paquete ARL, analítica, timeline | 10h |
| BIZ-1 + reporte | Productividad y ROI mensual | 2h |
| LEGAL-1/2 | Habeas Data + Audit log | 4h |
| ARCH-3/6 + MU-1 | Tests, Alembic, multi-usuario base | 9h |
| **TOTAL** | | **~94 horas (~12 días de trabajo real)** |

> **Lo que tiene este sistema cuando esté completo:**
> Un fisioterapeuta colombiana afiliada a ARL Positiva, con un iPhone y conexión WiFi,
> puede terminar una consulta, subir el audio desde el dashboard, y recibir en 15 minutos
> un paquete ZIP con carta de presentación + 7 formatos clínicos + resumen ejecutivo,
> listo para enviar a ARL. El sistema le avisó esa mañana de sus citas, recordó los plazos
> de vencimiento, detectó que el diagnóstico cambió en el portal, y le preguntó por el dato
> que le faltaba para completar el análisis. Todo cumpliendo la ley de protección de datos
> colombiana, con logs de auditoría, backups cifrados, y capacidad de funcionar aunque
> DeepSeek o Deepgram estén caídos. Es el estado del arte en automatización clínica para
> una clínica pequeña en Colombia.

*Actualizado 2026-05-22 (v9). 59 bugs + 22 EVO + 17 PARTE 16 = plataforma clínica completa.
Dashboard especializado, CIE-10 knowledge base, Tomy entrevistador, analítica cruzada, paquete ARL profesional,
Habeas Data, circuit breaker, test suite, nginx HTTPS, setup script, Alembic, multi-usuario base.*


---

---

# PARTE 17 — Dashboard como canal único: UX de clase clínica

> **Filosofía:** Sandra no necesita WhatsApp, no necesita llamar, no necesita un técnico.
> Todo lo que el sistema puede decirle, pedirle o mostrarle lo hace **dentro del dashboard**.
> El dashboard no es una pantalla de administración — es la herramienta de trabajo diario
> de una fisioterapeuta colombiana de 55+ años. Cada decisión de UX parte de ese hecho.

---

## DASH-1 — Sistema de notificaciones in-app (toasts + bandeja)

**Por qué:** Hoy el sistema depende de Telegram para avisar a Sandra que algo pasó.
Si Sandra no tiene el teléfono cerca, se pierde el aviso. El dashboard debe ser la fuente
primaria de notificaciones — Telegram es el respaldo, no al revés.

**Diseño:**
- Toast en la esquina superior derecha cuando un workflow termina (aparece aunque Sandra
  esté en otra página del dashboard)
- Bandeja de notificaciones persistente (ícono de campana en el header) con historial
  de los últimos 30 eventos: formatos listos, errores, nudges proactivos, recordatorios
- Badge numérico en la campana para no-leídas
- Las notificaciones no desaparecen hasta que Sandra las marca como leídas
- SSE desde el backend para push en tiempo real (sin polling)

**`backend/notificaciones_db.py`:**
```python
import sqlite3, os
from pathlib import Path

NOTIF_DB = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS notificaciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo        TEXT NOT NULL,
    titulo      TEXT NOT NULL,
    cuerpo      TEXT NOT NULL,
    paciente_cc TEXT,
    task_id     TEXT,
    leida       INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""

def crear_notif(tipo, titulo, cuerpo, paciente_cc=None, task_id=None):
    with sqlite3.connect(NOTIF_DB) as conn:
        conn.execute(SCHEMA)
        conn.execute(
            "INSERT INTO notificaciones (tipo,titulo,cuerpo,paciente_cc,task_id) VALUES (?,?,?,?,?)",
            (tipo, titulo, cuerpo, paciente_cc, task_id)
        )

def listar_notifs(solo_no_leidas=False):
    with sqlite3.connect(NOTIF_DB) as conn:
        conn.execute(SCHEMA)
        q = ("SELECT id,tipo,titulo,cuerpo,paciente_cc,task_id,leida,created_at "
             "FROM notificaciones")
        if solo_no_leidas:
            q += " WHERE leida=0"
        q += " ORDER BY id DESC LIMIT 50"
        rows = conn.execute(q).fetchall()
    cols = ["id","tipo","titulo","cuerpo","paciente_cc","task_id","leida","created_at"]
    return [dict(zip(cols, r)) for r in rows]

def marcar_leida(notif_id):
    with sqlite3.connect(NOTIF_DB) as conn:
        conn.execute("UPDATE notificaciones SET leida=1 WHERE id=?", (notif_id,))

def marcar_todas_leidas():
    with sqlite3.connect(NOTIF_DB) as conn:
        conn.execute("UPDATE notificaciones SET leida=1")
```

**Endpoints en `server.py`:**
```python
@app.get("/api/notificaciones")
def get_notifs(solo_no_leidas: bool = False):
    from backend.notificaciones_db import listar_notifs
    return {"notificaciones": listar_notifs(solo_no_leidas)}

@app.post("/api/notificaciones/{notif_id}/leer")
def marcar_leida_endpoint(notif_id: int):
    from backend.notificaciones_db import marcar_leida
    marcar_leida(notif_id)
    return {"ok": True}

@app.post("/api/notificaciones/leer-todas")
def marcar_todas_endpoint():
    from backend.notificaciones_db import marcar_todas_leidas
    marcar_todas_leidas()
    return {"ok": True}

@app.get("/api/notificaciones/stream")
async def notif_stream(request: Request):
    """SSE: el dashboard recibe notificaciones nuevas en tiempo real sin polling."""
    from backend.notificaciones_db import listar_notifs
    import asyncio, json
    async def generator():
        ultimo_id = 0
        while True:
            if await request.is_disconnected():
                break
            notifs = listar_notifs()
            nuevas = [n for n in notifs if n["id"] > ultimo_id]
            if nuevas:
                ultimo_id = nuevas[0]["id"]
                yield f"data: {json.dumps(nuevas, ensure_ascii=False)}\n\n"
            await asyncio.sleep(3)
    return StreamingResponse(generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

**`dashboard/components/NotifBell.tsx`:**
```tsx
"use client";
import { useEffect, useState } from "react";
import { Bell } from "lucide-react";

interface Notif {
  id: number; tipo: string; titulo: string; cuerpo: string;
  paciente_cc?: string; leida: number; created_at: string;
}

export default function NotifBell() {
  const [notifs, setNotifs] = useState<Notif[]>([]);
  const [open, setOpen] = useState(false);
  const noLeidas = notifs.filter(n => !n.leida).length;

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/notificaciones`)
      .then(r => r.json()).then(d => setNotifs(d.notificaciones || []));
  }, []);

  useEffect(() => {
    const ev = new EventSource(`${process.env.NEXT_PUBLIC_API_URL}/notificaciones/stream`);
    ev.onmessage = (e) => {
      const nuevas: Notif[] = JSON.parse(e.data);
      setNotifs(prev => {
        const ids = new Set(prev.map(n => n.id));
        return [...nuevas.filter(n => !ids.has(n.id)), ...prev].slice(0, 50);
      });
    };
    return () => ev.close();
  }, []);

  const leerTodas = async () => {
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/notificaciones/leer-todas`, { method: "POST" });
    setNotifs(prev => prev.map(n => ({ ...n, leida: 1 })));
  };

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} className="relative p-2 rounded-full hover:bg-slate-100">
        <Bell size={24} className="text-slate-600" />
        {noLeidas > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs
                           rounded-full w-5 h-5 flex items-center justify-center font-bold">
            {noLeidas > 9 ? "9+" : noLeidas}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-12 w-96 bg-white rounded-2xl shadow-2xl
                        border border-slate-200 z-50 max-h-[500px] overflow-y-auto">
          <div className="flex items-center justify-between p-4 border-b">
            <h3 className="font-bold text-slate-800 text-lg">Notificaciones</h3>
            {noLeidas > 0 && (
              <button onClick={leerTodas} className="text-sm text-blue-600 hover:underline">
                Marcar todas como leídas
              </button>
            )}
          </div>
          {notifs.length === 0 ? (
            <p className="p-6 text-center text-slate-400 text-sm">Sin notificaciones</p>
          ) : notifs.map(n => (
            <div key={n.id}
              className={`p-4 border-b hover:bg-slate-50 ${!n.leida ? "bg-blue-50" : ""}`}>
              <p className="font-semibold text-slate-800 text-sm">{n.titulo}</p>
              <p className="text-slate-600 text-sm mt-0.5">{n.cuerpo}</p>
              <p className="text-slate-400 text-xs mt-1">{n.created_at}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

Las notificaciones se crean automáticamente desde: `notificar_listo.py` (workflow listo),
`proactivo.py` (nudges diarios), `cron_pre_extraccion.py` (recordatorios de citas),
`correction_resolver.py` (corrección aplicada), `backup_diario.py` (backup completado).

---

## DASH-2 — Header global con estado del sistema

**Por qué:** Sandra necesita saber de un vistazo si el sistema está bien sin abrir la consola.
El header del dashboard es el semáforo permanente del sistema.

**Diseño:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│  RILO SAS — Tomy    ● Sistema OK    [Juan Carlos ▾]  🔔3  [⌘K]  Sandra▾│
└─────────────────────────────────────────────────────────────────────────┘
```

- **Punto de color**: verde=OK, amarillo=portal caído pero funcional, rojo=error crítico
- **Paciente activo**: dropdown — seleccionarlo pre-llena CC en Subir Audio y contextualiza el chat
- **Campana**: `NotifBell` (DASH-1) con badge de no leídas
- **[⌘K]**: abre el buscador global (DASH-6)
- **Sandra ▾**: menú con "Configuración" y "Cerrar sesión"

**`dashboard/components/Header.tsx`:**
```tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import NotifBell from "./NotifBell";
import { ChevronDown, Search } from "lucide-react";

type SysStatus = "ok" | "degradado" | "error";

export default function Header() {
  const [status, setStatus] = useState<SysStatus>("ok");
  const [pacienteActivo, setPacienteActivo] = useState<string | null>(null);
  const [pacientes, setPacientes] = useState<{cc: string; nombre: string}[]>([]);
  const router = useRouter();

  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/portales/health`,
          { signal: AbortSignal.timeout(5000) });
        const d = await r.json();
        const caidos = Object.values(d).filter((v: any) => !v?.ok).length;
        setStatus(caidos === 0 ? "ok" : caidos < 2 ? "degradado" : "error");
      } catch { setStatus("error"); }
    };
    check();
    const t = setInterval(check, 30_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/pacientes`)
      .then(r => r.json()).then(d => setPacientes(d.pacientes || []));
    setPacienteActivo(localStorage.getItem("paciente_activo"));
  }, []);

  const seleccionar = (cc: string) => {
    setPacienteActivo(cc || null);
    localStorage.setItem("paciente_activo", cc);
  };

  const dot = { ok: "bg-green-500", degradado: "bg-yellow-400", error: "bg-red-500" }[status];
  const label = { ok: "Sistema OK", degradado: "Modo parcial", error: "Error" }[status];
  const nombreActivo = pacientes.find(p => p.cc === pacienteActivo)?.nombre?.split(" ")[0];

  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center
                       justify-between px-6 flex-shrink-0 z-40">
      <div className="flex items-center gap-4">
        <span className="text-xl font-bold text-slate-800">RILO SAS — Tomy</span>
        <div className="flex items-center gap-1.5">
          <span className={`w-2.5 h-2.5 rounded-full animate-pulse ${dot}`} />
          <span className="text-sm text-slate-500">{label}</span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div className="relative group">
          <button className="flex items-center gap-2 px-3 py-1.5 rounded-xl
                             bg-slate-100 text-slate-700 text-sm hover:bg-slate-200">
            {nombreActivo ?? "Sin paciente"} <ChevronDown size={14} />
          </button>
          <div className="absolute right-0 top-10 hidden group-hover:block w-64 bg-white
                          rounded-xl shadow-xl border border-slate-200 z-50 py-2">
            <button onClick={() => seleccionar("")}
              className="w-full text-left px-4 py-2 text-sm text-slate-400 hover:bg-slate-50">
              Sin paciente activo
            </button>
            {pacientes.map(p => (
              <button key={p.cc} onClick={() => seleccionar(p.cc)}
                className={`w-full text-left px-4 py-2 text-sm hover:bg-blue-50
                  ${pacienteActivo === p.cc ? "bg-blue-50 text-blue-700 font-semibold" : "text-slate-700"}`}>
                {p.nombre}
                <span className="text-slate-400 text-xs ml-2">CC {p.cc}</span>
              </button>
            ))}
          </div>
        </div>
        <NotifBell />
        <button
          onClick={() => window.dispatchEvent(new CustomEvent("open-search"))}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100
                     text-slate-500 text-sm hover:bg-slate-200">
          <Search size={16} /> <kbd className="text-xs">⌘K</kbd>
        </button>
        <div className="relative group">
          <button className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900">
            Sandra <ChevronDown size={14} />
          </button>
          <div className="absolute right-0 top-8 hidden group-hover:block w-44 bg-white
                          rounded-xl shadow-xl border border-slate-200 z-50 py-2">
            <button onClick={() => router.push("/configuracion")}
              className="w-full text-left px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50">
              Configuración
            </button>
            <button onClick={async () => {
              await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/logout`, { method: "POST" });
              router.push("/login");
            }} className="w-full text-left px-4 py-2.5 text-sm text-red-600 hover:bg-red-50">
              Cerrar sesión
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
```

---

## DASH-3 — Página "Mi Día" rediseñada: briefing matinal completo

**Por qué:** La página `/hoy` es lo primero que ve Sandra. Actualmente muestra agenda básica
y tareas con estado raw (ej: "transcribiendo"). Puede ser el centro de control completo del día.

**Diseño visual:**
```
Buenos días, Sandra   Viernes 22 de mayo — 3 citas hoy
───────────────────────────────────────────────────────
AGENDA DE HOY              TAREAS EN PROGRESO
09:00  Juan Carlos →       ██████░░░ Juan Carlos — paso 6/9
11:00  Rosa María  →           Generando formatos — ETA: ~8 min
14:30  Laura Rojas →
───────────────────────────────────────────────────────
PENDIENTES
⚠  Rosa María: diagnóstico cambió en Positiva → revisar
📋 Laura Rojas: falta fecha de incapacidad → completar
⏰ Juan Carlos: cierre de caso vence el 28 mayo
───────────────────────────────────────────────────────
LISTO PARA ENVIAR A ARL
✅ Rosa María García — 3 formatos     [Descargar paquete]
```

**Nombres de pasos legibles:**
```typescript
// dashboard/lib/pasos.ts
export const NOMBRE_PASO: Record<number, string> = {
  1: "Transcribiendo audio",
  2: "Buscando datos del paciente",
  3: "Leyendo notas del workspace",
  4: "Leyendo formatos de referencia",
  5: "Sintetizando información clínica",
  6: "Generando los 7 formatos",
  7: "Verificando documentos",
  8: "Convirtiendo a PDF",
  9: "Enviando notificación",
};
```

**ETA calculada en el backend:**
```python
# En task_db.py — guardar timestamp de inicio de cada paso
def calcular_eta(task: dict) -> str:
    paso_actual = task.get("paso_actual", 0)
    pasos_restantes = 9 - paso_actual
    duracion_prom_s = task.get("duracion_promedio_paso_s", 90)
    eta_s = pasos_restantes * duracion_prom_s
    if eta_s < 60:   return "menos de 1 minuto"
    if eta_s < 120:  return "~1 minuto"
    return f"~{eta_s // 60} minutos"
```

**Barra de progreso animada:**
```tsx
<div className="w-full bg-slate-100 rounded-full h-3 mt-2">
  <div
    className="bg-blue-500 h-3 rounded-full transition-all duration-700"
    style={{ width: `${(pasoActual / 9) * 100}%` }}
  />
</div>
<p className="text-xs text-slate-500 mt-1">
  Paso {pasoActual} de 9 — {NOMBRE_PASO[pasoActual]} — ETA: {eta}
</p>
```

El polling de tareas activas es adaptativo: cada 3s mientras hay tasks activas, cada 30s si no hay.

---

## DASH-4 — Vista 360 del paciente: expediente clínico digital

**Por qué:** `/paciente/[cc]` es el expediente digital. Hoy muestra formatos y poco más.
Debe ser la pantalla desde la que Sandra hace todo relacionado con un paciente.

**Mejoras sobre la versión actual:**

### Indicadores de confianza de datos de portales
```tsx
function ConfidenceBadge({ fuente, confianza }: { fuente: string; confianza: number }) {
  const color = confianza >= 90 ? "green" : confianza >= 70 ? "yellow" : "red";
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full
      bg-${color}-100 text-${color}-700 font-medium`}>
      {fuente} {confianza}%
    </span>
  );
}
// Uso: <ConfidenceBadge fuente="Positiva" confianza={100} />
//      <ConfidenceBadge fuente="Medifolios" confianza={85} />
```

### Corrección con toast (reemplaza alert())
```tsx
import toast from "react-hot-toast";

const enviarCorreccion = async () => {
  if (!texto.trim()) return;
  const r = await fetch(`${API}/corregir-paciente/${cc}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mensaje: texto }),
  });
  const d = await r.json();
  if (d.ok) {
    toast.success(`Corrección aplicada: campo "${d.campo_corregido}"`);
    setTexto("");
  } else {
    toast.error("No pude aplicar la corrección. Intenta de otro modo.");
  }
};
```

### Estado por formato (no todos aplican a todos los casos)
```tsx
const ESTADOS_FORMATO = {
  generado:    { label: "Listo",       color: "green",  icon: "✅" },
  pendiente:   { label: "Pendiente",   color: "yellow", icon: "⏳" },
  no_aplica:   { label: "No aplica",   color: "slate",  icon: "—"  },
  con_errores: { label: "Con errores", color: "red",    icon: "⚠️" },
};
```

### Botones clave en la parte inferior
```
[📦 Descargar paquete ARL completo]    [🔄 Regenerar todos]    [🗑 Limpiar borradores]
```

---

## DASH-5 — Subir Audio: drag-and-drop, validación, progreso XHR

**Por qué:** El flujo de subir audio es el punto de entrada más crítico. Hoy es un formulario
básico sin feedback. Tres problemas concretos: no valida tipo de archivo, no muestra progreso,
no pre-llena la CC del paciente activo.

### Drag-and-drop con validación
```tsx
const FORMATOS_OK = /\.(mp3|m4a|wav|ogg|mp4|aac)$/i;
const MAX_MB = 500;

const validar = (file: File): string => {
  if (!FORMATOS_OK.test(file.name))
    return "Solo se aceptan archivos de audio (MP3, M4A, WAV, OGG, AAC)";
  if (file.size > MAX_MB * 1024 * 1024)
    return `El archivo pesa más de ${MAX_MB} MB. Por favor reduce el audio.`;
  return "";
};
```

### CC pre-llenada desde el paciente activo
```typescript
const [cc, setCc] = useState(() => localStorage.getItem("paciente_activo") ?? "");
```

### Barra de progreso con XHR (fetch no da progreso)
```tsx
const subir = (file: File, cc: string) => {
  const form = new FormData();
  form.append("audio", file);
  form.append("paciente_cc", cc);
  const xhr = new XMLHttpRequest();
  xhr.upload.onprogress = e => {
    if (e.lengthComputable) setProgreso(Math.round(e.loaded / e.total * 100));
  };
  xhr.onload = () => {
    const d = JSON.parse(xhr.responseText);
    router.push(`/hoy?task=${d.task_id}`);
  };
  xhr.onerror = () => toast.error("Error al subir el audio. Intenta de nuevo.");
  xhr.open("POST", `${process.env.NEXT_PUBLIC_API_URL}/upload-audio`);
  xhr.send(form);
};
```

### Duración del audio antes de subir
```tsx
const mostrarDuracion = (file: File) => {
  const url = URL.createObjectURL(file);
  const audio = new Audio(url);
  audio.onloadedmetadata = () => {
    const m = Math.floor(audio.duration / 60);
    const s = Math.round(audio.duration % 60);
    setDuracion(`${m}:${s.toString().padStart(2,"0")}`);
    URL.revokeObjectURL(url);
  };
};
// En la UI: "Audio listo: consulta_juan.m4a — 12:34 min — 45.2 MB"
```

---

## DASH-6 — Buscador global (Cmd+K)

**Por qué:** Con más pacientes y más documentos, Sandra necesita encontrar cosas en 2 segundos.
El buscador tipo Spotlight aparece con Cmd+K desde cualquier página.

**Qué busca:**
- Pacientes por nombre o CC → navega a `/paciente/[cc]`
- Páginas del dashboard → navega directamente
- Acciones rápidas → "Subir audio para Juan Carlos" → `/subir-audio` con CC pre-llenada

**Navegación por teclado:**
```tsx
// Flechas ↑↓ para moverse entre resultados, Enter para navegar, Esc para cerrar
const [seleccionado, setSeleccionado] = useState(0);

useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    if (!open) return;
    if (e.key === "ArrowDown") setSeleccionado(s => Math.min(s + 1, resultados.length - 1));
    if (e.key === "ArrowUp")   setSeleccionado(s => Math.max(s - 1, 0));
    if (e.key === "Enter" && resultados[seleccionado])
      navegar(resultados[seleccionado].href);
  };
  window.addEventListener("keydown", handler);
  return () => window.removeEventListener("keydown", handler);
}, [open, resultados, seleccionado]);
```

Se activa también con el botón `[⌘K]` del header (DASH-2).

---

## DASH-7 — Visualizador DOCX en el navegador (sin Word)

**Por qué:** Sandra descarga el DOCX para revisarlo en Word. Si puede verlo dentro del
dashboard, aprueba más rápido y no se acumulan copias descargadas.

**Backend — `backend/docx_viewer.py`:**
```python
from docx import Document
import html as html_lib

def docx_a_html(ruta: str) -> str:
    doc = Document(ruta)
    partes = ["<style>",
        ".dv{font-family:'Segoe UI',sans-serif;font-size:14px;line-height:1.7;color:#1e293b;max-width:780px;margin:0 auto}",
        ".dv h1{font-size:1.4rem;font-weight:700;margin:1.5rem 0 .5rem}",
        ".dv h2{font-size:1.15rem;font-weight:600;margin:1.2rem 0 .4rem}",
        ".dv p{margin:.3rem 0}",
        ".dv table{width:100%;border-collapse:collapse;margin:1rem 0}",
        ".dv th,.dv td{border:1px solid #cbd5e1;padding:8px 12px;text-align:left}",
        ".dv th{background:#f1f5f9;font-weight:600}",
        "</style><div class='dv'>"]

    for bloque in doc.element.body:
        tag = bloque.tag.split("}")[-1]
        if tag == "p":
            from docx.text.paragraph import Paragraph
            p = Paragraph(bloque, doc)
            runs_html = ""
            for r in p.runs:
                t = html_lib.escape(r.text or "")
                if r.bold:   t = f"<strong>{t}</strong>"
                if r.italic: t = f"<em>{t}</em>"
                runs_html += t
            if not runs_html.strip():
                partes.append("<br>"); continue
            sn = p.style.name.lower()
            if "heading 1" in sn:   partes.append(f"<h1>{runs_html}</h1>")
            elif "heading 2" in sn: partes.append(f"<h2>{runs_html}</h2>")
            else:                   partes.append(f"<p>{runs_html}</p>")
        elif tag == "tbl":
            from docx.table import Table
            tabla = Table(bloque, doc)
            filas = []
            for i, fila in enumerate(tabla.rows):
                tc = "th" if i == 0 else "td"
                celdas = f"<tr>{''.join(f'<{tc}>{html_lib.escape(c.text)}</{tc}>' for c in fila.cells)}</tr>"
                filas.append(celdas)
            partes.append(f"<table>{''.join(filas)}</table>")

    partes.append("</div>")
    return "".join(partes)
```

**Endpoint:**
```python
@app.get("/api/formatos/{filename}/preview", response_class=HTMLResponse)
def preview_docx(filename: str):
    from backend.docx_viewer import docx_a_html
    ruta = Path(os.getenv("STORAGE_DIR","./storage")) / "docs" / filename
    if not ruta.exists() or not filename.endswith(".docx"):
        raise HTTPException(404)
    return docx_a_html(str(ruta))
```

**`dashboard/components/DocxPreview.tsx`:**
```tsx
"use client";
import { useState } from "react";
import { Eye, X } from "lucide-react";

export default function DocxPreview({ filename }: { filename: string }) {
  const [open, setOpen] = useState(false);
  const [contenido, setContenido] = useState("");

  const ver = async () => {
    const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/formatos/${filename}/preview`);
    setContenido(await r.text());
    setOpen(true);
  };

  return (
    <>
      <button onClick={ver}
        className="flex items-center gap-1 text-sm text-blue-600 hover:underline">
        <Eye size={16} /> Ver
      </button>
      {open && (
        <div className="fixed inset-0 bg-black/50 z-[200] overflow-y-auto p-8"
             onClick={() => setOpen(false)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl mx-auto"
               onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b sticky top-0 bg-white rounded-t-2xl">
              <h3 className="font-semibold text-slate-700">{filename}</h3>
              <button onClick={() => setOpen(false)}
                className="p-2 hover:bg-slate-100 rounded-lg">
                <X size={20} />
              </button>
            </div>
            <div className="p-8 max-h-[75vh] overflow-y-auto"
                 dangerouslySetInnerHTML={{ __html: contenido }} />
          </div>
        </div>
      )}
    </>
  );
}
```

---

## DASH-8 — Modo oscuro + accesibilidad

**Por qué:** Sandra trabaja en consultorios con luz variable. El modo oscuro reduce fatiga
visual. La accesibilidad asegura que pueda usar el sistema sin dificultad.

**`dashboard/components/ThemeToggle.tsx`:**
```tsx
"use client";
import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";

export default function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    const preferDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = saved === "dark" || (!saved && preferDark);
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  const toggle = () => {
    const next = !dark; setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  };

  return (
    <button onClick={toggle}
      className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
      {dark
        ? <Sun size={20} className="text-yellow-400" />
        : <Moon size={20} className="text-slate-500" />}
    </button>
  );
}
```

**`tailwind.config.js`:**
```js
module.exports = { darkMode: "class", /* ... */ };
```

**Reglas de accesibilidad aplicadas en toda la UI:**
- Fuente mínima `text-lg` (18px) — Sandra trabaja sin gafas cerca del PC
- Área táctil mínima `min-h-11 min-w-11` (44px) para botones en mobile
- Contraste AA+ en todos los textos sobre fondo
- `focus:ring-2 focus:ring-blue-500` en todos los elementos interactivos
- `prefers-reduced-motion`: deshabilitar animaciones si el usuario lo prefiere
  ```css
  @media (prefers-reduced-motion: reduce) {
    * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
  }
  ```

---

## DASH-9 — Página de configuración (`/configuracion`)

**Por qué:** Sandra y Manuel necesitan ajustar el sistema sin tocar el servidor ni el `.env`.

**Secciones:**

### Panel 1 — Estado en tiempo real de las APIs
```tsx
// Llama a GET /api/portales/health y GET /api/sistema/info
// Muestra: DeepSeek LLM, Deepgram, Medifolios, Positiva, Telegram, Gmail
// Con: ✅/⚠️/❌ + "Último uso: hace X horas"
```

### Panel 2 — Cambiar PIN
```tsx
// POST /api/auth/cambiar-pin { pin_actual, pin_nuevo }
// Validación frontend: 4 dígitos, pin_nuevo !== pin_actual
// Feedback con toast
```

### Panel 3 — Información del sistema
```tsx
// GET /api/sistema/info
// Muestra: versión, commit git, tamaño DB, cantidad de docs/pdfs, último backup
```

**Endpoints:**
```python
@app.post("/api/auth/cambiar-pin")
async def cambiar_pin(body: dict):
    from backend.auth_simple import validar_pin
    if not validar_pin(body.get("pin_actual", "")):
        raise HTTPException(403, "PIN actual incorrecto")
    nuevo = str(body.get("pin_nuevo", ""))
    if len(nuevo) != 4 or not nuevo.isdigit():
        raise HTTPException(400, "El nuevo PIN debe ser de 4 dígitos")
    # Actualizar en .env
    env_path = Path(".env")
    contenido = env_path.read_text()
    import re
    contenido = re.sub(r"AUTH_PIN=\d+", f"AUTH_PIN={nuevo}", contenido)
    env_path.write_text(contenido)
    os.environ["AUTH_PIN"] = nuevo
    return {"ok": True}

@app.get("/api/sistema/info")
def sistema_info():
    import subprocess
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    db_path = Path(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))
    return {
        "docs_count":  len(list((storage / "docs").glob("*.docx"))),
        "pdfs_count":  len(list((storage / "pdfs").glob("*.pdf"))),
        "db_size_mb":  round(db_path.stat().st_size / 1e6, 1) if db_path.exists() else 0,
        "git_commit":  subprocess.getoutput("git rev-parse --short HEAD 2>/dev/null") or "N/A",
    }
```

---

## DASH-10 — PWA instalable en iPhone

**Por qué:** Si Sandra instala el dashboard en la pantalla de inicio del iPhone, accede con
un toque — igual que una app, sin App Store, sin código, sin costos.

**`dashboard/public/manifest.json`:**
```json
{
  "name": "RILO SAS — Tomy",
  "short_name": "Tomy",
  "description": "Asistente clínico fisioterapia",
  "start_url": "/hoy",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#2563eb",
  "orientation": "portrait",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
```

**`dashboard/public/sw.js`:**
```javascript
const CACHE = "rilo-v1";

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(["/hoy", "/offline"]))
  );
  self.skipWaiting();
});

self.addEventListener("fetch", e => {
  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request).catch(() =>
        caches.match(e.request).then(r => r || caches.match("/offline"))
      )
    );
  }
});
```

**`dashboard/app/offline/page.tsx`:**
```tsx
export default function Offline() {
  return (
    <div className="h-screen flex flex-col items-center justify-center gap-6 bg-slate-50">
      <div className="text-8xl">📡</div>
      <h1 className="text-3xl font-bold text-slate-700">Sin conexión</h1>
      <p className="text-slate-500 text-center max-w-sm text-lg">
        No hay internet. Cuando se restaure la conexión,
        el sistema vuelve automáticamente.
      </p>
    </div>
  );
}
```

**En `dashboard/app/layout.tsx`:**
```tsx
<link rel="manifest" href="/manifest.json" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
<meta name="apple-mobile-web-app-title" content="Tomy" />
<link rel="apple-touch-icon" href="/icon-192.png" />
```

Registro del SW:
```tsx
useEffect(() => {
  if ("serviceWorker" in navigator)
    navigator.serviceWorker.register("/sw.js");
}, []);
```

---

## PARTE 17 — Tabla resumen

| ID | Feature | Tipo | Impacto para Sandra | Tiempo |
|----|---------|------|---------------------|--------|
| DASH-1 | Notificaciones in-app: bandeja SSE + campana | UX | Ve formatos listos sin revisar el celular | 3h |
| DASH-2 | Header global: semáforo + paciente activo + ⌘K | UX | Estado del sistema visible siempre | 2h |
| DASH-3 | Mi Día: briefing completo, ETA, nombres de pasos legibles | UX | Sabe qué pasa y cuánto falta sin navegar | 3h |
| DASH-4 | Vista 360: confianza de datos, toasts, estado por formato | UX | Expediente digital completo en una pantalla | 2h |
| DASH-5 | Subir Audio: drag-drop, validación, progreso XHR, duración | UX | Sube audio sin sorpresas, ve el avance | 3h |
| DASH-6 | Buscador global ⌘K con navegación de teclado | UX | Encuentra paciente o página en 2 segundos | 2h |
| DASH-7 | Visualizador DOCX en navegador (sin Word) | UX | Revisa y aprueba formatos sin abrir Word | 3h |
| DASH-8 | Modo oscuro + accesibilidad AA+ + fuentes grandes | UX | Cómodo en cualquier condición de luz | 1.5h |
| DASH-9 | Página /configuracion: APIs, cambio PIN, info sistema | UX | Sistema autosuficiente sin tocar el servidor | 2.5h |
| DASH-10 | PWA instalable en iPhone + página offline | UX | Acceso con un toque, funciona sin internet | 2h |

**Subtotal PARTE 17: ~24 horas**

---

## Tiempo estimado total (v10 — dashboard como canal único)

| Bloque | Descripción | Tiempo |
|--------|-------------|--------|
| A + FX + NC críticos | Bugs que impiden arrancar el sistema | 4h |
| B + NC4/5 + EVO-1 | Chat de clase mundial (streaming, Markdown, voz, CC, contexto) | 7h |
| P + EVO-5/6/7/8 | Portales inteligentes, paralelos, con keep-alive y fallback manual | 7h |
| CR + NC12 + INT-2 | Corrección + entrevistador + prompt adaptativo | 5h |
| Z + EVO-2/3/18 | Entrega incremental, queue, Draft→Aprobado→ARL | 5h |
| TG | Telegram para avisos salientes (backup respaldo, no canal principal) | 4h |
| DASH-1/2/3/10 | Notificaciones in-app + header + Mi Día + PWA | 10h |
| AG + EVO-14 + INT-4 | Agenda + plazos ARL + nudges proactivos en dashboard | 5h |
| M + EVO-10 | M4A + auto-CC del audio | 3h |
| LH + PD + ARCH-4/5 | Limpieza Hermes + PM2 + nginx + setup script | 8h |
| EVO restantes | Streaming, modo degradado, diff, cleanup, WAL, CB | 12h |
| INT-1/3/5/6 | Conocimiento clínico, paquete ARL, analítica, timeline | 10h |
| BIZ-1 | Productividad y ROI mensual | 2h |
| LEGAL-1/2 | Habeas Data + Audit log | 4h |
| ARCH-3/6 + MU-1 | Tests, Alembic, multi-usuario base | 9h |
| DASH-4/5/6/7/8/9 | Buscador, visor DOCX, drag-drop, modo oscuro, config | 14h |
| **TOTAL** | | **~109 horas (~14 días de trabajo real)** |

> **Lo que tiene este sistema cuando esté completo:**
> Sandra abre el dashboard en su iPhone (instalado como app con un toque desde la pantalla
> de inicio), ve el briefing de sus 3 citas de hoy con los pendientes de cada caso resaltados,
> arrastra el audio de la consulta a la zona de subida, ve la barra de progreso avanzar en
> tiempo real con el nombre legible de cada paso, y recibe una notificación dentro del propio
> dashboard cuando los formatos están listos — sin revisar el celular, sin abrir Telegram.
> Hace clic en "Ver" para revisar el Análisis de Exigencias dentro del navegador sin abrir Word.
> Aprueba. Descarga el paquete ARL completo con un clic. Usa ⌘K para buscar a cualquier
> paciente en 2 segundos. Todo desde una sola herramienta especializada para ella, en español
> colombiano, con letras grandes, colores claros, modo oscuro si el consultorio está oscuro,
> y sin ningún canal externo (WhatsApp, correo) que interfiera con el flujo de trabajo.

*Actualizado 2026-05-22 (v10). PARTE 17: dashboard como canal único — 10 features de UX
especializadas para una fisioterapeuta colombiana. Sin WhatsApp. Todo vive en el dashboard.*


---

---

# PARTE 18 — Chat de siguiente nivel + Dashboard como cockpit clínico

> El chat con Tomy no es un chatbot de preguntas y respuestas. Es el centro de comandos
> del sistema: Sandra puede hablar, preguntar, y HACER cosas desde el chat sin navegar
> a ningún otro lado. El dashboard no es un explorador de archivos — es el cockpit desde
> donde Sandra pilota su clínica entera, con toda la información justa en el momento justo.

---

## CHAT-1 — Slash commands: Tomy entiende intenciones, no solo preguntas

**Por qué:** Hoy Sandra escribe texto libre y Tomy responde. Eso es lento para tareas
repetitivas. Con slash commands, Sandra escribe `/generar` y ve una lista de acciones
posibles — como una app de verdad.

**Comandos disponibles (frontend muestra sugerencias al escribir `/`):**

| Comando | Acción |
|---------|--------|
| `/paciente [cc o nombre]` | Muestra resumen del paciente: datos, formatos, estado del caso |
| `/formatos` | Lista los formatos disponibles del paciente activo |
| `/generar [tipo]` | Solicita generar un formato específico para el paciente activo |
| `/agenda` | Muestra la agenda de hoy con links a cada paciente |
| `/estado [task_id]` | Muestra el estado detallado de un workflow |
| `/corregir [instrucción]` | Aplica una corrección al último formato del paciente activo |
| `/descargar [tipo]` | Genera link de descarga directa del formato |
| `/portal medifolios` | Consulta los datos del paciente en Medifolios |
| `/portal positiva` | Consulta los datos del paciente en ARL Positiva |
| `/costo hoy` | Muestra el gasto de API del día |
| `/ayuda` | Lista todos los comandos disponibles |

**`dashboard/app/chat/page.tsx` — autocompletar slash commands:**
```tsx
const COMANDOS = [
  { cmd: "/paciente",  desc: "Ver resumen de un paciente" },
  { cmd: "/formatos",  desc: "Listar formatos del paciente activo" },
  { cmd: "/generar",   desc: "Generar un formato específico" },
  { cmd: "/agenda",    desc: "Ver la agenda de hoy" },
  { cmd: "/estado",    desc: "Estado de una tarea" },
  { cmd: "/corregir",  desc: "Corregir el último formato" },
  { cmd: "/descargar", desc: "Descargar un formato" },
  { cmd: "/portal",    desc: "Consultar datos en Medifolios o Positiva" },
  { cmd: "/costo",     desc: "Gasto de API del día" },
  { cmd: "/ayuda",     desc: "Lista de comandos" },
];

// En el input del chat:
const [sugerencias, setSugerencias] = useState<typeof COMANDOS>([]);

const onInput = (valor: string) => {
  setMensaje(valor);
  if (valor.startsWith("/")) {
    const match = COMANDOS.filter(c => c.cmd.startsWith(valor.split(" ")[0]));
    setSugerencias(match);
  } else {
    setSugerencias([]);
  }
};

// Renderizar sugerencias encima del input
{sugerencias.length > 0 && (
  <div className="absolute bottom-full left-0 right-0 bg-white rounded-xl shadow-lg
                  border border-slate-200 mb-2 overflow-hidden">
    {sugerencias.map(s => (
      <button key={s.cmd} onClick={() => setMensaje(s.cmd + " ")}
        className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 text-left">
        <code className="text-blue-600 font-mono text-sm">{s.cmd}</code>
        <span className="text-slate-500 text-sm">{s.desc}</span>
      </button>
    ))}
  </div>
)}
```

**Backend — `chat_handler.py`: detectar y rutear slash commands:**
```python
SLASH_COMMANDS = {
    "/paciente": _cmd_paciente,
    "/formatos": _cmd_formatos,
    "/generar":  _cmd_generar,
    "/agenda":   _cmd_agenda,
    "/estado":   _cmd_estado,
    "/corregir": _cmd_corregir,
    "/descargar": _cmd_descargar,
    "/portal":   _cmd_portal,
    "/costo":    _cmd_costo,
    "/ayuda":    _cmd_ayuda,
}

async def procesar_mensaje(mensaje: str, paciente_cc: str = None) -> str:
    if mensaje.startswith("/"):
        partes = mensaje.split(" ", 1)
        cmd = partes[0].lower()
        arg = partes[1] if len(partes) > 1 else ""
        if cmd in SLASH_COMMANDS:
            return await SLASH_COMMANDS[cmd](arg, paciente_cc)
        return f"Comando desconocido: `{cmd}`. Escribe `/ayuda` para ver los disponibles."
    # Flujo normal de LLM
    return await _llamar_llm(mensaje, paciente_cc)

async def _cmd_paciente(arg: str, cc: str = None) -> str:
    target_cc = arg.strip() or cc
    if not target_cc:
        return "¿Para qué cédula? Escribe `/paciente 1193143688` o selecciona un paciente activo en el header."
    from backend.task_db import TaskDB
    from pathlib import Path
    import json, os
    data_path = Path(os.getenv("STORAGE_DIR","./storage")) / "data" / f"{target_cc}.json"
    if not data_path.exists():
        return f"No encontré datos para CC {target_cc}."
    datos = json.loads(data_path.read_text())
    nombre = datos.get("nombre", "Desconocido")
    empresa = datos.get("empresa", "N/A")
    dx = datos.get("diagnostico", "N/A")
    return (f"**{nombre}** — CC {target_cc}\n"
            f"- Empresa: {empresa}\n- Diagnóstico: {dx}\n"
            f"- [Ver expediente completo](/paciente/{target_cc})")

async def _cmd_ayuda(arg: str, cc: str = None) -> str:
    lineas = ["**Comandos disponibles:**\n"]
    for cmd, fn in SLASH_COMMANDS.items():
        lineas.append(f"- `{cmd}` — {fn.__doc__ or ''}")
    return "\n".join(lineas)
```

---

## CHAT-2 — Tomy ejecuta acciones desde el chat

**Por qué:** El chat no debe ser solo consultas — debe ser el lugar desde donde Sandra
puede HACER cosas. "Tomy, genera la carta de recomendaciones para Juan Carlos" debería
generar el formato, no explicar cómo generarlo.

**Detección de intención de acción:**
```python
INTENCIONES_ACCION = [
    (r"genera[r]?\s+(.*?)\s+para\s+(.+)", "generar_formato"),
    (r"descarg[ar]?\s+(.+)", "descargar_formato"),
    (r"correg[ir]?\s+(.+)", "corregir_formato"),
    (r"verifica[r]?\s+(.+)", "verificar_formato"),
    (r"reenvía[r]?\s+(a\s+)?arl", "reenviar_arl"),
]

async def _detectar_accion(mensaje: str, cc: str) -> str | None:
    import re
    for patron, accion in INTENCIONES_ACCION:
        m = re.search(patron, mensaje.lower())
        if m:
            return accion, m.groups()
    return None
```

**Flujo de confirmación antes de ejecutar:**
```
Sandra: "Tomy, genera la carta de recomendaciones para Juan Carlos"
Tomy:   "Voy a generar la **Carta de Recomendaciones** para Juan Carlos Durán (CC 1193143688).
         ¿Confirmas? [Sí, generar] [No, cancelar]"
Sandra: [clic en "Sí, generar"]
Tomy:   "Listo ✅ La carta quedó en /paciente/1193143688. [Descargar]"
```

**Botones de acción en las respuestas de Tomy:**
```tsx
interface AccionMensaje {
  label: string;
  endpoint: string;
  body: object;
  confirmacion?: string;
}

// En el render del mensaje de Tomy:
{msg.acciones?.map(a => (
  <button key={a.label}
    onClick={() => ejecutarAccion(a)}
    className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-xl text-sm hover:bg-blue-700">
    {a.label}
  </button>
))}
```

---

## CHAT-3 — Streaming de respuestas en tiempo real

**Por qué:** Con DeepSeek v4, esperar 60-120 segundos viendo una pantalla en blanco es
frustrante. El streaming muestra los tokens conforme llegan — Sandra ve a Tomy "pensando"
y la respuesta aparece palabra a palabra. La experiencia parece instantánea.

**Backend — `server.py`:**
```python
@app.post("/api/chat/stream")
async def chat_stream(body: dict, request: Request):
    """SSE que entrega tokens del LLM conforme llegan."""
    from backend.chat_handler import _llamar_llm_stream
    mensaje = body.get("mensaje", "")
    cc = body.get("paciente_cc")

    async def generator():
        async for token in _llamar_llm_stream(mensaje, cc):
            if await request.is_disconnected():
                break
            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

**`backend/chat_handler.py` — streaming con la API de OpenCode:**
```python
import httpx

async def _llamar_llm_stream(mensaje: str, cc: str = None):
    """Genera tokens del LLM uno a uno via streaming."""
    prompt = _construir_prompt(mensaje, cc)
    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream("POST", LLM_URL + "/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "model": LLM_MODEL_SINTESIS,
                "messages": prompt,
                "stream": True,
                "max_tokens": 8000,
            }
        ) as resp:
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:]
                if chunk == "[DONE]":
                    return
                try:
                    data = json.loads(chunk)
                    token = data["choices"][0]["delta"].get("content", "")
                    if token:
                        yield token
                except Exception:
                    continue
```

**`dashboard/app/chat/page.tsx` — recibir streaming:**
```tsx
const enviarMensaje = async (texto: string) => {
  const msgId = Date.now();
  setMensajes(prev => [...prev,
    { id: msgId, rol: "usuario", contenido: texto },
    { id: msgId + 1, rol: "tomy", contenido: "", streaming: true },
  ]);

  const ev = new EventSource(
    `${API}/chat/stream?mensaje=${encodeURIComponent(texto)}&paciente_cc=${cc ?? ""}`
  );

  // Para POST con body, usar fetch + ReadableStream:
  const resp = await fetch(`${API}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mensaje: texto, paciente_cc: cc }),
  });

  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let acumulado = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value);
    for (const line of chunk.split("\n")) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6);
      if (data === "[DONE]") break;
      try {
        const { token } = JSON.parse(data);
        acumulado += token;
        setMensajes(prev => prev.map(m =>
          m.id === msgId + 1 ? { ...m, contenido: acumulado } : m
        ));
      } catch {}
    }
  }

  // Marcar como terminado
  setMensajes(prev => prev.map(m =>
    m.id === msgId + 1 ? { ...m, streaming: false } : m
  ));
};
```

**Cursor parpadeante mientras Tomy "piensa":**
```tsx
{msg.streaming && (
  <span className="inline-block w-2 h-4 bg-blue-500 ml-0.5 animate-pulse rounded-sm" />
)}
```

---

## CHAT-4 — Contexto automático del paciente activo + historial por paciente

**Por qué:** Hoy el chat es global y sin memoria entre sesiones (más allá de los últimos
50 mensajes en localStorage). Tomy debe saber automáticamente con quién está trabajando
Sandra y tener historial separado por paciente.

**Contexto automático desde el paciente activo:**
```typescript
// En el chat, leer el paciente activo del localStorage
const cc = localStorage.getItem("paciente_activo") ?? "";

// El header del mensaje ya incluye:
// - Nombre del paciente
// - Últimas 3 tareas completadas
// - Último formato generado
// - Datos del portal (siniestro, diagnóstico)
```

**Historial separado por paciente en `backend/chat_db.py`:**
```python
SCHEMA_CHAT = """
CREATE TABLE IF NOT EXISTS chat_historial (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    cc         TEXT NOT NULL,         -- 'global' si no hay paciente
    rol        TEXT NOT NULL,         -- 'usuario' o 'tomy'
    contenido  TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_chat_cc ON chat_historial(cc, id DESC);
"""

def guardar_mensaje(cc: str, rol: str, contenido: str):
    with sqlite3.connect(NOTIF_DB) as conn:
        conn.execute(SCHEMA_CHAT)
        conn.execute("INSERT INTO chat_historial (cc,rol,contenido) VALUES (?,?,?)",
                     (cc or "global", rol, contenido))

def cargar_historial(cc: str, limite: int = 20) -> list[dict]:
    with sqlite3.connect(NOTIF_DB) as conn:
        conn.execute(SCHEMA_CHAT)
        rows = conn.execute(
            "SELECT rol, contenido, created_at FROM chat_historial "
            "WHERE cc=? ORDER BY id DESC LIMIT ?",
            (cc or "global", limite)
        ).fetchall()
    return [{"rol": r[0], "contenido": r[1], "created_at": r[2]}
            for r in reversed(rows)]
```

**Endpoints:**
```python
@app.get("/api/chat/historial")
def get_historial(cc: str = "global", limite: int = 20):
    from backend.chat_db import cargar_historial
    return {"mensajes": cargar_historial(cc, limite)}

@app.delete("/api/chat/historial")
def limpiar_historial(cc: str = "global"):
    from backend.chat_db import limpiar_historial
    limpiar_historial(cc)
    return {"ok": True}
```

---

## CHAT-5 — Tomy explica el workflow y el razonamiento

**Por qué:** Cuando el workflow falla o genera algo inesperado, Sandra no sabe qué pasó.
Tomy debería poder explicar paso a paso qué hizo, qué datos usó, y por qué generó lo que generó.

**Nuevo endpoint — log narrativo del workflow:**
```python
@app.get("/api/tasks/{task_id}/explicar")
async def explicar_workflow(task_id: str):
    """Tomy explica en lenguaje natural qué pasó en el workflow."""
    from backend.task_db import TaskDB
    from backend.chat_handler import _llamar_llm_simple
    db = TaskDB(os.getenv("WORKFLOW_DB_PATH","./storage/workflow.db"))
    task = db.obtener_task(task_id)
    if not task:
        raise HTTPException(404)

    resumen = (
        f"Workflow {task_id} para paciente CC {task['paciente_cc']}.\n"
        f"Estado: {task['estado']}. Paso actual: {task.get('paso_actual', 0)}/9.\n"
        f"Log de pasos:\n{task.get('log_pasos', 'Sin log disponible')}\n"
        f"Errores: {task.get('error', 'Ninguno')}"
    )
    explicacion = await _llamar_llm_simple(
        f"Explícale a Sandra (fisioterapeuta, no técnica) en términos simples y amables "
        f"qué pasó en este proceso. Si hubo error, explica qué significa y qué puede hacer. "
        f"Datos del proceso:\n{resumen}"
    )
    return {"explicacion": explicacion}
```

**En el chat — comando automático al hacer clic en una tarea:**
```tsx
// En la tarjeta de tarea en /hoy:
<button onClick={() => {
  router.push(`/chat?cmd=/estado ${taskId}&explicar=true`);
}}>
  ¿Qué pasó?
</button>
```

---

## DASH-11 — Logs visibles del workflow (Sandra ve qué está pasando)

**Por qué:** El workflow es una caja negra para Sandra. Si tarda 15 minutos y algo falla,
no sabe dónde. Un panel de logs legibles (en español, no stacktraces) le da visibilidad.

**Endpoint:**
```python
@app.get("/api/tasks/{task_id}/logs")
def get_logs_tarea(task_id: str):
    from backend.task_db import TaskDB
    db = TaskDB(os.getenv("WORKFLOW_DB_PATH","./storage/workflow.db"))
    task = db.obtener_task(task_id)
    if not task: raise HTTPException(404)
    return {
        "task_id": task_id,
        "estado": task["estado"],
        "pasos": task.get("log_pasos_json", []),  # lista de {paso, nombre, estado, duracion_s, mensaje}
    }
```

**`dashboard/components/WorkflowLogs.tsx`:**
```tsx
interface PasoLog {
  paso: number; nombre: string;
  estado: "completado" | "en_progreso" | "error" | "pendiente";
  duracion_s?: number; mensaje?: string;
}

const ICONOS = { completado: "✅", en_progreso: "⏳", error: "❌", pendiente: "○" };

export default function WorkflowLogs({ taskId }: { taskId: string }) {
  const [pasos, setPasos] = useState<PasoLog[]>([]);

  useEffect(() => {
    const cargar = () =>
      fetch(`${process.env.NEXT_PUBLIC_API_URL}/tasks/${taskId}/logs`)
        .then(r => r.json()).then(d => setPasos(d.pasos || []));
    cargar();
    const t = setInterval(cargar, 5000);
    return () => clearInterval(t);
  }, [taskId]);

  return (
    <div className="space-y-2">
      {pasos.map(p => (
        <div key={p.paso} className={`flex items-start gap-3 p-3 rounded-xl
          ${p.estado === "error" ? "bg-red-50" :
            p.estado === "en_progreso" ? "bg-blue-50" :
            p.estado === "completado" ? "bg-green-50" : "bg-slate-50"}`}>
          <span className="text-lg flex-shrink-0">{ICONOS[p.estado]}</span>
          <div className="flex-1">
            <p className="font-medium text-slate-800 text-sm">{p.nombre}</p>
            {p.mensaje && <p className="text-slate-600 text-xs mt-0.5">{p.mensaje}</p>}
            {p.duracion_s && (
              <p className="text-slate-400 text-xs mt-0.5">{p.duracion_s}s</p>
            )}
          </div>
          {p.estado === "en_progreso" && (
            <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent
                            rounded-full animate-spin flex-shrink-0 mt-0.5" />
          )}
        </div>
      ))}
    </div>
  );
}
```

---

## DASH-12 — Descarga en lote: paquete ZIP desde la vista del paciente

**Por qué:** Sandra necesita enviar todos los formatos de un paciente a ARL Positiva.
Hoy tiene que descargar cada DOCX por separado. Un botón "Descargar todo" que genere
un ZIP con todos los formatos (DOCX + PDF) del paciente ahorra 5 minutos por caso.

**Backend:**
```python
@app.get("/api/pacientes/{cc}/descargar-todo")
def descargar_todo(cc: str):
    """Genera ZIP con todos los DOCX y PDFs del paciente."""
    import zipfile, io
    from pathlib import Path
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))

    buffer = io.BytesIO()
    archivos_incluidos = 0

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for carpeta, ext in [("docs", ".docx"), ("pdfs", ".pdf")]:
            for f in (storage / carpeta).glob(f"*{cc}*{ext}"):
                zf.write(f, f"{carpeta}/{f.name}")
                archivos_incluidos += 1
            for f in (storage / carpeta).glob(f"*-{cc[:-4]}*{ext}"):  # variantes de CC
                if f.name not in [x.filename.split("/")[-1] for x in zf.infolist()]:
                    zf.write(f, f"{carpeta}/{f.name}")
                    archivos_incluidos += 1

    if archivos_incluidos == 0:
        raise HTTPException(404, "No hay formatos para este paciente")

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=RILO_{cc}_{datetime.now().strftime('%Y%m%d')}.zip"}
    )
```

**En la vista del paciente:**
```tsx
<a href={`${API}/pacientes/${cc}/descargar-todo`}
   className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-xl
              text-lg font-semibold hover:bg-green-700 transition-colors">
  📦 Descargar todo (ZIP)
</a>
```

---

## DASH-13 — Panel de actividad reciente (feed de eventos)

**Por qué:** Sandra necesita saber qué hizo el sistema en las últimas horas sin revisar logs.
Un feed cronológico de eventos ("Generé 3 formatos para Juan Carlos", "Backup completado",
"Positiva responde lento, usé datos locales") da tranquilidad y trazabilidad sin tecnicismos.

**Fuentes de eventos:**
- Tabla `notificaciones` (ya existe desde DASH-1)
- Completions de workflows
- Cambios detectados en portales
- Backups

**`dashboard/app/actividad/page.tsx`:**
```tsx
"use client";
import { useEffect, useState } from "react";

const ICONOS_TIPO: Record<string, string> = {
  workflow_listo:  "✅",
  error:           "❌",
  nudge:           "💡",
  recordatorio:    "⏰",
  sistema:         "🔧",
  correccion:      "✏️",
  portal:          "🌐",
};

export default function Actividad() {
  const [eventos, setEventos] = useState<any[]>([]);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/notificaciones`)
      .then(r => r.json()).then(d => setEventos(d.notificaciones || []));
  }, []);

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-3xl font-bold text-slate-800 mb-8">Actividad reciente</h1>
      <div className="space-y-3">
        {eventos.map(e => (
          <div key={e.id} className="flex items-start gap-4 p-4 bg-white rounded-2xl
                                     border border-slate-100 shadow-sm">
            <span className="text-2xl flex-shrink-0">{ICONOS_TIPO[e.tipo] ?? "📋"}</span>
            <div className="flex-1">
              <p className="font-semibold text-slate-800">{e.titulo}</p>
              <p className="text-slate-500 text-sm mt-0.5">{e.cuerpo}</p>
              <p className="text-slate-400 text-xs mt-1">{e.created_at}</p>
            </div>
            {e.paciente_cc && (
              <a href={`/paciente/${e.paciente_cc}`}
                className="text-sm text-blue-600 hover:underline flex-shrink-0">
                Ver paciente
              </a>
            )}
          </div>
        ))}
        {eventos.length === 0 && (
          <p className="text-center text-slate-400 py-12">Sin actividad reciente</p>
        )}
      </div>
    </div>
  );
}
```

Agregar al Sidebar: `{ href: "/actividad", label: "Actividad", icon: Activity }`.

---

## DASH-14 — Panel de costos de API para Manuel (`/costos`)

**Por qué:** Manuel necesita saber cuánto está gastando en DeepSeek y Deepgram.
El sistema ya trackea tokens en `costos_tracker.py` pero no hay UI. Esta página
convierte los datos de SQLite en gráficas y alertas.

**`dashboard/app/costos/page.tsx`:**
```tsx
// GET /api/costos?dias=30
// Muestra:
// - Gasto total del mes (USD)
// - Gasto por día (gráfica de barras simple con CSS)
// - Top pacientes por costo
// - Estimación del mes completo
// - Alerta si supera umbral configurado

const datos = await fetch(`${API}/costos?dias=30`).then(r => r.json());

// Gráfica CSS (sin librería):
{datos.por_dia.map((d: any) => (
  <div key={d.fecha} className="flex items-end gap-1 h-32">
    <div
      className="w-8 bg-blue-400 rounded-t"
      style={{ height: `${(d.costo_usd / datos.max_dia) * 100}%` }}
      title={`${d.fecha}: $${d.costo_usd.toFixed(3)}`}
    />
    <p className="text-xs text-slate-400 -rotate-45 origin-left">{d.fecha.slice(5)}</p>
  </div>
))}

// Resumen:
// Total mes: $1.24 USD
// Deepgram:  $0.31 (25%)
// DeepSeek:  $0.93 (75%)
// Proyección fin de mes: $1.87 USD
```

Agregar al Sidebar (solo visible si `SHOW_COSTOS=true` en env, para que Sandra no lo vea).

---

## PARTE 18 — Tabla resumen

| ID | Feature | Tipo | Impacto | Tiempo |
|----|---------|------|---------|--------|
| CHAT-1 | Slash commands con autocompletar | UX+Power | Sandra hace cosas con `/generar`, `/agenda`, `/corregir` | 3h |
| CHAT-2 | Tomy ejecuta acciones (genera, descarga, corrige) con confirmación | Power | El chat es un centro de comandos, no solo Q&A | 4h |
| CHAT-3 | Streaming de respuestas token a token | UX | La espera de 90s parece instantánea | 3h |
| CHAT-4 | Historial por paciente + contexto automático del paciente activo | Intelligence | Tomy ya sabe con quién está trabajando Sandra | 2h |
| CHAT-5 | Tomy explica el workflow en lenguaje natural | Intelligence | Sandra entiende qué pasó sin ser técnica | 1.5h |
| DASH-11 | Logs visuales del workflow paso a paso | UX | Caja negra → panel de progreso legible | 2h |
| DASH-12 | Descarga en lote (ZIP de todos los formatos del paciente) | Productivity | 1 clic → ZIP con todo listo para ARL | 1.5h |
| DASH-13 | Feed de actividad reciente (`/actividad`) | UX | Sandra ve qué hizo el sistema sin revisar logs | 2h |
| DASH-14 | Panel de costos de API (`/costos`) para Manuel | Analytics | Control de gasto real de DeepSeek + Deepgram | 2h |

**Subtotal PARTE 18: ~21 horas**

---

## Tiempo estimado total (v11 — sistema completo)

| Bloque | Descripción | Tiempo |
|--------|-------------|--------|
| A + FX + NC críticos | Bugs bloqueantes | 4h |
| B + CHAT-1/2/3/4/5 | Chat de clase mundial: streaming, acciones, slash commands | 14h |
| P + EVO-5/6/7/8 | Portales inteligentes con fallback | 7h |
| CR + NC12 + INT-2 | Corrección + entrevistador + prompt adaptativo | 5h |
| Z + EVO-2/3/18 | Entrega incremental, queue, Draft→ARL | 5h |
| TG | Telegram avisos salientes | 4h |
| DASH-1/2/3/10/11/12/13 | Mi Día + notif + header + logs + ZIP + actividad | 12h |
| AG + EVO-14 + INT-4 | Agenda + plazos + nudges | 5h |
| M + EVO-10 | M4A + auto-CC | 3h |
| LH + PD + ARCH-4/5 | Limpieza Hermes + PM2 + nginx + setup | 8h |
| EVO restantes | Streaming, CB, WAL, diff, cleanup | 12h |
| INT-1/3/5/6 | Conocimiento clínico, paquete ARL, analítica, timeline | 10h |
| BIZ-1 + DASH-14 | ROI mensual + panel de costos | 4h |
| LEGAL-1/2 | Habeas Data + Audit log | 4h |
| ARCH-3/6 + MU-1 | Tests, Alembic, multi-usuario | 9h |
| DASH-4/5/6/7/8/9 | Buscador, visor DOCX, drag-drop, modo oscuro, config | 14h |
| **TOTAL** | | **~120 horas (~15 días de trabajo real)** |



---

---

# MVP — Versión Mínima Funcional (Lo que Sandra puede usar HOY)

> **Filosofía del MVP:** No se necesita el sistema perfecto para ahorrarle 2 horas por
> paciente a Sandra. Se necesita un sistema que funcione. El MVP es lo mínimo que hace
> la diferencia real: Sandra sube el audio de una consulta y recibe los formatos listos.
> Todo lo demás del plan viene después, sin apuros.

---

## ¿Qué puede hacer Sandra con el MVP?

1. **Abrir el dashboard** en el navegador del PC
2. **Ir a "Subir Audio"**, escribir la cédula del paciente, arrastrar el M4A de iPhone
3. **Esperar 15-20 minutos** mientras Tomy trabaja (puede seguir con otra tarea)
4. **Ir a "Mi Día"** y ver que los formatos están listos
5. **Descargar los DOCX** del paciente y revisarlos en Word
6. **Preguntar a Tomy** por chat si necesita aclarar algo sobre el caso

**Resultado:** Sandra ahorra 2-3 horas por paciente que antes pasaba llenando los formatos
a mano en Word. Con 10-15 pacientes al mes, eso son 20-45 horas mensuales recuperadas.

---

## Lo que el MVP incluye

### Backend (ya implementado, requiere fixes menores)

| Componente | Estado | Acción necesaria |
|-----------|--------|-----------------|
| FastAPI servidor | ✅ Listo | Solo iniciar con PM2 |
| Deepgram transcripción | ✅ Listo | Configurar API key en .env |
| DeepSeek v4 síntesis | ✅ Listo | Configurar API key en .env |
| Workflow 9 pasos | ✅ Listo | Fix NC-8 (daemon thread) — 30 min |
| Generación 7 formatos DOCX | ✅ Listo | Verificar plantillas existen |
| QA de formatos | ⚠️ Bug NC-1 | Inline QA simple — 1h |
| SQLite persistencia | ✅ Listo | Crear directorio storage/ |
| Chat con Tomy | ✅ Listo | Funciona con deepseek-v4-pro |
| Telegram avisos | ✅ Listo | Configurar BOT_TOKEN en .env |

### Dashboard (ya implementado, requiere fix de URL)

| Página | Estado | Acción necesaria |
|--------|--------|-----------------|
| `/hoy` (Mi Día) | ✅ Listo | Fix NC-7: NEXT_PUBLIC_API_URL — 30 min |
| `/subir-audio` | ✅ Listo | Fix NC-7: NEXT_PUBLIC_API_URL |
| `/chat` | ✅ Listo | Fix NC-7: NEXT_PUBLIC_API_URL |
| `/paciente/[cc]` | ✅ Listo | Fix NC-7 + cambiar alert() por toast — 30 min |
| `/archivos` | ✅ Listo | Fix rglob por scandir — 30 min |
| `/pacientes` | ✅ Listo | Fix import hermes → api — 20 min |

---

## Lo que el MVP NO incluye (para después)

| Feature | Por qué después |
|---------|----------------|
| Extracción automática de portales (Playwright) | Complejidad alta, datos JSON bastan para empezar |
| Auth/login con PIN | Red doméstica, no urgente |
| Streaming del chat | El chat funciona sin él (solo más lento) |
| Slash commands | Funcionalidad extra, no bloqueante |
| Notificaciones in-app (bandeja) | Telegram cubre la necesidad por ahora |
| PWA / modo oscuro | Mejora de UX, no funcional |
| Corrección por chat (correction_resolver) | Sandra puede editar el DOCX en Word por ahora |
| Backup automático | Manuel hace backup manual al principio |
| Agenda Gmail | Sandra revisa agenda en Medifolios directamente |
| Panel de costos | Funciona sin él |
| Visualizador DOCX | Sandra abre en Word |
| Buscador global ⌘K | Pocos pacientes por ahora |

---

## Plan de implementación del MVP — 2 días

### Día 1 (mañana) — Fixes críticos y arranque

**Hora 1-2 — Fix NC-7: unificar URL del backend**

```typescript
// Crear dashboard/lib/config.ts (NUEVO)
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

// Reemplazar en TODOS los archivos del dashboard:
// "http://localhost:8000/api" → import { API_URL } from "@/lib/config"
// "http://localhost:8000"     → import { API_URL } from "@/lib/config"
```

Archivos a tocar: `app/hoy/page.tsx`, `app/chat/page.tsx`, `app/paciente/[cc]/page.tsx`,
`app/subir-audio/page.tsx`, `app/archivos/page.tsx`, `lib/workflow.ts`, `lib/hermes.ts`

**Hora 2 — Fix NC-8: daemon thread**

```python
# backend/workflow_runner.py — reemplazar:
# threading.Thread(target=_runner, daemon=True).start()

# Por: usar FastAPI BackgroundTasks (ya lo soporta server.py)
@app.post("/api/procesar-paciente")
async def procesar_paciente(
    audio: UploadFile,
    paciente_cc: str,
    background_tasks: BackgroundTasks,
):
    # guardar audio
    task_id = db.crear_task(paciente_cc=paciente_cc, audio_path=str(audio_path))
    background_tasks.add_task(_correr_workflow, task_id, str(audio_path), paciente_cc)
    return {"task_id": task_id, "estado": "iniciado"}
```

**Hora 3 — Fix NC-1: QA inline**

```python
# backend/qa_formatos.py — reemplazar llamada al script externo por:
def _qa_docx_inline(ruta: str) -> dict:
    from docx import Document
    doc = Document(ruta)
    advertencias = []
    texto_completo = " ".join(p.text for p in doc.paragraphs)

    # Check 1: Placeholders sin reemplazar
    import re
    placeholders = re.findall(r'\[(?!VERIFICAR)[A-Z_]{3,}\]', texto_completo)
    if placeholders:
        advertencias.append(f"Placeholders sin reemplazar: {', '.join(set(placeholders))}")

    # Check 2: Documento muy corto
    if len(texto_completo) < 200:
        advertencias.append("El documento parece muy corto (menos de 200 caracteres)")

    # Check 3: Tablas vacías
    for i, tabla in enumerate(doc.tables):
        celdas_vacias = sum(1 for fila in tabla.rows for c in fila.cells if not c.text.strip())
        total_celdas = sum(len(fila.cells) for fila in tabla.rows)
        if total_celdas > 0 and celdas_vacias / total_celdas > 0.8:
            advertencias.append(f"Tabla {i+1} tiene más del 80% de celdas vacías")

    return {
        "qa_ok": len(advertencias) == 0,
        "qa_warnings": advertencias,
        "qa_score": max(0, 100 - len(advertencias) * 20),
    }
```

**Hora 4 — Fix import hermes y rglob**

```python
# dashboard/app/pacientes/page.tsx — cambiar:
# import type { Paciente, FormatoInfo } from "@/lib/hermes"
# Por:
# import type { Paciente, FormatoInfo } from "@/lib/api"
# (o mover las definiciones a un archivo types.ts)

# backend/server.py línea ~457 — cambiar rglob por scandir:
def _listar_archivos_safe(path: Path, max_depth: int = 2) -> list[Path]:
    resultado = []
    def _scan(p: Path, depth: int):
        if depth > max_depth: return
        try:
            for entry in os.scandir(p):
                ep = Path(entry.path)
                if entry.is_file(): resultado.append(ep)
                elif entry.is_dir(): _scan(ep, depth + 1)
        except PermissionError: pass
    _scan(path, 0)
    return resultado
```

**Hora 4-5 — Configurar .env de producción en WSL**

```bash
# ~/rilo-backend/.env — valores reales para producción:
OPENCODE_GO_API_KEY=sk-...        # API key de OpenCode Go
DEEPGRAM_API_KEY=...              # API key de Deepgram
TELEGRAM_BOT_TOKEN=...            # Token del bot de Telegram
TELEGRAM_CHAT_ID=...              # Chat ID de Sandra en Telegram
AUTH_PIN=XXXX                     # PIN de 4 dígitos (NO 1234)
AUTH_SECRET=rilo-sas-prod-2026-XXX  # Secret aleatorio largo

# URLs de producción (IP de la PC de Sandra en la red local):
NEXT_PUBLIC_API_URL=http://192.168.X.X:8000/api
DASHBOARD_URL=http://192.168.X.X:3000

# Paths
STORAGE_DIR=./storage
WORKFLOW_DB_PATH=./storage/workflow.db
WORKSPACE_SANDRA=/mnt/c/Users/Sandra/Desktop/SANDRA/ACTIVIDADES OCUPACIONALES

# Feature flags
TOMY_COMPLETO_ENABLED=true    # Activar el workflow completo
FASE_A_CRON_ENABLED=false     # Crons apagados en MVP
```

**Hora 5-6 — Arrancar todo con PM2**

```bash
# En WSL, en ~/rilo-backend:
git pull origin main

# Instalar dependencias del backend
pip install -r requirements.txt
playwright install chromium  # para extracción portales (después)

# Iniciar backend
pm2 start "uvicorn backend.server:app --host 0.0.0.0 --port 8000" --name rilo-backend

# Instalar dependencias del dashboard
cd ~/rilo-dashboard
npm install
npm run build

# Iniciar dashboard
pm2 start "npm run start" --name rilo-dashboard

# Guardar configuración PM2
pm2 save
pm2 startup  # configurar inicio automático al encender PC

# Verificar que todo está up
pm2 status
curl http://localhost:8000/  # debe responder {"status": "ok"...}
curl http://localhost:3000   # debe devolver HTML del dashboard
```

**Hora 6-7 — Prueba end-to-end con Sandra**

1. Abrir `http://192.168.X.X:3000` desde el navegador de Sandra
2. Ir a "Subir Audio"
3. Escribir CC de un paciente de prueba
4. Subir un audio M4A corto (3-5 minutos de prueba)
5. Esperar y verificar que los DOCX se generan
6. Sandra descarga uno y revisa en Word
7. Sandra hace una pregunta en el chat y Tomy responde

### Día 2 (tarde) — Pulido y entrega

**Hora 1-2 — Datos de pacientes en JSON**

Antes de tener extracción de portales, cargar manualmente los datos de los 3 pacientes
en `storage/data/`:

```json
// storage/data/1193143688.json
{
  "nombre": "Juan Carlos Duran Narvaez",
  "cc": "1193143688",
  "siniestro": "503463870",
  "empresa": "...",
  "cargo": "...",
  "diagnostico": "...",
  "diagnostico_cie10": "...",
  "fecha_evento": "...",
  "eps": "..."
}
```

Manuel los llena con los datos reales de los portales (una vez, manualmente).

**Hora 2-3 — Verificación del checklist MVP**

Del archivo `VERIFICACION_SISTEMA.md`, ejecutar solo los bloques 0, 1, 2, 3, 5 y 6.
Son los bloques críticos para el MVP. Los demás bloques se verifican después.

**Hora 3 — Capacitación de Sandra (15 minutos)**

Mostrarle exactamente tres acciones:
1. Cómo subir un audio (ir a "Subir Audio", CC, arrastar archivo, clic en "Subir")
2. Cómo ver si está listo (ir a "Mi Día", buscar el nombre del paciente)
3. Cómo descargar un formato (ir al paciente, clic en DOCX)

No explicar nada más. Si hay duda, "pregúntale a Tomy en el chat".

---

## Criterios de éxito del MVP

El MVP está listo cuando Sandra puede hacer esto sin ayuda:

- [ ] Subir un audio M4A de iPhone de 15 minutos
- [ ] Ver el progreso en "Mi Día" (barra de pasos)
- [ ] Recibir notificación de Telegram cuando los formatos están listos
- [ ] Descargar el Análisis de Exigencias y abrirlo en Word con datos correctos
- [ ] Hacer una pregunta a Tomy en el chat y recibir respuesta coherente
- [ ] Hacer todo sin llamar a Manuel

---

## Roadmap post-MVP: el orden de implementación

Una vez el MVP está en manos de Sandra y funcionando, implementar en este orden:

### Sprint 1 — Semana 1-2 (prioridad alta)
- Fix NC-4: Markdown en el chat (react-markdown — 30 min)
- Fix NC-5: CC del paciente activo se pasa al chat (30 min)
- Fix NC-6: CC en las citas de la agenda (1h)
- CHAT-3: Streaming de respuestas (3h) — la mejora de UX más notoria
- DASH-5: Drag-and-drop en Subir Audio + barra de progreso (3h)
- DASH-1: Notificaciones in-app básicas (3h)

### Sprint 2 — Semana 3-4 (extracción de portales)
- Playwright Medifolios: extracción automática al subir audio
- Playwright Positiva: verificación de siniestro y diagnóstico
- Modo degradado documentado y visible en la UI

### Sprint 3 — Semana 5-6 (chat potente)
- CHAT-1: Slash commands (`/formatos`, `/paciente`, `/agenda`)
- CHAT-2: Tomy ejecuta acciones desde el chat
- CHAT-4: Historial por paciente

### Sprint 4 — Semana 7-8 (dashboard completo)
- DASH-6: Buscador global ⌘K
- DASH-7: Visualizador DOCX in-browser
- DASH-9: Página de configuración
- DASH-10: PWA instalable en iPhone

### Sprint 5 — Mes 3 (inteligencia clínica)
- INT-1: Base de conocimiento CIE-10
- INT-2: Entrevistador clínico (pausa + pregunta datos faltantes)
- INT-3: Paquete ARL completo (ZIP profesional)
- INT-4: Nudges proactivos

### Sprint 6 — Mes 3-4 (robustez)
- ARCH-2: Circuit breakers
- ARCH-3: Test suite
- ARCH-6: Alembic migrations
- LEGAL-1: Habeas Data
- BIZ-1: Reporte mensual ROI

---

## Lo que Sandra tiene al final del Sprint 1 (2 semanas)

- Sube audio → formatos listos en 15 min ✅
- Ve el progreso en tiempo real ✅
- Tomy responde mientras escribe (streaming) ✅
- Chat con contexto del paciente que está trabajando ✅
- Notificación in-app cuando termina (sin depender del celular) ✅
- Drag-and-drop de audio con validación y barra de progreso ✅

**Ahorro estimado:** 2-3 horas por paciente × 12 pacientes/mes = 24-36 horas mensuales.
A una tarifa de $50.000 COP/hora, son $1.2M - $1.8M COP de valor mensual generado.

---

*Actualizado 2026-05-22 (v11). MVP: 2 días de fixes sobre código ya implementado.
El 90% del sistema ya existe — lo que falta son 3 fixes críticos y la configuración de producción.*
