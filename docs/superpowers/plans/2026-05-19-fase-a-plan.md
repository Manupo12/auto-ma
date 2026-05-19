# Fase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estabilizar el pipeline IA de RILO SAS (resolver OOM por reasoning_content de DeepSeek v4) e implementar la verificación real contra Medifolios + ARL Positiva con Playwright, dejando la pre-extracción nocturna automática conectada al chat de Tomy.

**Architecture:** Subprocess por lote para aislar memoria; Playwright headless en mismo proceso FastAPI (WSL); APScheduler dentro de FastAPI para cron nocturno; feature flag para rollback. Mantener DeepSeek v4 (cuota OpenCode Go) pero usar `deepseek-chat` sólo para extracción literal y `deepseek-v4-pro` con razonamiento completo para síntesis.

**Tech Stack:** Python 3 + FastAPI + uvicorn + Playwright + APScheduler + python-docx + requests + DeepSeek v4 vía OpenCode Go.

**Spec:** `docs/superpowers/specs/2026-05-19-fase-a-pipeline-portales-design.md`

---

## File Structure

```
backend/
├── lote_worker.py                 [NEW]     ~150 líneas. Subprocess CLI: lee docs, llama LLM, imprime JSON, muere.
├── cron_pre_extraccion.py         [NEW]     ~150 líneas. APScheduler jobs: 21:00 extracción + 06:30 recordatorio.
├── playwright_real/               [NEW]
│   ├── __init__.py                          Exports públicos.
│   ├── session.py                 [NEW]     ~180 líneas. Login + storage_state + re-auth.
│   ├── selectores.py              [NEW]     ~80 líneas. Constantes CSS/XPath/JS de skills/flujo-browser/.
│   ├── medifolios.py              [NEW]     ~220 líneas. 4 funciones extracción.
│   ├── positiva.py                [NEW]     ~250 líneas. 4 funciones extracción (6 pestañas).
│   └── orquestador.py             [NEW]     ~120 líneas. Une fuentes, detecta discrepancias.
├── chat_handler.py                [MOD]     ~200 líneas modificadas. Subprocess + datos verificados.
├── server.py                      [MOD]     6 endpoints nuevos/modificados.
├── notificador.py                 [MOD]     ~50 líneas. Mensajes Telegram para cron.
├── fusionador.py                  [MOD]     ~30 líneas. Integrar `_meta.discrepancias`.
├── puente_docker.py               [DELETE]  Reemplazado por flow nativo.
├── extractor_medifolios.py        [MARK]    Banner DEPRECATED al inicio.
├── extractor_positiva.py          [MARK]    Banner DEPRECATED al inicio.
├── browser_session.py             [MARK]    Banner DEPRECATED al inicio.
├── requirements.txt               [MOD]     +playwright, +apscheduler, +pytz, +aiofiles, +pytest, +pytest-asyncio.
└── .env.example                   [NEW]     Plantilla con variables nuevas.

tests/                             [NEW dir]
├── __init__.py
├── conftest.py                    [NEW]     Fixtures comunes (tmp storage, mock LLM, etc).
├── test_lote_worker.py            [NEW]
├── test_playwright_session.py     [NEW]
├── test_extractor_medi.py         [NEW]     Live tests contra Medifolios (CC 55162801).
├── test_extractor_pos.py          [NEW]     Live tests contra Positiva (CC 1193143688).
├── test_orquestador_playwright.py [NEW]
├── test_cron.py                   [NEW]
├── test_chat_integration.py       [NEW]
└── test_e2e.py                    [NEW]     Tests end-to-end.

storage/
├── playwright_sessions/           [NEW dir, .gitignore'd] Cookies + localStorage.
└── screenshots/                   [NEW dir, .gitignore'd] Evidencia cuando selector falla.

.env                               [MOD]     +FASE_A_ENABLED, +PLAYWRIGHT_*, +CRON_*, +LLM_MODEL_*.
.gitignore                         [MOD]     +storage/playwright_sessions/, +storage/screenshots/.
```

---

## Conventions

- **Python style:** PEP 8, type hints donde aporta, docstrings cortos en español para funciones públicas.
- **Tests:** `pytest` + `pytest-asyncio`. Tests live contra portales marcados con `@pytest.mark.live` (skippeables en CI).
- **Commits:** uno por task completada. Mensajes con emoji + área + verbo: `🔧 lote_worker: aislamiento subprocess para OOM`.
- **Feature flag:** todo el código nuevo se activa con `FASE_A_ENABLED=true` en `.env`. Por defecto `false` durante desarrollo.
- **Logs:** usar `_log()` style de `chat_handler.py` (stderr con timestamp). No `print`.

---

## Task 1: Estructura base, dependencias y feature flag

**Files:**
- Modify: `backend/requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `backend/playwright_real/__init__.py`
- Modify: `.env`
- Create: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Actualizar `requirements.txt`**

Agregar al final del archivo:

```text
playwright>=1.42.0
apscheduler>=3.10.4
pytz>=2024.1
aiofiles>=23.2.1
pytest>=8.0.0
pytest-asyncio>=0.23.0
psutil>=5.9.0
```

- [ ] **Step 2: Instalar dependencias y Playwright Chromium**

Run:
```bash
cd /home/manu/Documentos/Temporal/auto-ma
pip install -r backend/requirements.txt
playwright install chromium
```

Expected: instalación OK, chromium descargado.

- [ ] **Step 3: Crear `.env.example` (plantilla sin secretos)**

```bash
cat > .env.example <<'EOF'
# ============================================================
# RILO SAS — Plantilla de variables de entorno
# Copia este archivo a .env y rellena con tus valores
# ============================================================

# --- Medifolios ---
MEDIFOLIOS_URL=https://www.server0medifolios.net/
MEDIFOLIOS_USER=
MEDIFOLIOS_PASSWORD=

# --- ARL Positiva ---
POSITIVA_URL=https://positivacuida.positiva.gov.co/cas/login
POSITIVA_USER=
POSITIVA_PASSWORD=

# --- Deepgram ---
DEEPGRAM_API_KEY=

# --- Telegram ---
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# --- Gmail ---
GMAIL_USER=
GMAIL_APP_PASSWORD=

# --- Directorios ---
STORAGE_DIR=./storage
TEMPLATES_DIR=./templates/formatos
WORKSPACE_DIR=

# --- LLM ---
OPENCODE_GO_API_KEY=
OPENCODE_GO_BASE_URL=https://opencode.ai/zen/go/v1
LLM_MODEL_EXTRACCION=deepseek-chat
LLM_MODEL_SINTESIS=deepseek-v4-pro

# --- Fase A: pipeline IA + portales ---
FASE_A_ENABLED=false
FASE_A_CRON_ENABLED=false

# --- Playwright ---
PLAYWRIGHT_DEBUG=false
PLAYWRIGHT_TIMEOUT_MS=30000
PLAYWRIGHT_SESSIONS_DIR=./storage/playwright_sessions

# --- Cron ---
CRON_HORA_NOCHE=21
CRON_COOLDOWN_PACIENTES_S=30
EOF
```

- [ ] **Step 4: Agregar variables nuevas a `.env`**

Editar `.env` y agregar las siguientes líneas al final (mantener las existentes):

```bash
# --- Fase A: pipeline IA + portales ---
FASE_A_ENABLED=false
FASE_A_CRON_ENABLED=false

# --- LLM modelos ---
LLM_MODEL_EXTRACCION=deepseek-chat
LLM_MODEL_SINTESIS=deepseek-v4-pro

# --- Playwright ---
PLAYWRIGHT_DEBUG=false
PLAYWRIGHT_TIMEOUT_MS=30000
PLAYWRIGHT_SESSIONS_DIR=./storage/playwright_sessions

# --- Cron ---
CRON_HORA_NOCHE=21
CRON_COOLDOWN_PACIENTES_S=30
```

- [ ] **Step 5: Actualizar `.gitignore`**

Agregar al final:

```text
# Fase A — sesiones browser y evidencia
storage/playwright_sessions/
storage/screenshots/
__pycache__/
.pytest_cache/
*.pyc
```

- [ ] **Step 6: Crear `tests/__init__.py` y `tests/conftest.py`**

`tests/__init__.py` (vacío):
```bash
touch tests/__init__.py
```

`tests/conftest.py`:

```python
"""Fixtures comunes para tests de Fase A."""
import os
import sys
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import pytest

# Asegurar que backend sea importable
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@pytest.fixture
def tmp_storage(tmp_path):
    """Crea un storage/ temporal para tests."""
    storage = tmp_path / "storage"
    for sub in ["docs", "data", "audio", "playwright_sessions", "screenshots"]:
        (storage / sub).mkdir(parents=True, exist_ok=True)
    return storage


@pytest.fixture
def mock_llm_response():
    """Mock para requests.post a OpenCode Go."""
    def _mock(content="Datos extraídos correctamente", reasoning="", tokens=500):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{
                "message": {"content": content, "reasoning_content": reasoning},
                "finish_reason": "stop",
            }],
            "usage": {"total_tokens": tokens},
        }
        return resp
    return _mock


@pytest.fixture
def datos_paciente_juan():
    """JSON de paciente de prueba (Juan Carlos)."""
    return {
        "paciente": {
            "documento": "1193143688",
            "nombre": "JUAN CARLOS DURAN NARVAEZ",
            "edad": "45",
            "telefono": "3001234567",
        },
        "siniestro": {"id_siniestro": "503463870", "fecha_evento": "02/03/2026"},
        "empresa": {"nombre": "ACME S.A.S."},
        "estado_caso": "SEGUIMIENTO",
    }


# Marcadores para tests live (que tocan portales reales)
def pytest_collection_modifyitems(config, items):
    skip_live = pytest.mark.skip(reason="needs --live flag")
    if config.getoption("--live", default=False):
        return
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


def pytest_addoption(parser):
    parser.addoption(
        "--live", action="store_true", default=False,
        help="Ejecutar tests live contra portales reales",
    )
```

- [ ] **Step 7: Crear `backend/playwright_real/__init__.py` (vacío)**

```bash
mkdir -p backend/playwright_real
touch backend/playwright_real/__init__.py
```

- [ ] **Step 8: Sanity check — importar backend sin errores**

Run:
```bash
cd /home/manu/Documentos/Temporal/auto-ma
python -c "from backend import server; print('OK')"
```

Expected: `OK`

- [ ] **Step 9: Commit**

```bash
git add backend/requirements.txt backend/playwright_real/ tests/ .env .env.example .gitignore
git commit -m "🔧 Fase A: dependencias, feature flag, estructura tests"
```

---

## Task 2: `lote_worker.py` — subprocess CLI (TDD)

**Files:**
- Create: `backend/lote_worker.py`
- Create: `tests/test_lote_worker.py`

- [ ] **Step 1: Escribir test que falla — extracción exitosa**

`tests/test_lote_worker.py`:

```python
"""Tests para lote_worker — subprocess que ejecuta 1 llamada LLM y muere."""
import json
import subprocess
import sys
from pathlib import Path
import pytest


def _ejecutar_worker(args: list) -> tuple[int, dict, str]:
    """Helper: ejecuta lote_worker como subprocess y parsea salida."""
    proc = subprocess.run(
        [sys.executable, "-m", "backend.lote_worker"] + args,
        capture_output=True, text=True, timeout=180,
        cwd=Path(__file__).parent.parent,
    )
    try:
        salida = json.loads(proc.stdout) if proc.stdout else {}
    except json.JSONDecodeError:
        salida = {"raw_stdout": proc.stdout}
    return proc.returncode, salida, proc.stderr


def test_lote_worker_sin_archivos_devuelve_error(tmp_path):
    """Llamar sin --archivos debe fallar con exit 1 y mensaje en stderr."""
    code, salida, stderr = _ejecutar_worker(["--tipo", "extraer", "--archivos", "", "--cc", "123"])
    assert code != 0
    assert "archivos" in stderr.lower() or "archivos" in str(salida).lower()
```

- [ ] **Step 2: Ejecutar test — debe fallar (módulo no existe)**

Run:
```bash
cd /home/manu/Documentos/Temporal/auto-ma
pytest tests/test_lote_worker.py::test_lote_worker_sin_archivos_devuelve_error -v
```

Expected: FAIL con `ModuleNotFoundError: No module named 'backend.lote_worker'`.

- [ ] **Step 3: Implementación mínima de `backend/lote_worker.py`**

```python
"""
lote_worker — subprocess CLI que ejecuta 1 llamada LLM y muere.

Diseño: el padre (FastAPI) acumula reasoning_content de DeepSeek v4 y crashea
por OOM. Aislar cada llamada en un subprocess hace que el OS libere la RAM
al terminar el proceso, eliminando el leak.

Uso:
  python -m backend.lote_worker \
      --tipo extraer \
      --archivos a.docx,b.docx \
      --modelo deepseek-chat \
      --cc 1193143688

Salida: JSON por stdout. Exit 0 si OK, exit 1 si error (stacktrace en stderr).
"""
import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import requests


API_KEY = os.getenv("OPENCODE_GO_API_KEY", "")
BASE_URL = os.getenv("OPENCODE_GO_BASE_URL", "https://opencode.ai/zen/go/v1")
MODEL_EXTRACCION = os.getenv("LLM_MODEL_EXTRACCION", "deepseek-chat")
MODEL_SINTESIS = os.getenv("LLM_MODEL_SINTESIS", "deepseek-v4-pro")

PROMPT_EXTRACCION = """Extrae los siguientes campos del documento. Formato EXACTO (una línea por campo):

PACIENTE: <nombre completo>
CC: <número>
SINIESTRO: <id>
FECHA_EVENTO: <dd/mm/aaaa>
DIAGNOSTICO: <código CIE-10 + descripción>
EMPRESA: <nombre>
SEGMENTO: <parte del cuerpo>
CAMPOS_VACIOS: <lista separada por comas>
OBSERVACIONES: <notas relevantes>

Si un campo no aparece, escribe FALTA."""


def _log(msg: str):
    print(f"[LOTE_WORKER {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _leer_docx(ruta: Path) -> str:
    """Lee .docx (primeras 60 párrafos + 5 tablas) o .txt."""
    if not ruta.exists():
        return ""
    if ruta.suffix.lower() == ".txt":
        return ruta.read_text(encoding="utf-8", errors="ignore")[:6000]
    if ruta.suffix.lower() != ".docx":
        return ""
    from docx import Document
    doc = Document(str(ruta))
    lines = [f"📄 {ruta.name}\n"]
    for p in doc.paragraphs[:60]:
        t = p.text.strip()
        if t:
            lines.append(t[:200])
    for ti, tabla in enumerate(doc.tables[:5]):
        lines.append(f"\nTabla {ti+1}:")
        for row in tabla.rows[:5]:
            celdas = [c.text.strip()[:50] for c in row.cells[:6] if c.text.strip()]
            if celdas:
                lines.append(" | ".join(celdas))
    return "\n".join(lines)[:6000]


def _llamar_llm(messages: list, modelo: str, max_tokens: int) -> dict:
    """Llamada HTTP al LLM. Devuelve dict con content, reasoning, tokens, finish."""
    t0 = time.time()
    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        json={
            "model": modelo,
            "messages": messages,
            "temperature": 0.3 if "deepseek-chat" in modelo else 0.7,
            "max_tokens": max_tokens,
        },
        timeout=180,
    )
    elapsed = time.time() - t0
    resp.raise_for_status()
    body = resp.json()
    choice = body.get("choices", [{}])[0]
    msg = choice.get("message", {})
    usage = body.get("usage", {})
    return {
        "content": (msg.get("content") or "").strip(),
        "reasoning": (msg.get("reasoning_content") or "").strip(),
        "finish": choice.get("finish_reason"),
        "tokens": {
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
            "reasoning": usage.get("reasoning_tokens", 0),
            "total": usage.get("total_tokens", 0),
        },
        "tiempo_s": round(elapsed, 2),
    }


def ejecutar_extraccion(archivos: list[Path], cc: str, modelo: str) -> dict:
    """Lee archivos, manda prompt mínimo de extracción, devuelve datos."""
    contenidos = []
    for ruta in archivos:
        c = _leer_docx(ruta)
        if c:
            contenidos.append(c)
    if not contenidos:
        return {"ok": False, "error": "ningún archivo legible"}

    contexto = "\n\n---\n\n".join(contenidos)[:8000]
    messages = [
        {"role": "system", "content": PROMPT_EXTRACCION},
        {"role": "user", "content": f"CC: {cc}\n\n{contexto}"},
    ]
    resultado = _llamar_llm(messages, modelo, max_tokens=4000)
    return {
        "ok": True,
        "tipo": "extraer",
        "modelo": modelo,
        "tokens": resultado["tokens"],
        "tiempo_s": resultado["tiempo_s"],
        "datos_raw": resultado["content"],
        "finish": resultado["finish"],
    }


def ejecutar_sintesis(mensaje: str, contexto: str, modelo: str) -> dict:
    """Llamada de síntesis: razonamiento completo, prompt completo."""
    # SYSTEM_PROMPT idéntico al del chat_handler actual (no se recorta).
    from backend.chat_handler import SYSTEM_PROMPT
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{mensaje}\n\n[CONTEXTO]:\n{contexto}"},
    ]
    resultado = _llamar_llm(messages, modelo, max_tokens=16000)
    if not resultado["content"] and resultado["reasoning"]:
        fallback = "🤔 " + " ".join(resultado["reasoning"].split("\n")[-3:])[:300]
        return {"ok": True, "tipo": "sintetizar", "modelo": modelo,
                "tokens": resultado["tokens"], "tiempo_s": resultado["tiempo_s"],
                "respuesta": fallback, "finish": resultado["finish"], "fallback": True}
    return {
        "ok": True,
        "tipo": "sintetizar",
        "modelo": modelo,
        "tokens": resultado["tokens"],
        "tiempo_s": resultado["tiempo_s"],
        "respuesta": resultado["content"],
        "finish": resultado["finish"],
    }


def main():
    parser = argparse.ArgumentParser(description="lote_worker — subprocess LLM aislado")
    parser.add_argument("--tipo", choices=["extraer", "sintetizar"], required=True)
    parser.add_argument("--archivos", default="", help="rutas separadas por coma")
    parser.add_argument("--modelo", default="")
    parser.add_argument("--cc", default="")
    parser.add_argument("--mensaje", default="")
    parser.add_argument("--contexto-file", default="", help="ruta a archivo con contexto largo")
    args = parser.parse_args()

    if not API_KEY:
        print("ERROR: OPENCODE_GO_API_KEY no configurada", file=sys.stderr)
        sys.exit(1)

    try:
        if args.tipo == "extraer":
            archivos = [Path(p.strip()) for p in args.archivos.split(",") if p.strip()]
            if not archivos:
                print("ERROR: --archivos vacío", file=sys.stderr)
                sys.exit(1)
            modelo = args.modelo or MODEL_EXTRACCION
            resultado = ejecutar_extraccion(archivos, args.cc, modelo)
        else:  # sintetizar
            contexto = ""
            if args.contexto_file:
                contexto = Path(args.contexto_file).read_text(encoding="utf-8")
            modelo = args.modelo or MODEL_SINTESIS
            resultado = ejecutar_sintesis(args.mensaje, contexto, modelo)

        print(json.dumps(resultado, ensure_ascii=False))
        sys.exit(0 if resultado.get("ok") else 1)
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"ok": False, "error": str(e), "tipo_error": type(e).__name__}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Volver a ejecutar el test inicial — debe pasar**

Run:
```bash
pytest tests/test_lote_worker.py::test_lote_worker_sin_archivos_devuelve_error -v
```

Expected: PASS.

- [ ] **Step 5: Agregar test de memoria estable (regresión OOM)**

Agregar a `tests/test_lote_worker.py`:

```python
@pytest.mark.skipif(not os.getenv("OPENCODE_GO_API_KEY"), reason="needs OPENCODE_GO_API_KEY")
def test_lote_worker_memoria_padre_estable(tmp_path):
    """10 invocaciones consecutivas → memoria del padre no crece >50MB."""
    import psutil
    import os
    # Crear archivo .docx mínimo de prueba
    docx_path = tmp_path / "test.docx"
    from docx import Document
    doc = Document()
    doc.add_paragraph("PACIENTE: TEST")
    doc.add_paragraph("CC: 12345678")
    doc.save(str(docx_path))

    proc = psutil.Process(os.getpid())
    mem_inicial = proc.memory_info().rss / 1024 / 1024  # MB

    for i in range(10):
        code, salida, _ = _ejecutar_worker([
            "--tipo", "extraer",
            "--archivos", str(docx_path),
            "--modelo", "deepseek-chat",
            "--cc", "12345678",
        ])
        # No exigimos ok=True (puede fallar la API), sólo que el padre sobreviva

    mem_final = proc.memory_info().rss / 1024 / 1024
    delta = mem_final - mem_inicial
    assert delta < 50, f"Memoria padre creció {delta:.1f}MB tras 10 invocaciones"
```

- [ ] **Step 6: Ejecutar test de memoria**

Run:
```bash
pytest tests/test_lote_worker.py::test_lote_worker_memoria_padre_estable -v
```

Expected: PASS (skip si no hay API key, lo cual es OK localmente).

- [ ] **Step 7: Test de exit code limpio con archivo válido**

Agregar:

```python
@pytest.mark.skipif(not os.getenv("OPENCODE_GO_API_KEY"), reason="needs OPENCODE_GO_API_KEY")
def test_lote_worker_extraccion_devuelve_json_valido(tmp_path):
    """Con archivo válido + API disponible, debe devolver JSON parseable."""
    from docx import Document
    docx_path = tmp_path / "paciente.docx"
    doc = Document()
    doc.add_paragraph("Paciente Juan Carlos Duran Narvaez")
    doc.add_paragraph("Cédula: 1193143688")
    doc.add_paragraph("Siniestro: 503463870 fecha 02/03/2026")
    doc.save(str(docx_path))

    code, salida, stderr = _ejecutar_worker([
        "--tipo", "extraer",
        "--archivos", str(docx_path),
        "--modelo", "deepseek-chat",
        "--cc", "1193143688",
    ])
    assert code == 0, f"exit {code}, stderr={stderr[:300]}"
    assert salida.get("ok") is True
    assert "datos_raw" in salida
    assert salida.get("modelo") == "deepseek-chat"
```

- [ ] **Step 8: Ejecutar todos los tests del worker**

Run:
```bash
pytest tests/test_lote_worker.py -v
```

Expected: 3 PASS (o skip si no hay API key).

- [ ] **Step 9: Commit**

```bash
git add backend/lote_worker.py tests/test_lote_worker.py
git commit -m "🔧 lote_worker: subprocess aislado para resolver OOM v4"
```

---

## Task 3: Integrar `lote_worker` en `chat_handler.py`

**Files:**
- Modify: `backend/chat_handler.py:589-677` (reemplazar `_procesar_en_lotes`)
- Create: `tests/test_chat_integration.py`

- [ ] **Step 1: Test de integración — chat_handler invoca subprocess**

`tests/test_chat_integration.py`:

```python
"""Tests de integración del chat_handler con subprocess workers."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_chat_handler_procesar_via_workers_invoca_subprocess(tmp_path, monkeypatch):
    """_procesar_via_workers debe usar subprocess.run, no llamadas en-proceso."""
    monkeypatch.setenv("FASE_A_ENABLED", "true")
    from backend import chat_handler

    # Crear 3 docx de prueba
    from docx import Document
    archivos = []
    for i in range(3):
        p = tmp_path / f"test_{i}.docx"
        doc = Document()
        doc.add_paragraph(f"Documento {i}")
        doc.save(str(p))
        archivos.append((p, 1, "01/01/2026"))

    with patch("backend.chat_handler.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"ok": true, "datos_raw": "PACIENTE: TEST"}',
            stderr="",
        )
        resultado = chat_handler._procesar_via_workers(archivos, cc="1193143688")

    assert mock_run.called, "subprocess.run no fue invocado"
    assert mock_run.call_count == 3, f"Esperado 3 subprocess (1 por archivo), invocado {mock_run.call_count}"
    args = mock_run.call_args_list[0][0][0]
    assert "lote_worker" in " ".join(args)
    assert isinstance(resultado, str)
    assert "PACIENTE" in resultado
```

- [ ] **Step 2: Ejecutar test — debe fallar (función no existe)**

Run:
```bash
pytest tests/test_chat_integration.py::test_chat_handler_procesar_via_workers_invoca_subprocess -v
```

Expected: FAIL con `AttributeError: module 'backend.chat_handler' has no attribute '_procesar_via_workers'`.

- [ ] **Step 3: Agregar `_procesar_via_workers` a `chat_handler.py`**

Agregar antes de `_procesar_en_lotes` (línea ~589). Importar `subprocess` al principio del archivo:

```python
# Al inicio del archivo, junto a los otros imports
import subprocess


# Antes de def _procesar_en_lotes:
def _procesar_via_workers(archivos: list, cc: str) -> str:
    """
    Reemplazo de _procesar_en_lotes que aísla cada llamada LLM en subprocess.
    
    Cada subprocess procesa 1 archivo, imprime JSON con datos extraídos, muere.
    El OS libera la RAM del reasoning_content de DeepSeek al terminar el proceso.
    
    Para extracción usa LLM_MODEL_EXTRACCION (deepseek-chat por defecto, sin razonamiento).
    Los resultados se concatenan y se devuelven como string para inyectar al contexto.
    """
    modelo_extraccion = os.getenv("LLM_MODEL_EXTRACCION", "deepseek-chat")
    _log(f"WORKERS: {len(archivos)} archivos con modelo={modelo_extraccion}")
    t0 = time.time()
    
    todos_datos = []
    for i, (path, size_kb, mtime) in enumerate(archivos):
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "backend.lote_worker",
                 "--tipo", "extraer",
                 "--archivos", str(path),
                 "--modelo", modelo_extraccion,
                 "--cc", cc],
                capture_output=True, text=True, timeout=180,
                cwd=str(Path(__file__).parent.parent),
            )
            if proc.returncode == 0 and proc.stdout:
                resultado = json.loads(proc.stdout)
                if resultado.get("ok") and resultado.get("datos_raw"):
                    todos_datos.append(
                        f"═══ DOC {i+1}/{len(archivos)} ({path.name}) ═══\n"
                        f"{resultado['datos_raw']}"
                    )
                    tokens = resultado.get("tokens", {})
                    _log(f"WORKER {i+1}: {tokens.get('total', '?')}t en {resultado.get('tiempo_s', '?')}s")
            else:
                _log(f"WORKER {i+1}: FAILED exit={proc.returncode} stderr={proc.stderr[:200]}")
                todos_datos.append(f"═══ DOC {i+1} ({path.name}) ═══\n[ERROR de extracción]")
        except subprocess.TimeoutExpired:
            _log(f"WORKER {i+1}: TIMEOUT")
            todos_datos.append(f"═══ DOC {i+1} ({path.name}) ═══\n[TIMEOUT]")
        except Exception as e:
            _log(f"WORKER {i+1}: {type(e).__name__}: {e}")
            todos_datos.append(f"═══ DOC {i+1} ({path.name}) ═══\n[{type(e).__name__}]")
    
    elapsed = time.time() - t0
    resultado_str = "\n\n".join(todos_datos)
    _log(f"WORKERS: {len(archivos)} procesados en {elapsed:.1f}s → {len(resultado_str)} chars")
    
    return f"""[DATOS EXTRAÍDOS DE {len(archivos)} FORMATOS POR WORKERS AISLADOS]

{resultado_str}

⚠️ Tu tarea con estos datos:
1. CRUZAR campos entre documentos, detectar inconsistencias
2. VERIFICAR contra portales (marcar ✅/⚠️/❌)
3. ORGANIZAR información por secciones
4. CORREGIR discrepancias detectadas
5. COMPLETAR campos faltantes con prioridad"""
```

- [ ] **Step 4: Modificar `procesar_mensaje` para usar workers cuando FASE_A_ENABLED=true**

En `chat_handler.py` línea ~700 (dentro de `procesar_mensaje`), reemplazar:

```python
    if archivos_paciente and len(archivos_paciente) >= 3:
        # MODO LOTES: procesar 3-4 archivos por lote, comprimir, luego cruzar
        doc_content = _procesar_en_lotes(archivos_paciente, cc, mensaje)
        archivo_nombre = f"{len(archivos_paciente)} archivos (lotes)"
```

Por:

```python
    if archivos_paciente and len(archivos_paciente) >= 3:
        # MODO WORKERS (Fase A) o LOTES (legacy)
        if os.getenv("FASE_A_ENABLED", "false").lower() == "true":
            doc_content = _procesar_via_workers(archivos_paciente, cc)
            archivo_nombre = f"{len(archivos_paciente)} archivos (workers)"
        else:
            doc_content = _procesar_en_lotes(archivos_paciente, cc, mensaje)
            archivo_nombre = f"{len(archivos_paciente)} archivos (lotes-legacy)"
```

- [ ] **Step 5: Ejecutar test de integración**

Run:
```bash
pytest tests/test_chat_integration.py -v
```

Expected: PASS.

- [ ] **Step 6: Sanity check end-to-end con archivo real (opcional, requiere API)**

```bash
FASE_A_ENABLED=true python -c "
from backend.chat_handler import procesar_mensaje
r = procesar_mensaje('revisa al paciente 1193143688', paciente_cc='1193143688')
print(r.get('contenido', '')[:500])
print(f'Tiempo: {r.get(\"tiempo\", \"?\")}')"
```

Expected: respuesta razonable, no crashea, sin exit 137.

- [ ] **Step 7: Commit**

```bash
git add backend/chat_handler.py tests/test_chat_integration.py
git commit -m "🔧 chat_handler: _procesar_via_workers usando subprocess (Fase A)"
```

---

## Task 4: `playwright_real/selectores.py` — constantes de portales

**Files:**
- Create: `backend/playwright_real/selectores.py`

- [ ] **Step 1: Crear archivo con todos los selectores documentados**

`backend/playwright_real/selectores.py`:

```python
"""
Selectores CSS/XPath/JS de los portales Medifolios y ARL Positiva.

Origen: skills/flujo-browser/references/ (7 pasadas de exploración).
Cuando un portal cambie HTML, actualizar SOLO este archivo.

Cada selector tiene 3 fallbacks: CSS principal, XPath alternativo, texto visible.
"""

# ═══════════════════════════════════════════════════════════════════════
# MEDIFOLIOS
# ═══════════════════════════════════════════════════════════════════════

MEDI_URL = "https://www.server0medifolios.net/"

MEDI_LOGIN = {
    "usuario_input": "input[name='USUARIO'], #USUARIO, input[type='text']",
    "password_input": "input[name='CONTRASEÑA'], input[name='CONTRASENA'], input[type='password']",
    "submit_button": "button:has-text('Ingresar'), input[type='submit']",
    "popup_cambia_password_close": "button:has-text('Close'), .modal .close",
    "post_login_heartbeat": "text=Bienvenido, Sandra",
}

MEDI_PACIENTES = {
    "menu_pacientes": "a:has-text('Pacientes'), [href*='pacientes']",
    "numero_id_input": "#numero_id",
    "nombre1": "#nombre1",
    "nombre2": "#nombre2",
    "apellido1": "#apellido1",
    "apellido2": "#apellido2",
    "fecha_nacimiento": "#fecha_nacimiento",
    "telefono": "#telefono",
    "direccion": "#direccion",
    "email": "#email",
    "eps_select": "#slct_eps_paciente",
    "afp_select": "#slct_afp_paciente",
    "arl_select": "#slct_arl_paciente",
    "empresa_select": "#slct_empresa_paciente",
}

# JS para forzar carga de paciente (Enter nativo no dispara búsqueda)
MEDI_JS_CARGAR_PACIENTE = """
(cc) => {
    const f = document.getElementById('numero_id');
    if (!f) return false;
    f.value = cc;
    f.dispatchEvent(new Event('input', {bubbles: true}));
    f.dispatchEvent(new Event('change', {bubbles: true}));
    f.blur();
    f.focus();
    f.blur();
    f.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', keyCode:13, bubbles:true}));
    return true;
}
"""

# JS para volcar todos los campos del form de pacientes
MEDI_JS_EXTRAER_FORM = """
() => {
    const ids = ['numero_id','nombre1','nombre2','apellido1','apellido2',
                 'fecha_nacimiento','telefono','direccion','email'];
    const d = {};
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) d[id] = el.value || (el.textContent || '').trim();
    });
    ['slct_eps_paciente','slct_afp_paciente','slct_arl_paciente','slct_empresa_paciente'].forEach(id => {
        const el = document.getElementById(id);
        if (el && el.options && el.selectedIndex >= 0) {
            d[id] = el.options[el.selectedIndex].text;
        }
    });
    return d;
}
"""

MEDI_AGENDA = {
    "menu_agenda": "a:has-text('Agenda Citas'), [href*='agenda']",
    "select_profesional": "select",
    "valor_sandra": "168-0",  # SANDRA PATRICIA POLANIA - TODOS LOS PUNTOS
    "cita_link_template": "a:has-text('{cc}'), tr:has-text('{cc}') a",
    "popup_detalle_observaciones": "textarea[name='observaciones'], #observaciones",
}

# Regex para extraer siniestro del campo observaciones
MEDI_REGEX_SINIESTRO = r'NO\.?\s*SINIESTRO\s*(\d+)'


# ═══════════════════════════════════════════════════════════════════════
# ARL POSITIVA
# ═══════════════════════════════════════════════════════════════════════

POS_URL = "https://positivacuida.positiva.gov.co/cas/login?service=https://positivacuida.positiva.gov.co/web/j_spring_cas_security_check"

POS_LOGIN = {
    "usuario_input": "input[name='username'], #username",
    "password_input": "input[name='password'], #password",
    "submit_button": "button[type='submit'], input[name='submit']",
    "post_login_heartbeat": "text=MARIA GREIDY",
}

POS_CONSULTA_INTEGRAL = {
    "menu": "a:has-text('Consulta integral')",
    "tipo_id_select": "select[name='tipoIdentificacion']",
    "numero_id_input": "input[name='numeroIdentificacion'], #numeroIdentificacion",
    "buscar_button": "button:has-text('Buscar'), input[value='Buscar']",
}

POS_TABS = {
    "datos_asegurado": "a:has-text('DATOS ASEGURADO'), [data-tab='datos']",
    "siniestros": "a:has-text('SINIESTROS')",
    "rehab_integral": "a:has-text('REHABILITACIÓN INTEGRAL')",
    "gestion_aut": "a:has-text('GESTIÓN AUTORIZACIONES')",
    "evoluciones": "a:has-text('EVOLUCIONES')",
    "bitacoras": "a:has-text('BITACORAS')",
}

# Selectores por columna en la tabla SINIESTROS de Positiva
POS_TABLA_SINIESTROS = {
    "filas": "table.siniestros tbody tr, [data-tab='siniestros'] tbody tr",
    "col_siniestro": 1,
    "col_fecha": 2,
    "col_tipo_evento": 3,
    "col_pcl": 6,
    "col_diagnostico": 8,
}


# ═══════════════════════════════════════════════════════════════════════
# TIMEOUTS Y REINTENTOS
# ═══════════════════════════════════════════════════════════════════════

TIMEOUT_NAVEGACION_MS = 30_000
TIMEOUT_ELEMENTO_MS = 10_000
REINTENTOS = [2, 5, 15]  # segundos entre reintentos
```

- [ ] **Step 2: Sanity check — importar selectores**

Run:
```bash
python -c "from backend.playwright_real import selectores; print(selectores.MEDI_URL)"
```

Expected: imprime URL de Medifolios.

- [ ] **Step 3: Commit**

```bash
git add backend/playwright_real/selectores.py
git commit -m "🌐 playwright_real: selectores de Medifolios y Positiva"
```

---

## Task 5: `playwright_real/session.py` — login y storage_state

**Files:**
- Create: `backend/playwright_real/session.py`
- Create: `tests/test_playwright_session.py`

- [ ] **Step 1: Test que falla — login Medifolios crea storage_state**

`tests/test_playwright_session.py`:

```python
"""Tests para playwright_real/session.py."""
import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.live
@pytest.mark.asyncio
async def test_login_medifolios_guarda_storage_state(tmp_path, monkeypatch):
    """Login real contra Medifolios + verificar que se crea storage_state."""
    monkeypatch.setenv("PLAYWRIGHT_SESSIONS_DIR", str(tmp_path))
    from backend.playwright_real.session import login_y_guardar
    
    state_path = await login_y_guardar(portal="medifolios")
    
    assert state_path.exists(), f"storage_state no fue creado: {state_path}"
    assert state_path.stat().st_size > 100, "storage_state demasiado pequeño"


@pytest.mark.live
@pytest.mark.asyncio
async def test_sesion_activa_reusa_state(tmp_path, monkeypatch):
    """Si existe storage_state válido, no re-loguea."""
    monkeypatch.setenv("PLAYWRIGHT_SESSIONS_DIR", str(tmp_path))
    from backend.playwright_real.session import login_y_guardar, abrir_contexto
    
    # Primera vez: login
    await login_y_guardar(portal="medifolios")
    
    # Segunda vez: usar el state, debe pasar el heartbeat
    async with abrir_contexto(portal="medifolios") as (browser, ctx, page):
        from backend.playwright_real.selectores import MEDI_LOGIN
        # Heartbeat post-login: que el texto exista
        heartbeat = await page.locator(MEDI_LOGIN["post_login_heartbeat"]).count()
        assert heartbeat > 0, "heartbeat post-login falló — re-login esperado"
```

- [ ] **Step 2: Ejecutar test — debe fallar (módulo no existe)**

Run:
```bash
pytest tests/test_playwright_session.py -v --live
```

Expected: FAIL con ModuleNotFoundError (o ImportError).

- [ ] **Step 3: Implementación de `backend/playwright_real/session.py`**

```python
"""
Manejo de sesión Playwright con storage_state persistente y re-login automático.

Cada portal tiene un archivo de state en PLAYWRIGHT_SESSIONS_DIR/{portal}.json.
El state contiene cookies + localStorage. Vive ~15 min en ambos portales.

Uso:
    async with abrir_contexto(portal="medifolios") as (browser, ctx, page):
        # ya estás logueado (re-auto si hace falta)
        await page.goto(...)
"""
import os
import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Tuple

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from backend.playwright_real import selectores as S


SESSIONS_DIR = Path(os.getenv("PLAYWRIGHT_SESSIONS_DIR", "./storage/playwright_sessions"))
DEBUG = os.getenv("PLAYWRIGHT_DEBUG", "false").lower() == "true"
TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "30000"))


def _log(msg: str):
    import sys
    from datetime import datetime
    print(f"[PWREAL {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _state_path(portal: str) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR / f"{portal}.json"


async def _login_medifolios(page: Page):
    """Hace login en Medifolios. Asume page acaba de cargar MEDI_URL."""
    await page.goto(S.MEDI_URL, timeout=TIMEOUT_MS)
    await page.fill(S.MEDI_LOGIN["usuario_input"], os.getenv("MEDIFOLIOS_USER", ""))
    await page.fill(S.MEDI_LOGIN["password_input"], os.getenv("MEDIFOLIOS_PASSWORD", ""))
    await page.click(S.MEDI_LOGIN["submit_button"])
    # Cerrar popup "Cambia tu contraseña"
    try:
        await page.wait_for_selector(S.MEDI_LOGIN["popup_cambia_password_close"], timeout=5000)
        await page.click(S.MEDI_LOGIN["popup_cambia_password_close"])
    except Exception:
        pass
    # Verificar login OK
    await page.wait_for_selector(S.MEDI_LOGIN["post_login_heartbeat"], timeout=TIMEOUT_MS)
    _log("MEDI: login OK")


async def _login_positiva(page: Page):
    """Hace login en ARL Positiva."""
    await page.goto(S.POS_URL, timeout=TIMEOUT_MS)
    await page.fill(S.POS_LOGIN["usuario_input"], os.getenv("POSITIVA_USER", ""))
    await page.fill(S.POS_LOGIN["password_input"], os.getenv("POSITIVA_PASSWORD", ""))
    await page.click(S.POS_LOGIN["submit_button"])
    await page.wait_for_selector(S.POS_LOGIN["post_login_heartbeat"], timeout=TIMEOUT_MS)
    _log("POS: login OK")


async def _verificar_sesion(page: Page, portal: str) -> bool:
    """Heartbeat post-login: ¿la sesión sigue viva?"""
    selector = S.MEDI_LOGIN["post_login_heartbeat"] if portal == "medifolios" else S.POS_LOGIN["post_login_heartbeat"]
    try:
        count = await page.locator(selector).count()
        return count > 0
    except Exception:
        return False


async def login_y_guardar(portal: str) -> Path:
    """Hace login limpio y guarda storage_state. Retorna path al state."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not DEBUG)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        try:
            if portal == "medifolios":
                await _login_medifolios(page)
            elif portal == "positiva":
                await _login_positiva(page)
            else:
                raise ValueError(f"portal desconocido: {portal}")
            
            state_path = _state_path(portal)
            await ctx.storage_state(path=str(state_path))
            _log(f"{portal.upper()}: storage_state guardado en {state_path}")
            return state_path
        finally:
            await browser.close()


@asynccontextmanager
async def abrir_contexto(portal: str) -> Tuple[Browser, BrowserContext, Page]:
    """
    Context manager: devuelve (browser, context, page) listo para usar.
    Auto-loguea si el state no existe o expiró.
    """
    state_path = _state_path(portal)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not DEBUG)
        
        # Intentar cargar state existente
        kwargs = {}
        if state_path.exists():
            kwargs["storage_state"] = str(state_path)
        ctx = await browser.new_context(**kwargs)
        page = await ctx.new_page()
        
        # Verificar sesión navegando a la home post-login
        home_url = S.MEDI_URL if portal == "medifolios" else S.POS_URL.split("?")[0].replace("/cas/login", "/web/")
        await page.goto(home_url, timeout=TIMEOUT_MS)
        
        if not await _verificar_sesion(page, portal):
            _log(f"{portal.upper()}: sesión expirada o inexistente — re-login")
            if portal == "medifolios":
                await _login_medifolios(page)
            else:
                await _login_positiva(page)
            await ctx.storage_state(path=str(state_path))
        
        try:
            yield browser, ctx, page
        finally:
            # Actualizar state al salir (cookies pueden haber cambiado)
            try:
                await ctx.storage_state(path=str(state_path))
            except Exception:
                pass
            await browser.close()
```

- [ ] **Step 4: Ejecutar tests live**

Run:
```bash
pytest tests/test_playwright_session.py -v --live
```

Expected: PASS si las credenciales son correctas y los portales están up.

- [ ] **Step 5: Smoke test manual con debug visible (opcional)**

Run:
```bash
PLAYWRIGHT_DEBUG=true python -c "
import asyncio
from backend.playwright_real.session import login_y_guardar
asyncio.run(login_y_guardar('medifolios'))
"
```

Expected: ventana Chrome se abre, hace login, guarda state, cierra.

- [ ] **Step 6: Commit**

```bash
git add backend/playwright_real/session.py tests/test_playwright_session.py
git commit -m "🌐 playwright_real: session con login + storage_state + re-auth"
```

---

## Task 6: `playwright_real/medifolios.py` — extracción real

**Files:**
- Create: `backend/playwright_real/medifolios.py`
- Create: `tests/test_extractor_medi.py`

- [ ] **Step 1: Test live para extracción de paciente conocido**

`tests/test_extractor_medi.py`:

```python
"""Tests para extractor real Medifolios."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.live
@pytest.mark.asyncio
async def test_extraer_paciente_sandra():
    """CC 55162801 = Sandra. Sus datos siempre están en Medifolios."""
    from backend.playwright_real.medifolios import get_paciente_completo
    from backend.playwright_real.session import abrir_contexto
    
    async with abrir_contexto(portal="medifolios") as (_, _, page):
        datos = await get_paciente_completo(page, cc="55162801")
    
    assert isinstance(datos, dict)
    assert "nombre" in datos or "nombre1" in datos
    nombre = datos.get("nombre") or f"{datos.get('nombre1','')} {datos.get('apellido1','')}"
    assert "SANDRA" in nombre.upper()
```

- [ ] **Step 2: Ejecutar test — debe fallar**

Run:
```bash
pytest tests/test_extractor_medi.py -v --live
```

Expected: FAIL con ModuleNotFoundError.

- [ ] **Step 3: Implementación de `backend/playwright_real/medifolios.py`**

```python
"""
Extractor real de datos del paciente desde Medifolios.

Usa los selectores documentados en skills/flujo-browser/references/.
4 fuentes de datos:
  1. Form pacientes (DATOS PERSONALES + DATOS GENERALES)
  2. Historia Clínica → Visión Clínica
  3. Agenda Citas → Popup → Observaciones (siniestro)
"""
import re
from typing import Dict
from playwright.async_api import Page

from backend.playwright_real import selectores as S


async def _navegar_a_pacientes(page: Page):
    """Click en menú Pacientes."""
    try:
        await page.click(S.MEDI_PACIENTES["menu_pacientes"], timeout=10000)
    except Exception:
        pass  # ya podemos estar ahí
    await page.wait_for_selector(S.MEDI_PACIENTES["numero_id_input"], timeout=10000)


async def _cargar_paciente_en_form(page: Page, cc: str) -> bool:
    """JS para forzar carga (Enter nativo no dispara)."""
    ok = await page.evaluate(S.MEDI_JS_CARGAR_PACIENTE, cc)
    if not ok:
        return False
    # Esperar a que el form se llene
    await page.wait_for_function(
        "() => { const f = document.getElementById('nombre1'); return f && f.value.length > 0; }",
        timeout=15000,
    )
    return True


async def _extraer_form_pacientes(page: Page) -> Dict:
    """Extrae todos los campos del form de pacientes vía JS."""
    return await page.evaluate(S.MEDI_JS_EXTRAER_FORM)


async def _extraer_siniestro_de_agenda(page: Page, cc: str) -> str:
    """Navega a Agenda Citas → busca cita del paciente → extrae siniestro de observaciones."""
    try:
        await page.click(S.MEDI_AGENDA["menu_agenda"], timeout=10000)
    except Exception:
        return ""
    
    # Seleccionar profesional Sandra
    try:
        await page.select_option(S.MEDI_AGENDA["select_profesional"], S.MEDI_AGENDA["valor_sandra"])
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    
    # Buscar cita que contenga el CC
    try:
        link_selector = S.MEDI_AGENDA["cita_link_template"].format(cc=cc)
        await page.click(link_selector, timeout=5000)
    except Exception:
        return ""
    
    # Leer observaciones del popup
    try:
        obs_el = await page.wait_for_selector(S.MEDI_AGENDA["popup_detalle_observaciones"], timeout=5000)
        observaciones = await obs_el.input_value() if obs_el else ""
        match = re.search(S.MEDI_REGEX_SINIESTRO, observaciones, re.IGNORECASE)
        return match.group(1) if match else ""
    except Exception:
        return ""


async def get_paciente_completo(page: Page, cc: str) -> Dict:
    """
    Función principal. Retorna dict con campos extraídos + campos faltantes marcados.
    """
    datos = {"cc_buscado": cc, "fuente": "medifolios"}
    
    # 1. Form pacientes
    try:
        await _navegar_a_pacientes(page)
        cargado = await _cargar_paciente_en_form(page, cc)
        if cargado:
            form = await _extraer_form_pacientes(page)
            datos.update(form)
        else:
            datos["error_form"] = "no se pudo cargar el paciente"
    except Exception as e:
        datos["error_form"] = f"{type(e).__name__}: {e}"
    
    # 2. Siniestro desde Agenda
    try:
        siniestro = await _extraer_siniestro_de_agenda(page, cc)
        if siniestro:
            datos["siniestro_medi"] = siniestro
        else:
            datos["siniestro_medi"] = "[VERIFICAR]"
    except Exception as e:
        datos["error_siniestro"] = f"{type(e).__name__}: {e}"
        datos["siniestro_medi"] = "[VERIFICAR]"
    
    return datos
```

- [ ] **Step 4: Ejecutar test live**

Run:
```bash
pytest tests/test_extractor_medi.py::test_extraer_paciente_sandra -v --live
```

Expected: PASS con datos de Sandra extraídos.

- [ ] **Step 5: Smoke manual contra CC de prueba**

Run:
```bash
python -c "
import asyncio
from backend.playwright_real.session import abrir_contexto
from backend.playwright_real.medifolios import get_paciente_completo

async def main():
    async with abrir_contexto(portal='medifolios') as (_, _, page):
        datos = await get_paciente_completo(page, cc='55162801')
        for k, v in datos.items():
            print(f'  {k}: {v}')

asyncio.run(main())
"
```

Expected: imprime nombre/CC/teléfono/dirección de Sandra.

- [ ] **Step 6: Commit**

```bash
git add backend/playwright_real/medifolios.py tests/test_extractor_medi.py
git commit -m "🌐 playwright_real: medifolios.get_paciente_completo (form + siniestro)"
```

---

## Task 7: `playwright_real/positiva.py` — extracción real

**Files:**
- Create: `backend/playwright_real/positiva.py`
- Create: `tests/test_extractor_pos.py`

- [ ] **Step 1: Test live**

`tests/test_extractor_pos.py`:

```python
"""Tests para extractor real ARL Positiva."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.live
@pytest.mark.asyncio
async def test_extraer_paciente_juan():
    """CC 1193143688 = Juan Carlos Duran. Tiene siniestros en Positiva."""
    from backend.playwright_real.positiva import get_paciente_completo
    from backend.playwright_real.session import abrir_contexto
    
    async with abrir_contexto(portal="positiva") as (_, _, page):
        datos = await get_paciente_completo(page, cc="1193143688")
    
    assert isinstance(datos, dict)
    # Debe haber al menos un siniestro
    assert datos.get("siniestros", []) or datos.get("siniestro_principal"), \
        f"No se extrajo siniestro. Datos: {datos}"
```

- [ ] **Step 2: Ejecutar test — debe fallar**

Run:
```bash
pytest tests/test_extractor_pos.py -v --live
```

Expected: FAIL con ModuleNotFoundError.

- [ ] **Step 3: Implementación de `backend/playwright_real/positiva.py`**

```python
"""
Extractor real ARL Positiva.

Consulta Integral → 6 pestañas:
  DATOS ASEGURADO, SINIESTROS, REHABILITACIÓN INTEGRAL,
  GESTIÓN AUTORIZACIONES, EVOLUCIONES, BITACORAS
"""
from typing import Dict, List
from playwright.async_api import Page

from backend.playwright_real import selectores as S


async def _buscar_paciente(page: Page, cc: str) -> bool:
    """Va a Consulta Integral y busca por CC."""
    try:
        await page.click(S.POS_CONSULTA_INTEGRAL["menu"], timeout=10000)
        await page.wait_for_selector(S.POS_CONSULTA_INTEGRAL["numero_id_input"], timeout=10000)
        await page.fill(S.POS_CONSULTA_INTEGRAL["numero_id_input"], cc)
        await page.click(S.POS_CONSULTA_INTEGRAL["buscar_button"])
        await page.wait_for_load_state("networkidle", timeout=15000)
        return True
    except Exception:
        return False


async def _click_tab(page: Page, tab_selector: str) -> bool:
    """Click en una pestaña de Consulta Integral."""
    try:
        await page.click(tab_selector, timeout=8000)
        await page.wait_for_load_state("networkidle", timeout=10000)
        return True
    except Exception:
        return False


async def _extraer_datos_asegurado(page: Page) -> Dict:
    """Pestaña DATOS ASEGURADO → form con nombre, dirección, teléfonos."""
    if not await _click_tab(page, S.POS_TABS["datos_asegurado"]):
        return {"_error_tab_datos": True}
    return await page.evaluate("""
        () => {
            const d = {};
            document.querySelectorAll('input, span, td').forEach(el => {
                const label = (el.previousElementSibling?.textContent || el.parentElement?.querySelector('label,th')?.textContent || '').trim();
                const val = (el.value || el.textContent || '').trim();
                if (label && val && val.length < 200 && label.length < 60) {
                    d[label] = val;
                }
            });
            return d;
        }
    """)


async def _extraer_siniestros(page: Page) -> List[Dict]:
    """Pestaña SINIESTROS → tabla con filas."""
    if not await _click_tab(page, S.POS_TABS["siniestros"]):
        return []
    return await page.evaluate("""
        () => {
            const filas = document.querySelectorAll('table tbody tr');
            return Array.from(filas).map(fila => {
                const c = fila.querySelectorAll('td');
                return {
                    siniestro: c[1]?.textContent?.trim() || '',
                    fecha: c[2]?.textContent?.trim() || '',
                    tipo_evento: c[3]?.textContent?.trim() || '',
                    pcl: c[6]?.textContent?.trim() || '',
                    diagnostico: c[8]?.textContent?.trim() || '',
                };
            }).filter(s => s.siniestro);
        }
    """)


async def _extraer_rehab(page: Page) -> List[Dict]:
    """Pestaña REHABILITACIÓN INTEGRAL → tabla con CIE-10."""
    if not await _click_tab(page, S.POS_TABS["rehab_integral"]):
        return []
    return await page.evaluate("""
        () => {
            const filas = document.querySelectorAll('table tbody tr');
            return Array.from(filas).map(fila => {
                const c = fila.querySelectorAll('td');
                return {
                    id_ingreso: c[1]?.textContent?.trim() || '',
                    fecha_ingreso: c[2]?.textContent?.trim() || '',
                    siniestro: c[3]?.textContent?.trim() || '',
                    diagnostico_cie10: c[6]?.textContent?.trim() || '',
                    proveedor: c[5]?.textContent?.trim() || '',
                    estado: c[8]?.textContent?.trim() || '',
                };
            }).filter(s => s.id_ingreso);
        }
    """)


async def get_paciente_completo(page: Page, cc: str) -> Dict:
    """Función principal — extrae las 6 pestañas (las 3 más críticas por ahora)."""
    datos = {"cc_buscado": cc, "fuente": "positiva"}
    
    if not await _buscar_paciente(page, cc):
        datos["error_busqueda"] = "no se pudo buscar el paciente"
        return datos
    
    # DATOS ASEGURADO
    try:
        datos["datos_asegurado"] = await _extraer_datos_asegurado(page)
    except Exception as e:
        datos["error_datos_asegurado"] = f"{type(e).__name__}: {e}"
    
    # SINIESTROS
    try:
        siniestros = await _extraer_siniestros(page)
        datos["siniestros"] = siniestros
        if siniestros:
            # El más reciente es el primero (Positiva ordena así)
            datos["siniestro_principal"] = siniestros[0]
    except Exception as e:
        datos["error_siniestros"] = f"{type(e).__name__}: {e}"
    
    # REHABILITACIÓN INTEGRAL
    try:
        datos["rehab_integral"] = await _extraer_rehab(page)
    except Exception as e:
        datos["error_rehab"] = f"{type(e).__name__}: {e}"
    
    return datos
```

- [ ] **Step 4: Ejecutar test live**

Run:
```bash
pytest tests/test_extractor_pos.py::test_extraer_paciente_juan -v --live
```

Expected: PASS con siniestros de Juan Carlos extraídos.

- [ ] **Step 5: Commit**

```bash
git add backend/playwright_real/positiva.py tests/test_extractor_pos.py
git commit -m "🌐 playwright_real: positiva.get_paciente_completo (3 tabs críticas)"
```

---

## Task 8: `playwright_real/orquestador.py` — fusión + discrepancias

**Files:**
- Create: `backend/playwright_real/orquestador.py`
- Create: `tests/test_orquestador_playwright.py`

- [ ] **Step 1: Test que falla — orquestador fusiona ambos portales**

`tests/test_orquestador_playwright.py`:

```python
"""Tests para orquestador playwright_real."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.asyncio
async def test_fusionar_detecta_discrepancia_siniestro():
    """Si Medi y Pos dan siniestros distintos, marca discrepancia."""
    from backend.playwright_real.orquestador import _fusionar
    
    datos_medi = {"siniestro_medi": "503463870"}
    datos_pos = {"siniestro_principal": {"siniestro": "503476658"}}
    
    fusionado = _fusionar(datos_medi, datos_pos, cc="1193143688")
    
    assert fusionado["_meta"]["discrepancias"]
    discrepancia = fusionado["_meta"]["discrepancias"][0]
    assert discrepancia["campo"] == "siniestro"
    assert fusionado["siniestro_final"] == "503476658"  # prevalece Positiva


@pytest.mark.asyncio
async def test_fusionar_sin_discrepancias():
    """Si ambos coinciden, no marca discrepancias."""
    from backend.playwright_real.orquestador import _fusionar
    
    datos_medi = {"siniestro_medi": "503463870"}
    datos_pos = {"siniestro_principal": {"siniestro": "503463870"}}
    
    fusionado = _fusionar(datos_medi, datos_pos, cc="1193143688")
    
    assert not fusionado["_meta"]["discrepancias"]
    assert fusionado["siniestro_final"] == "503463870"
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

Run:
```bash
pytest tests/test_orquestador_playwright.py -v
```

Expected: FAIL con ModuleNotFoundError.

- [ ] **Step 3: Implementación**

```python
"""
Orquestador playwright_real — combina extracción de Medifolios + ARL Positiva,
detecta discrepancias, devuelve JSON unificado.

Output: dict listo para guardar en storage/data/{cc}-completo.json.
"""
import asyncio
from datetime import datetime
from typing import Dict
from pathlib import Path

from backend.playwright_real import medifolios, positiva
from backend.playwright_real.session import abrir_contexto


def _fusionar(datos_medi: Dict, datos_pos: Dict, cc: str) -> Dict:
    """Unifica los 2 dicts, detecta discrepancias, asigna valores finales."""
    fusionado = {
        "cc": cc,
        "datos_medifolios": datos_medi,
        "datos_positiva": datos_pos,
        "_meta": {
            "extraido_en": datetime.now().isoformat(),
            "fuentes": ["medifolios", "positiva"],
            "discrepancias": [],
        },
    }
    
    # Reconciliación siniestro
    sin_medi = (datos_medi.get("siniestro_medi") or "").strip()
    sin_pos = ""
    if datos_pos.get("siniestro_principal"):
        sin_pos = datos_pos["siniestro_principal"].get("siniestro", "").strip()
    
    if sin_medi and sin_pos and sin_medi != sin_pos:
        fusionado["_meta"]["discrepancias"].append({
            "campo": "siniestro",
            "medifolios": sin_medi,
            "positiva": sin_pos,
            "resolucion": "prevalece Positiva (fuente oficial)",
        })
        fusionado["siniestro_final"] = sin_pos
    else:
        fusionado["siniestro_final"] = sin_pos or sin_medi or ""
    
    # Diagnóstico (de Positiva)
    if datos_pos.get("siniestro_principal"):
        fusionado["diagnostico_final"] = datos_pos["siniestro_principal"].get("diagnostico", "")
    
    # Marca de estado
    if fusionado["_meta"]["discrepancias"]:
        fusionado["estado_verificacion"] = "discrepancias"
    elif sin_medi and sin_pos:
        fusionado["estado_verificacion"] = "verificado"
    elif sin_medi or sin_pos:
        fusionado["estado_verificacion"] = "parcial"
    else:
        fusionado["estado_verificacion"] = "vacio"
    
    return fusionado


async def extraer_paciente_completo(cc: str, guardar_en: Path | None = None) -> Dict:
    """
    Extrae desde Medifolios + Positiva en secuencia (no paralelo: evitamos sobrecarga browser).
    Retorna dict fusionado. Si guardar_en se proporciona, escribe JSON ahí.
    """
    # Medifolios
    async with abrir_contexto(portal="medifolios") as (_, _, page_medi):
        datos_medi = await medifolios.get_paciente_completo(page_medi, cc)
    
    # Positiva
    async with abrir_contexto(portal="positiva") as (_, _, page_pos):
        datos_pos = await positiva.get_paciente_completo(page_pos, cc)
    
    fusionado = _fusionar(datos_medi, datos_pos, cc)
    
    if guardar_en:
        import json
        guardar_en.parent.mkdir(parents=True, exist_ok=True)
        guardar_en.write_text(
            json.dumps(fusionado, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    
    return fusionado


def extraer_sincrono(cc: str, guardar_en: Path | None = None) -> Dict:
    """Wrapper síncrono para llamar desde FastAPI."""
    return asyncio.run(extraer_paciente_completo(cc, guardar_en))
```

- [ ] **Step 4: Ejecutar tests — deben pasar**

Run:
```bash
pytest tests/test_orquestador_playwright.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Smoke test integral con paciente real (live)**

Agregar test live al mismo archivo:

```python
@pytest.mark.live
@pytest.mark.asyncio
async def test_extraer_paciente_completo_juan(tmp_path):
    """End-to-end: extrae Juan de ambos portales, fusiona, guarda."""
    from backend.playwright_real.orquestador import extraer_paciente_completo
    
    salida = tmp_path / "1193143688-completo.json"
    datos = await extraer_paciente_completo("1193143688", guardar_en=salida)
    
    assert datos["cc"] == "1193143688"
    assert datos["estado_verificacion"] in ["verificado", "parcial", "discrepancias"]
    assert salida.exists()
```

Run:
```bash
pytest tests/test_orquestador_playwright.py::test_extraer_paciente_completo_juan -v --live
```

Expected: PASS, archivo JSON guardado.

- [ ] **Step 6: Commit**

```bash
git add backend/playwright_real/orquestador.py tests/test_orquestador_playwright.py
git commit -m "🔗 playwright_real: orquestador fusión Medi+Pos con discrepancias"
```

---

## Task 9: Endpoints FastAPI nuevos

**Files:**
- Modify: `backend/server.py` (agregar al final, antes del `if __name__`)

- [ ] **Step 1: Test que falla — endpoint /api/verificar/{cc}/extraer-ahora**

Agregar a `tests/test_chat_integration.py`:

```python
def test_endpoint_extraer_ahora_existe():
    """El endpoint POST /api/verificar/{cc}/extraer-ahora debe existir."""
    from fastapi.testclient import TestClient
    from backend.server import app
    client = TestClient(app)
    # Sin paciente real, esperamos 4xx o 5xx — no 404
    resp = client.post("/api/verificar/9999999/extraer-ahora")
    assert resp.status_code != 404, "endpoint no registrado"
```

- [ ] **Step 2: Ejecutar test — debe fallar**

Run:
```bash
pytest tests/test_chat_integration.py::test_endpoint_extraer_ahora_existe -v
```

Expected: FAIL (404).

- [ ] **Step 3: Reemplazar endpoints `/api/verificar/...` en `server.py`**

En `backend/server.py`, eliminar los endpoints actuales `/api/verificar/{cc}` y `/api/verificar/{cc}/extraer` (líneas ~519-573) y agregar al final del archivo:

```python
# ─── Fase A: endpoints verificación browser real ───────────────

@app.get("/api/verificar/{cc}")
def verificar_paciente_v2(cc: str):
    """Devuelve datos pre-extraídos si existen, o estado pendiente."""
    data_dir = STORAGE / "data"
    archivos = list(data_dir.glob(f"*{cc}*-completo.json"))
    if not archivos:
        return {"ok": True, "estado": "pendiente_extraccion",
                "mensaje": f"No hay datos pre-extraídos para CC {cc}."}
    mas_reciente = max(archivos, key=lambda p: p.stat().st_mtime)
    with open(mas_reciente, encoding="utf-8") as f:
        datos = json.load(f)
    return {"ok": True, "estado": datos.get("estado_verificacion", "verificado"),
            "datos": datos, "archivo": str(mas_reciente),
            "fecha_extraccion": datetime.fromtimestamp(mas_reciente.stat().st_mtime).isoformat()}


@app.post("/api/verificar/{cc}/extraer-ahora")
async def extraer_paciente_ahora(cc: str):
    """
    Dispara extracción Playwright real contra Medifolios + ARL Positiva.
    Síncrono. Tarda ~1-3 min. Devuelve datos fusionados.
    """
    if os.getenv("FASE_A_ENABLED", "false").lower() != "true":
        raise HTTPException(503, "Fase A no habilitada. Activa FASE_A_ENABLED=true en .env")
    try:
        from backend.playwright_real.orquestador import extraer_paciente_completo
        archivo = STORAGE / "data" / f"{datetime.now().strftime('%Y%m%d')}-{cc}-completo.json"
        datos = await extraer_paciente_completo(cc, guardar_en=archivo)
        return {"ok": True, "estado": datos.get("estado_verificacion"),
                "datos": datos, "archivo": str(archivo)}
    except Exception as e:
        raise HTTPException(500, f"Error de extracción: {type(e).__name__}: {e}")


@app.get("/api/cron/estado")
def cron_estado():
    """Estado del scheduler APScheduler."""
    try:
        from backend.cron_pre_extraccion import scheduler, get_estado
        return {"ok": True, **get_estado()}
    except ImportError:
        return {"ok": False, "estado": "cron_no_inicializado"}


@app.post("/api/cron/disparar-ahora")
async def cron_disparar_ahora():
    """Fire manual del cron nocturno (testing)."""
    if os.getenv("FASE_A_ENABLED", "false").lower() != "true":
        raise HTTPException(503, "Fase A no habilitada")
    try:
        from backend.cron_pre_extraccion import revisar_email_y_extraer
        resultado = await revisar_email_y_extraer()
        return {"ok": True, **resultado}
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")


@app.get("/api/portales/health")
async def portales_health():
    """Heartbeat ligero de Medifolios y ARL Positiva."""
    if os.getenv("FASE_A_ENABLED", "false").lower() != "true":
        return {"ok": True, "fase_a": False}
    from backend.playwright_real.session import abrir_contexto, _verificar_sesion
    resultado = {}
    for portal in ["medifolios", "positiva"]:
        try:
            async with abrir_contexto(portal=portal) as (_, _, page):
                resultado[portal] = "ok" if await _verificar_sesion(page, portal) else "sin_sesion"
        except Exception as e:
            resultado[portal] = f"error: {type(e).__name__}"
    return {"ok": True, "portales": resultado}
```

- [ ] **Step 4: Ejecutar el test de existencia**

Run:
```bash
pytest tests/test_chat_integration.py::test_endpoint_extraer_ahora_existe -v
```

Expected: PASS (status != 404).

- [ ] **Step 5: Smoke con uvicorn**

Run:
```bash
cd /home/manu/Documentos/Temporal/auto-ma
uvicorn backend.server:app --port 8000 &
sleep 3
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/verificar/1193143688
pkill -f "uvicorn.*server:app"
```

Expected: respuestas JSON sin errores 500.

- [ ] **Step 6: Commit**

```bash
git add backend/server.py
git commit -m "🔌 server: endpoints verificación browser real + cron control"
```

---

## Task 10: `cron_pre_extraccion.py` — APScheduler

**Files:**
- Create: `backend/cron_pre_extraccion.py`
- Modify: `backend/server.py` (startup event)
- Create: `tests/test_cron.py`

- [ ] **Step 1: Test que falla — scheduler tiene job nocturno registrado**

`tests/test_cron.py`:

```python
"""Tests para cron_pre_extraccion."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_scheduler_registra_job_nocturno(monkeypatch):
    """Al iniciar, scheduler debe tener job 'pre_extraccion_nocturna' a las 21:00 COL."""
    monkeypatch.setenv("FASE_A_CRON_ENABLED", "true")
    from backend.cron_pre_extraccion import scheduler, iniciar
    iniciar()
    job = scheduler.get_job("pre_extraccion_nocturna")
    assert job is not None
    assert job.trigger.fields[5].name == "hour"  # cron hour field


@pytest.mark.asyncio
async def test_revisar_email_y_extraer_sin_citas(tmp_path, monkeypatch):
    """Si no hay citas mañana, no extrae nada y reporta OK."""
    monkeypatch.setenv("FASE_A_ENABLED", "true")
    monkeypatch.setattr("backend.cron_pre_extraccion.STORAGE", tmp_path)
    
    # Mock email_reader sin citas
    import backend.cron_pre_extraccion as cron
    async def mock_check_agenda():
        return {"ok": True, "citas": []}
    monkeypatch.setattr(cron, "_obtener_agenda_manana", mock_check_agenda)
    
    resultado = await cron.revisar_email_y_extraer()
    assert resultado["citas"] == 0
    assert resultado["ok"] is True
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

Run:
```bash
pytest tests/test_cron.py -v
```

Expected: FAIL con ModuleNotFoundError.

- [ ] **Step 3: Implementación de `backend/cron_pre_extraccion.py`**

```python
"""
Cron pre-extracción nocturna — APScheduler dentro de FastAPI.

21:00 COL: lee agenda Gmail de mañana, extrae cada paciente, guarda JSON,
notifica por Telegram (inicio + fin + alertas).
"""
import asyncio
import os
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


COL = pytz.timezone("America/Bogota")
STORAGE = Path(os.getenv("STORAGE_DIR", "./storage"))
HORA_NOCHE = int(os.getenv("CRON_HORA_NOCHE", "21"))
COOLDOWN_S = int(os.getenv("CRON_COOLDOWN_PACIENTES_S", "30"))

scheduler = AsyncIOScheduler(timezone=COL)
_estado_ultimo_run: Dict = {"ts": None, "ok": False, "detalles": {}}


def _log(msg: str):
    import sys
    print(f"[CRON {datetime.now(COL).strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


async def _obtener_agenda_manana() -> Dict:
    """Llama email_reader / notificador para obtener agenda de mañana."""
    try:
        from backend.notificador import api_get_agenda
        return api_get_agenda() or {"ok": False, "citas": []}
    except Exception as e:
        _log(f"AGENDA: error {e}")
        return {"ok": False, "citas": [], "error": str(e)}


async def _notificar_telegram(mensaje: str):
    """Envía mensaje a Sandra vía Telegram."""
    try:
        from backend.notificador import enviar_telegram
        enviar_telegram(mensaje)
    except Exception as e:
        _log(f"TELEGRAM: error {e}")


async def revisar_email_y_extraer() -> Dict:
    """Job principal: lee agenda + extrae por paciente + notifica."""
    global _estado_ultimo_run
    t0 = time.time()
    _estado_ultimo_run = {"ts": datetime.now(COL).isoformat(), "ok": False, "detalles": {}}
    
    if os.getenv("FASE_A_ENABLED", "false").lower() != "true":
        _log("FASE_A_ENABLED=false → cron skip")
        return {"ok": False, "skip": True, "razon": "FASE_A_ENABLED=false"}
    
    agenda = await _obtener_agenda_manana()
    citas = agenda.get("citas", [])
    
    if not citas:
        await _notificar_telegram("🌙 Sin citas para mañana. Buenas noches Sandra.")
        return {"ok": True, "citas": 0, "tiempo_s": time.time() - t0}
    
    await _notificar_telegram(
        f"🌙 Mañana {len(citas)} citas. Empiezo a buscar sus datos en los portales..."
    )
    
    # Importar Playwright sólo cuando vamos a usarlo
    from backend.playwright_real.orquestador import extraer_paciente_completo
    
    exitosos, parciales, errores = 0, 0, 0
    detalles = []
    
    for i, cita in enumerate(citas):
        cc = cita.get("cc") or cita.get("documento") or ""
        nombre = cita.get("paciente", "Sin nombre")
        if not cc:
            errores += 1
            detalles.append(f"❌ {nombre}: sin CC")
            continue
        
        archivo = STORAGE / "data" / f"{datetime.now().strftime('%Y%m%d')}-{cc}-completo.json"
        try:
            _log(f"PACIENTE {i+1}/{len(citas)}: {nombre} ({cc})")
            datos = await extraer_paciente_completo(cc, guardar_en=archivo)
            estado = datos.get("estado_verificacion")
            if estado == "verificado":
                exitosos += 1
                detalles.append(f"✅ {nombre}: OK")
            elif estado == "parcial":
                parciales += 1
                detalles.append(f"⚠️ {nombre}: parcial")
            else:
                detalles.append(f"❌ {nombre}: {estado}")
                errores += 1
        except Exception as e:
            _log(f"ERROR {nombre}: {e}")
            errores += 1
            detalles.append(f"❌ {nombre}: {type(e).__name__}")
        
        # Cooldown entre pacientes
        if i < len(citas) - 1:
            await asyncio.sleep(COOLDOWN_S)
    
    elapsed = time.time() - t0
    resumen = (
        f"✅ Listo. Datos para mañana:\n"
        f"  • {exitosos} completos\n"
        f"  • {parciales} parciales (revisar)\n"
        f"  • {errores} con error\n"
        f"Tiempo total: {elapsed/60:.1f} min"
    )
    await _notificar_telegram(resumen)
    
    _estado_ultimo_run = {
        "ts": datetime.now(COL).isoformat(),
        "ok": True,
        "detalles": {
            "citas": len(citas),
            "exitosos": exitosos,
            "parciales": parciales,
            "errores": errores,
            "tiempo_s": round(elapsed, 1),
            "lineas": detalles,
        },
    }
    return {"ok": True, "citas": len(citas), "exitosos": exitosos,
            "parciales": parciales, "errores": errores, "tiempo_s": elapsed}


def iniciar():
    """Registra jobs en el scheduler. Idempotente."""
    if not scheduler.running and os.getenv("FASE_A_CRON_ENABLED", "false").lower() == "true":
        scheduler.add_job(
            revisar_email_y_extraer,
            CronTrigger(hour=HORA_NOCHE, minute=0, timezone=COL),
            id="pre_extraccion_nocturna",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        scheduler.start()
        _log(f"Scheduler iniciado. Próximo run: {scheduler.get_job('pre_extraccion_nocturna').next_run_time}")


def detener():
    """Apaga el scheduler limpiamente."""
    if scheduler.running:
        scheduler.shutdown(wait=False)


def get_estado() -> Dict:
    """Estado para /api/cron/estado."""
    job = scheduler.get_job("pre_extraccion_nocturna") if scheduler.running else None
    return {
        "scheduler_running": scheduler.running,
        "proximo_run": job.next_run_time.isoformat() if job else None,
        "ultimo_run": _estado_ultimo_run,
    }
```

- [ ] **Step 4: Conectar scheduler al startup de FastAPI**

En `backend/server.py`, agregar después de la creación del `app`:

```python
# ── Fase A: arrancar/parar cron al levantar/cerrar FastAPI ──

@app.on_event("startup")
async def fase_a_startup():
    if os.getenv("FASE_A_ENABLED", "false").lower() == "true":
        try:
            from backend.cron_pre_extraccion import iniciar
            iniciar()
            print("[FASTAPI] Fase A cron scheduler iniciado")
        except Exception as e:
            print(f"[FASTAPI] Cron no inició: {e}")


@app.on_event("shutdown")
async def fase_a_shutdown():
    try:
        from backend.cron_pre_extraccion import detener
        detener()
    except Exception:
        pass
```

- [ ] **Step 5: Ejecutar tests**

Run:
```bash
pytest tests/test_cron.py -v
```

Expected: 2 PASS.

- [ ] **Step 6: Smoke manual — disparar cron sin esperar**

Run:
```bash
FASE_A_ENABLED=true FASE_A_CRON_ENABLED=true python -c "
import asyncio
from backend.cron_pre_extraccion import revisar_email_y_extraer
print(asyncio.run(revisar_email_y_extraer()))
"
```

Expected: corre, lee agenda, intenta extracciones, imprime resumen.

- [ ] **Step 7: Commit**

```bash
git add backend/cron_pre_extraccion.py backend/server.py tests/test_cron.py
git commit -m "⏰ cron: pre-extracción nocturna 21:00 COL con APScheduler"
```

---

## Task 11: Chat carga datos verificados + ofrece extracción on-demand

**Files:**
- Modify: `backend/chat_handler.py:680-727` (función `procesar_mensaje`)

- [ ] **Step 1: Test que falla — chat carga JSON pre-existente**

Agregar a `tests/test_chat_integration.py`:

```python
def test_chat_carga_datos_verificados_si_existen(tmp_path, monkeypatch):
    """Si hay storage/data/{cc}-completo.json, se inyecta al contexto."""
    monkeypatch.setenv("FASE_A_ENABLED", "true")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    archivo = data_dir / "20260519-1193143688-completo.json"
    archivo.write_text('{"cc": "1193143688", "siniestro_final": "503463870", "estado_verificacion": "verificado"}', encoding="utf-8")
    
    from backend.chat_handler import _cargar_datos_verificados
    datos = _cargar_datos_verificados("1193143688", storage_dir=tmp_path)
    
    assert datos is not None
    assert datos["siniestro_final"] == "503463870"
```

- [ ] **Step 2: Ejecutar test — debe fallar**

Run:
```bash
pytest tests/test_chat_integration.py::test_chat_carga_datos_verificados_si_existen -v
```

Expected: FAIL con AttributeError.

- [ ] **Step 3: Agregar `_cargar_datos_verificados` a `chat_handler.py`**

Agregar antes de `procesar_mensaje`:

```python
def _cargar_datos_verificados(cc: str, storage_dir: Path = None) -> Optional[dict]:
    """Carga el JSON pre-extraído más reciente del paciente, si existe."""
    if not cc:
        return None
    storage = storage_dir or Path(os.getenv("STORAGE_DIR", "./storage"))
    data_dir = storage / "data"
    if not data_dir.exists():
        return None
    archivos = list(data_dir.glob(f"*{cc}*-completo.json"))
    if not archivos:
        return None
    mas_reciente = max(archivos, key=lambda p: p.stat().st_mtime)
    # ¿Tiene <24h?
    edad_h = (time.time() - mas_reciente.stat().st_mtime) / 3600
    if edad_h > 48:
        _log(f"VERIFICADOS: archivo viejo ({edad_h:.0f}h), ignorando")
        return None
    try:
        with open(mas_reciente, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        _log(f"VERIFICADOS: error leyendo {mas_reciente}: {e}")
        return None


def _formatear_datos_verificados(datos: dict) -> str:
    """Convierte el JSON verificado en texto con marcas ✅/⚠️/❌."""
    if not datos:
        return ""
    estado = datos.get("estado_verificacion", "?")
    siniestro = datos.get("siniestro_final", "")
    diagnostico = datos.get("diagnostico_final", "")
    discrepancias = datos.get("_meta", {}).get("discrepancias", [])
    fecha = datos.get("_meta", {}).get("extraido_en", "")[:10]
    
    lines = [f"📊 DATOS VERIFICADOS (extraídos {fecha}):"]
    if estado == "verificado":
        lines.append(f"  ✅ Siniestro: {siniestro}")
    elif estado == "discrepancias":
        lines.append(f"  ❌ Siniestro: {siniestro} (discrepancia entre portales)")
        for d in discrepancias:
            lines.append(f"    → {d['campo']}: Medi={d.get('medifolios')} vs Pos={d.get('positiva')}")
    else:
        lines.append(f"  ⚠️ Siniestro: {siniestro} (estado: {estado})")
    
    if diagnostico:
        lines.append(f"  📋 Diagnóstico: {diagnostico}")
    return "\n".join(lines)
```

- [ ] **Step 4: Modificar `procesar_mensaje` para usar los datos verificados**

En `chat_handler.py`, función `procesar_mensaje`, después de detectar `cc` y antes de buscar archivos:

```python
    # NUEVO: cargar datos verificados pre-extraídos
    datos_verificados = None
    info_verificados = ""
    if cc and os.getenv("FASE_A_ENABLED", "false").lower() == "true":
        datos_verificados = _cargar_datos_verificados(cc)
        if datos_verificados:
            info_verificados = _formatear_datos_verificados(datos_verificados)
```

Y luego pasarlo al LLM. Modificar la llamada a `_llamar_llm` para incluir `info_verificados` en el contexto:

```python
    # 4. Llamar LLM con todo el contexto + datos verificados
    contexto_extra = info_verificados if info_verificados else ""
    respuesta = _llamar_llm(mensaje, cc, doc_content + "\n\n" + contexto_extra, workspace_files)
```

Y al final, si NO hay datos verificados pero SÍ hay CC, sugerir extracción:

```python
    # Si el usuario menciona una CC pero no hay datos verificados, sugerir extracción
    if cc and not datos_verificados and os.getenv("FASE_A_ENABLED", "false").lower() == "true":
        respuesta += (
            f"\n\n💡 Aún no tengo datos verificados de la CC {cc}. "
            f"¿Quiere que los busque ahora en Medifolios y Positiva? (~2 min). "
            f"Escribe 'verifica {cc}' para que arranque."
        )
```

- [ ] **Step 5: Ejecutar todos los tests del chat**

Run:
```bash
pytest tests/test_chat_integration.py -v
```

Expected: 3 PASS.

- [ ] **Step 6: Smoke test integral**

Run (con un JSON dummy en storage/data/):
```bash
mkdir -p storage/data
cat > storage/data/test-1193143688-completo.json <<'EOF'
{"cc": "1193143688", "siniestro_final": "503463870", "diagnostico_final": "S611",
 "estado_verificacion": "verificado",
 "_meta": {"extraido_en": "2026-05-19T21:00:00", "discrepancias": []}}
EOF
FASE_A_ENABLED=true python -c "
from backend.chat_handler import procesar_mensaje
r = procesar_mensaje('revisa al paciente 1193143688', paciente_cc='1193143688')
print(r['contenido'][:600])
"
rm storage/data/test-1193143688-completo.json
```

Expected: la respuesta menciona "503463870" y la marca ✅.

- [ ] **Step 7: Commit**

```bash
git add backend/chat_handler.py tests/test_chat_integration.py
git commit -m "💬 chat: carga datos verificados pre-extraídos + sugiere extracción"
```

---

## Task 12: Limpieza — eliminar `puente_docker.py` y marcar DEPRECATED

**Files:**
- Delete: `backend/puente_docker.py`
- Modify: `backend/extractor_medifolios.py` (banner)
- Modify: `backend/extractor_positiva.py` (banner)
- Modify: `backend/browser_session.py` (banner)
- Modify: `backend/server.py` (eliminar import roto)

- [ ] **Step 1: Verificar quién usaba `puente_docker`**

Run:
```bash
grep -r "puente_docker\|extraer_desde_wsl\|obtener_datos_verificados" --include="*.py" backend/ dashboard/ chat_bridge.py 2>/dev/null
```

Esperado: aparece solo en `server.py` (líneas 525-573, ya reemplazadas en Task 9).

- [ ] **Step 2: Eliminar puente_docker.py**

Run:
```bash
git rm backend/puente_docker.py
```

- [ ] **Step 3: Eliminar imports muertos en `server.py`**

En `backend/server.py`, eliminar cualquier `from backend.puente_docker import` restante. Buscar:
```bash
grep -n "puente_docker" backend/server.py
```
Y eliminar líneas. Si no queda nada, OK.

- [ ] **Step 4: Marcar `extractor_medifolios.py` como DEPRECATED**

En la línea 1 de `backend/extractor_medifolios.py`, insertar:

```python
"""
⚠️ DEPRECATED — referencia documental, no se ejecuta.

Este archivo fue diseñado como guía de pasos para un agente Claude Code
con browser tools (Hermes). La implementación real con Playwright vive en:
    backend/playwright_real/medifolios.py

Conservado por valor documental: los CAMPOS_PACIENTES y la estructura de
PasoExtraccion explican qué se busca en cada sección.
"""
```

- [ ] **Step 5: Idem para `extractor_positiva.py` y `browser_session.py`**

En cada archivo, insertar al inicio:

```python
"""
⚠️ DEPRECATED — referencia documental, no se ejecuta.

Implementación real en backend/playwright_real/
"""
```

- [ ] **Step 6: Sanity check — el servidor levanta sin errores**

Run:
```bash
cd /home/manu/Documentos/Temporal/auto-ma
uvicorn backend.server:app --port 8000 &
sleep 3
curl -s http://localhost:8000/api/health
pkill -f "uvicorn.*server:app"
```

Expected: `{"ok":true,"version":"1.0.0"}`

- [ ] **Step 7: Commit**

```bash
git add backend/server.py backend/extractor_medifolios.py backend/extractor_positiva.py backend/browser_session.py
git commit -m "🧹 deprecate: extractor_* y browser_session (vivo en playwright_real/)"
```

---

## Task 13: Tests end-to-end y suite completa

**Files:**
- Create: `tests/test_e2e.py`

- [ ] **Step 1: Test E2E del flujo de pre-extracción + chat**

`tests/test_e2e.py`:

```python
"""Tests end-to-end de Fase A."""
import sys
import json
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.live
@pytest.mark.asyncio
async def test_e2e_pre_extraccion_y_chat(tmp_path, monkeypatch):
    """
    1. Ejecuta extracción real de Juan Carlos.
    2. Verifica que el chat carga esos datos.
    3. Confirma que el OOM no aparece (memoria estable).
    """
    monkeypatch.setenv("FASE_A_ENABLED", "true")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Extracción
    from backend.playwright_real.orquestador import extraer_paciente_completo
    archivo = data_dir / "20260519-1193143688-completo.json"
    datos = await extraer_paciente_completo("1193143688", guardar_en=archivo)
    assert archivo.exists()
    assert datos["cc"] == "1193143688"
    
    # 2. Chat usa los datos
    from backend.chat_handler import procesar_mensaje
    resultado = procesar_mensaje(
        "revisa al paciente 1193143688",
        paciente_cc="1193143688",
    )
    contenido = resultado.get("contenido", "")
    # La respuesta debe incluir el siniestro o el estado verificado
    assert "1193143688" in contenido or "Juan" in contenido or datos.get("siniestro_final", "") in contenido
```

- [ ] **Step 2: Test OOM regresión**

```python
@pytest.mark.skipif(not os.environ.get("OPENCODE_GO_API_KEY"), reason="needs API key")
def test_e2e_oom_no_aparece_con_12_docs(tmp_path, monkeypatch):
    """12 docs procesados secuencialmente → memoria del padre estable."""
    import psutil, os
    from docx import Document
    monkeypatch.setenv("FASE_A_ENABLED", "true")
    
    archivos = []
    for i in range(12):
        p = tmp_path / f"doc{i}.docx"
        doc = Document()
        for j in range(40):
            doc.add_paragraph(f"Línea {j} del documento {i} con texto razonable.")
        doc.save(str(p))
        archivos.append((p, p.stat().st_size // 1024, "01/01/2026"))
    
    proc = psutil.Process(os.getpid())
    mem_inicial = proc.memory_info().rss / 1024 / 1024
    
    from backend.chat_handler import _procesar_via_workers
    resultado = _procesar_via_workers(archivos, cc="1193143688")
    
    mem_final = proc.memory_info().rss / 1024 / 1024
    delta = mem_final - mem_inicial
    
    assert isinstance(resultado, str)
    assert delta < 100, f"Memoria creció {delta:.1f}MB tras 12 docs"
```

- [ ] **Step 3: Ejecutar suite completa**

Run:
```bash
pytest tests/ -v --tb=short
```

Expected: todos los tests pasan o skippean apropiadamente. Sin failures.

- [ ] **Step 4: Ejecutar suite live (manual, con credenciales)**

Run:
```bash
pytest tests/ -v --live --tb=short
```

Expected: tests live pasan contra portales reales.

- [ ] **Step 5: Commit**

```bash
git add tests/test_e2e.py
git commit -m "✅ tests: suite e2e completa Fase A (extracción + chat + OOM)"
```

---

## Task 14: Rollout en WSL + smoke test con Sandra (manual)

**Files:**
- (sin cambios de código — pasos operativos)

- [ ] **Step 1: Pull en WSL**

```bash
ssh manu@wsl-rilo  # o conectarse al WSL local
cd ~/rilo-backend
git pull origin main
```

- [ ] **Step 2: Instalar dependencias**

```bash
pip install -r backend/requirements.txt
playwright install chromium
mkdir -p storage/playwright_sessions storage/screenshots
```

- [ ] **Step 3: Configurar `.env` en WSL**

Editar `~/rilo-backend/.env`:
```bash
FASE_A_ENABLED=false       # arrancar apagado
FASE_A_CRON_ENABLED=false  # arrancar apagado
LLM_MODEL_EXTRACCION=deepseek-chat
LLM_MODEL_SINTESIS=deepseek-v4-pro
PLAYWRIGHT_DEBUG=false
CRON_HORA_NOCHE=21
CRON_COOLDOWN_PACIENTES_S=30
```

- [ ] **Step 4: Restart FastAPI**

```bash
pkill -f "uvicorn.*server:app" || true
nohup uvicorn backend.server:app --host 0.0.0.0 --port 8000 > /tmp/rilo.log 2>&1 &
sleep 3
tail -50 /tmp/rilo.log
curl -s http://localhost:8000/api/health
```

Expected: `{"ok":true,"version":"1.0.0"}`

- [ ] **Step 5: Smoke en sombra — extracción manual de Juan**

```bash
FASE_A_ENABLED=true python -c "
import asyncio
from backend.playwright_real.orquestador import extraer_paciente_completo
from pathlib import Path
datos = asyncio.run(extraer_paciente_completo('1193143688', guardar_en=Path('storage/data/test.json')))
print('Estado:', datos.get('estado_verificacion'))
print('Siniestro:', datos.get('siniestro_final'))
print('Discrepancias:', len(datos.get('_meta',{}).get('discrepancias',[])))
"
```

Expected: imprime estado_verificacion y siniestro. Sin tracebacks.

- [ ] **Step 6: Activar Fase A completa**

Editar `.env`:
```bash
FASE_A_ENABLED=true
FASE_A_CRON_ENABLED=true
```

Reiniciar FastAPI:
```bash
pkill -f "uvicorn.*server:app"
nohup uvicorn backend.server:app --host 0.0.0.0 --port 8000 > /tmp/rilo.log 2>&1 &
sleep 3
curl -s http://localhost:8000/api/cron/estado
```

Expected: `{"ok": true, "scheduler_running": true, "proximo_run": "..."}`

- [ ] **Step 7: Esperar al cron de la noche (o disparar manual)**

```bash
curl -X POST http://localhost:8000/api/cron/disparar-ahora
```

Expected: respuesta con resumen de extracción + Telegram a Sandra.

- [ ] **Step 8: Sandra usa el chat al día siguiente**

Sandra abre dashboard `http://localhost:3000/chat`, escribe:
```
revisa al paciente Juan Carlos
```

Expected: respuesta en <60s que incluye datos verificados con marcas ✅/⚠️/❌.

- [ ] **Step 9: Monitoreo 1 semana**

Cada noche, revisar `tail -100 /tmp/rilo.log` para:
- Cron disparó OK
- Telegram llegó
- JSONs creados en `storage/data/`
- Memoria de FastAPI estable: `ps aux | grep uvicorn | awk '{print $6/1024 " MB"}'`

- [ ] **Step 10: Rollback plan (en caso de problema)**

Si algo falla en producción:
```bash
sed -i 's/FASE_A_ENABLED=true/FASE_A_ENABLED=false/' ~/rilo-backend/.env
sed -i 's/FASE_A_CRON_ENABLED=true/FASE_A_CRON_ENABLED=false/' ~/rilo-backend/.env
pkill -f "uvicorn.*server:app"
nohup uvicorn backend.server:app --host 0.0.0.0 --port 8000 > /tmp/rilo.log 2>&1 &
```

Vuelve al comportamiento legacy. Sandra no nota nada. JSONs ya extraídos permanecen en disco.

- [ ] **Step 11: Tag y commit del rollout**

```bash
cd ~/rilo-backend
git tag fase-a-v1.0
git push --tags
echo "Fase A activada en producción $(date)" >> CHANGELOG.md
git add CHANGELOG.md
git commit -m "🚀 Fase A: rollout completo en producción WSL"
```

---

## Self-Review (after writing this plan)

**1. Spec coverage check:** ✅ Repasados:
- Sec 2.1 OOM → Tasks 2, 3, 13 (worker + integración + test memoria)
- Sec 2.2 Portales sin implementar → Tasks 4-8 (Playwright completo)
- Sec 2.3 Flujo día listo → Task 10 (cron) + Task 11 (chat con verificados)
- Sec 5.1 lote_worker → Task 2
- Sec 5.2 playwright_real/ → Tasks 4-8
- Sec 5.3 cron_pre_extraccion → Task 10
- Sec 5.4 chat_handler v10 → Tasks 3, 11
- Sec 5.5 Endpoints FastAPI → Task 9
- Sec 5.6 requirements → Task 1
- Sec 5.7 Variables entorno → Task 1
- Sec 6 Optimización tokens → Tasks 2, 3 (modelo_extraccion vs modelo_sintesis)
- Sec 7 Errores → Tasks 5-7 (try/except + fallbacks), Task 10 (cron resiliente)
- Sec 8 Testing → Tasks 2, 5, 6, 7, 8, 10, 11, 13
- Sec 9 Rollout → Task 14
- Sec 11 Riesgos → mitigaciones en Tasks 5 (re-auth), 10 (Telegram avisos), 14 (feature flag)

**2. Placeholders:** Sin TBDs/TODOs/"fill in". Cada step tiene código real.

**3. Consistencia tipos:** `extraer_paciente_completo()` aparece con misma firma en Tasks 8, 9, 10, 13, 14. `_procesar_via_workers` aparece consistente en Tasks 3 y 13. Variables `FASE_A_ENABLED` y `FASE_A_CRON_ENABLED` consistentes en todas las tasks. `LLM_MODEL_EXTRACCION` / `LLM_MODEL_SINTESIS` consistentes.

Plan listo.

---

## Appendix B — Diferencias plan vs implementación real

| Item | Plan | Implementación | Decisión |
|------|------|----------------|----------|
| Modelo extracción | `deepseek-chat` | `deepseek-v4-flash` | OpenCode Go no tiene `deepseek-chat`. `deepseek-v4-flash` es el equivalente sin razonamiento. |
| `lote_worker.py` salida JSON | `datos` con campos estructurados | `datos_raw` con texto plano | El LLM devuelve texto plano en vez de JSON estructurado. Se mantiene `datos_raw` para no forzar parsing que puede fallar. |
| `/api/portales/health` | Heartbeat real (login + carga 1 página) | State check simple (storage_state existe + creds configuradas) | Un heartbeat real abriría navegador cada request. El state check es seguro y rápido. Si se necesita probar, usar test live. |
| `/api/verificar/{cc}/extraer` (POST) | Reemplazado por `extraer-ahora` | Ruta vieja eliminada con `puente_docker.py` | Coherente con eliminación del módulo puente. |
| `fusionador.py` integración discrepancias | `_meta.discrepancias` desde orquestador | Lee `_meta.discrepancias` de ambos fuentes y las consolida en `_metadata.discrepancias_portales` | Más robusto: mergea discrepancias de ambos lados. |
| `_formatear_datos_verificados` | `siniestro_final` del plan | Usa `datos["medifolios"]["siniestro_medi"]` y `datos["positiva"]["siniestros"][0]["id"]` | Estructura real del JSON de orquestador, no la especulación del spec. |

**Aceptado como nuevo baseline.** El spec original era un diseño inicial; la implementación reveló ajustes necesarios (modelos reales, estructura JSON real, performance). No vale la pena alinear artificialmente — el código funciona contra APIs/portales reales.
