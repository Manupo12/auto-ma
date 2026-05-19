# Tomy Completo — Plan de Implementación (ejecutable por OpenCode)

> **Para el agente ejecutor:** Este plan se ejecuta task por task. Cada step tiene código completo y comandos exactos. Marca cada paso con `[x]` al completarlo. Usa TDD: escribir test → fallar → implementar → pasar → commit. Lee la spec antes de empezar: `docs/superpowers/specs/2026-05-19-tomy-completo-design.md`.

**Goal:** Que Sandra solo grabe audio y revise resultado final. Tomy hace el resto (transcripción + cruce + generación + QA + PDF + notificación) en 10-20 min. Más: organizar formatos crudos, casos alternos, dashboard boomer-proof, producción endurecida.

**Spec:** `docs/superpowers/specs/2026-05-19-tomy-completo-design.md`
**Continuación de:** Fase A completada en commit `7ead22a` (pipeline IA estabilizado + Playwright real + cron pre-extracción).

**Tech Stack:** Python 3.12 + FastAPI + APScheduler + Playwright + Next.js 14 + Tailwind + DeepSeek v4 (OpenCode Go) + Deepgram nova-2 + LibreOffice headless (PDF) + SQLite.

---

## Convenciones para el ejecutor

- **Working dir:** `/home/manu/Documentos/Temporal/auto-ma` (o equivalente).
- **Python:** `python3` (no `python`).
- **Tests:** `pytest tests/ -v --tb=short`. Tests live: `pytest tests/ -v --live --tb=short`.
- **Commits:** uno por task completa. Formato: `<emoji> <área>: <verbo descripción>`. Ejemplos: `🔧 workflow_runner: pipeline 9 pasos end-to-end`, `🎨 dashboard: vista paciente 360 boomer-friendly`.
- **NO push** a `origin/main` sin que el usuario lo pida.
- **Feature flag:** Todo cambio nuevo se activa con env var `TOMY_COMPLETO_ENABLED=true`. Default `false`.
- **Logs:** estilo `_log(msg)` con prefijo del módulo + timestamp. Stderr, no stdout.
- **No tocar:** `doc_generator.py`, `custody.py`, `json_validator.py` core — solo agregar wrappers si hace falta.

---

## File structure (lo nuevo)

```
backend/
├── workflow_runner.py              [NEW] ~250 líneas. Orquestador 9 pasos.
├── task_db.py                      [NEW] ~150 líneas. SQLite para workflow_tasks.
├── workflow_steps/                 [NEW]
│   ├── __init__.py
│   ├── transcribir.py              [NEW] ~120 líneas. Deepgram + chunks ffmpeg si >30min.
│   ├── resolver_paciente.py        [NEW] ~80 líneas. JSON pre-extraído o Playwright.
│   ├── leer_notas_crudas.py        [NEW] ~60 líneas. Escanea workspace por CC.
│   ├── leer_formatos_subidos.py    [NEW] ~70 líneas. DOCX subidos como referencia.
│   ├── sintetizar_maestro.py       [NEW] ~150 líneas. LLM razonador con chunking.
│   ├── generar_formatos.py         [NEW] ~120 líneas. Wrapper sobre doc_generator.
│   ├── qa_formatos.py              [NEW] ~80 líneas. Wrapper sobre verificar-documento.
│   ├── convertir_pdf.py            [NEW] ~60 líneas. LibreOffice → PDF/A.
│   └── notificar_listo.py          [NEW] ~50 líneas. Mensaje Telegram final.
├── organizador_formato.py          [NEW] ~180 líneas. Organiza DOCX crudo.
├── correction_resolver.py          [NEW] ~140 líneas. Interpreta corrección.
├── aplicador_correccion.py         [NEW] ~120 líneas. Actualiza JSON + regen.
├── auth_simple.py                  [NEW] ~100 líneas. PIN + cookie HMAC.
├── backup_diario.py                [NEW] ~80 líneas. Cron 23:00 → Telegram.
├── costos_tracker.py               [NEW] ~80 líneas. Tokens diarios.
├── server.py                       [MOD] +12 endpoints nuevos.
├── chat_handler.py                 [MOD] integrar correction_resolver.
└── cron_pre_extraccion.py          [MOD] agregar job backup_diario.

dashboard/
├── app/
│   ├── hoy/page.tsx                [NEW] ~200 líneas. Vista "Mi Día".
│   ├── paciente/[cc]/page.tsx      [NEW] ~300 líneas. Vista 360.
│   ├── subir-audio/page.tsx        [MOD] simplificar UX (drag-and-drop grande).
│   ├── chat/page.tsx               [MOD] contexto paciente activo.
│   └── layout.tsx                  [MOD] tipografía boomer (text-lg base).
├── components/
│   ├── TimelinePaciente.tsx        [NEW] ~120 líneas. Pasos visuales.
│   ├── FormatoCard.tsx             [NEW] ~150 líneas. Card grande con preview.
│   ├── BotonGigante.tsx            [NEW] ~50 líneas. Botón principal.
│   ├── EstadoVisual.tsx            [NEW] ~70 líneas. Semáforo grande.
│   └── Sidebar.tsx                 [MOD] iconos más grandes, sin jerga.
└── lib/
    ├── workflow.ts                 [NEW] ~80 líneas. Cliente API workflow.
    └── auth.ts                     [NEW] ~50 líneas. PIN + sesión.

tests/
├── test_workflow_runner.py         [NEW]
├── test_task_db.py                 [NEW]
├── test_workflow_steps/            [NEW] (uno por step)
├── test_organizador_formato.py     [NEW]
├── test_correction_resolver.py     [NEW]
├── test_auth_simple.py             [NEW]
└── test_dashboard_e2e.py           [NEW] (Playwright contra dashboard).

storage/
├── workflow.db                     [NEW] SQLite (gitignored).
├── audit.log                       [NEW] (gitignored).
└── audios_temp/                    [NEW] chunks ffmpeg (gitignored).

.env                                [MOD] +TOMY_COMPLETO_ENABLED, +AUTH_PIN, +BACKUP_*
```

---

# PARTE 1: Setup + Persistencia (Tasks 1-2)

## Task 1: Dependencias nuevas + feature flag + estructura

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `.env`, `.env.example`
- Modify: `.gitignore`
- Create: `backend/workflow_steps/__init__.py`
- Create: `tests/test_workflow_steps/__init__.py`

- [ ] **Step 1: Agregar dependencias a `backend/requirements.txt`**

Append:

```text
sqlalchemy>=2.0.25
pydub>=0.25.1
itsdangerous>=2.1.2
psutil>=5.9.0
```

Install:
```bash
pip install -r backend/requirements.txt
# Si LibreOffice no está instalado en WSL:
which libreoffice || sudo apt-get install -y libreoffice
# Si ffmpeg no está instalado:
which ffmpeg || sudo apt-get install -y ffmpeg
```

- [ ] **Step 2: Agregar variables a `.env`**

Append:

```bash
# --- Tomy Completo ---
TOMY_COMPLETO_ENABLED=false
WORKFLOW_DB_PATH=./storage/workflow.db
WORKFLOW_TIMEOUT_TOTAL_S=1800     # 30 min máximo
AUDIO_CHUNK_DURATION_S=1500       # chunks de 25 min
AUDIO_TEMP_DIR=./storage/audios_temp

# --- Auth ---
AUTH_PIN=1234                     # cambiar en producción
AUTH_SECRET=cambiar-este-secret-en-prod

# --- Backup ---
BACKUP_HORA=23
BACKUP_DESTINO=./storage/backups
```

Mismo en `.env.example` (sin valores reales).

- [ ] **Step 3: Actualizar `.gitignore`**

Append:

```text
storage/workflow.db
storage/workflow.db-journal
storage/audit.log
storage/audios_temp/
storage/backups/
```

- [ ] **Step 4: Crear directorios + `__init__.py` vacíos**

```bash
mkdir -p backend/workflow_steps tests/test_workflow_steps storage/audios_temp storage/backups
touch backend/workflow_steps/__init__.py tests/test_workflow_steps/__init__.py
```

- [ ] **Step 5: Sanity check**

```bash
cd /home/manu/Documentos/Temporal/auto-ma
python3 -c "import sqlalchemy, pydub, itsdangerous; print('deps OK')"
python3 -c "from backend import server; print('server OK')"
```

Expected: `deps OK` y `server OK`.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/workflow_steps/ tests/test_workflow_steps/ .env .env.example .gitignore
git commit -m "🔧 Tomy Completo: deps + feature flag + estructura"
```

---

## Task 2: `task_db.py` — persistencia SQLite (TDD)

**Files:**
- Create: `backend/task_db.py`
- Create: `tests/test_task_db.py`

- [ ] **Step 1: Test que falla — crear y leer task**

`tests/test_task_db.py`:

```python
"""Tests para task_db.py — SQLite workflow_tasks."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_workflow.db"


def test_crear_task(db_path):
    from backend.task_db import TaskDB
    db = TaskDB(str(db_path))
    task_id = db.crear_task(paciente_cc="1193143688", audio_path="/tmp/audio.m4a")
    assert task_id
    task = db.obtener_task(task_id)
    assert task["paciente_cc"] == "1193143688"
    assert task["estado"] == "pendiente"
    assert task["paso_actual"] == 0
    assert task["audio_path"] == "/tmp/audio.m4a"


def test_actualizar_paso(db_path):
    from backend.task_db import TaskDB
    db = TaskDB(str(db_path))
    task_id = db.crear_task(paciente_cc="123", audio_path="/tmp/a.m4a")
    db.actualizar_paso(task_id, paso=3, estado="transcribiendo")
    task = db.obtener_task(task_id)
    assert task["paso_actual"] == 3
    assert task["estado"] == "transcribiendo"


def test_marcar_error(db_path):
    from backend.task_db import TaskDB
    db = TaskDB(str(db_path))
    task_id = db.crear_task(paciente_cc="123", audio_path="/tmp/a.m4a")
    db.marcar_error(task_id, paso=5, error="Timeout en LLM")
    task = db.obtener_task(task_id)
    assert task["estado"] == "error_en_paso_5"
    assert "Timeout" in task["error"]


def test_listar_tasks_paciente(db_path):
    from backend.task_db import TaskDB
    db = TaskDB(str(db_path))
    db.crear_task(paciente_cc="123", audio_path="/a.m4a")
    db.crear_task(paciente_cc="123", audio_path="/b.m4a")
    db.crear_task(paciente_cc="456", audio_path="/c.m4a")
    tasks = db.listar_tasks_paciente("123")
    assert len(tasks) == 2


def test_guardar_resultado(db_path):
    from backend.task_db import TaskDB
    db = TaskDB(str(db_path))
    task_id = db.crear_task(paciente_cc="123", audio_path="/a.m4a")
    db.guardar_resultado(task_id, {"formatos": ["analisis.docx", "voi.docx"], "qa_warnings": 1})
    task = db.obtener_task(task_id)
    assert task["resultado"]["formatos"] == ["analisis.docx", "voi.docx"]
```

- [ ] **Step 2: Ejecutar test — debe fallar (módulo no existe)**

```bash
pytest tests/test_task_db.py -v
```

Expected: FAIL con ModuleNotFoundError.

- [ ] **Step 3: Implementar `backend/task_db.py`**

```python
"""
Persistencia SQLite para workflow_tasks.

Schema:
  id INTEGER PRIMARY KEY
  task_id TEXT UNIQUE              -- ej: "abc12345"
  paciente_cc TEXT NOT NULL
  audio_path TEXT
  estado TEXT NOT NULL             -- pendiente, transcribiendo, ..., listo, error_en_paso_N
  paso_actual INTEGER              -- 0..9
  iniciado_en TIMESTAMP
  terminado_en TIMESTAMP
  error TEXT
  resultado TEXT                   -- JSON serializado
"""
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT UNIQUE NOT NULL,
    paciente_cc TEXT NOT NULL,
    audio_path TEXT,
    estado TEXT NOT NULL DEFAULT 'pendiente',
    paso_actual INTEGER DEFAULT 0,
    iniciado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    terminado_en TIMESTAMP,
    error TEXT,
    resultado TEXT
);

CREATE INDEX IF NOT EXISTS idx_paciente ON workflow_tasks(paciente_cc);
CREATE INDEX IF NOT EXISTS idx_estado ON workflow_tasks(estado);
"""


class TaskDB:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(SCHEMA)

    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def crear_task(self, paciente_cc: str, audio_path: str) -> str:
        task_id = uuid.uuid4().hex[:12]
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO workflow_tasks (task_id, paciente_cc, audio_path) VALUES (?, ?, ?)",
                (task_id, paciente_cc, audio_path),
            )
        return task_id

    def obtener_task(self, task_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        if data.get("resultado"):
            try:
                data["resultado"] = json.loads(data["resultado"])
            except Exception:
                pass
        return data

    def actualizar_paso(self, task_id: str, paso: int, estado: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE workflow_tasks SET paso_actual = ?, estado = ? WHERE task_id = ?",
                (paso, estado, task_id),
            )

    def marcar_error(self, task_id: str, paso: int, error: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE workflow_tasks SET estado = ?, error = ?, terminado_en = ? WHERE task_id = ?",
                (f"error_en_paso_{paso}", error[:1000], datetime.now().isoformat(), task_id),
            )

    def guardar_resultado(self, task_id: str, resultado: dict, estado: str = "listo"):
        with self._conn() as conn:
            conn.execute(
                "UPDATE workflow_tasks SET estado = ?, resultado = ?, terminado_en = ? WHERE task_id = ?",
                (estado, json.dumps(resultado, ensure_ascii=False), datetime.now().isoformat(), task_id),
            )

    def listar_tasks_paciente(self, paciente_cc: str, limit: int = 20) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM workflow_tasks WHERE paciente_cc = ? ORDER BY iniciado_en DESC LIMIT ?",
                (paciente_cc, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def listar_activos(self) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM workflow_tasks WHERE estado NOT IN ('listo','cancelado') AND estado NOT LIKE 'error_%' ORDER BY iniciado_en DESC",
            ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Tests pasan**

```bash
pytest tests/test_task_db.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/task_db.py tests/test_task_db.py
git commit -m "💾 task_db: SQLite para workflow_tasks (CRUD + queries)"
```

---

# PARTE 2: Workflow Steps individuales (Tasks 3-10)

## Task 3: `workflow_steps/transcribir.py` — Deepgram + chunks ffmpeg

**Files:**
- Create: `backend/workflow_steps/transcribir.py`
- Create: `tests/test_workflow_steps/test_transcribir.py`

- [ ] **Step 1: Test que falla — chunking de audio >30min**

`tests/test_workflow_steps/test_transcribir.py`:

```python
"""Tests para transcribir.py."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_calcular_duracion_devuelve_segundos(tmp_path):
    """Audio dummy: devuelve duración en segundos."""
    from backend.workflow_steps.transcribir import _calcular_duracion_s
    # Mock: para un .wav existente devuelve duración
    fake = tmp_path / "fake.wav"
    fake.write_bytes(b"RIFF" + b"\x00" * 100)
    with patch("backend.workflow_steps.transcribir.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="3600.5\n")
        dur = _calcular_duracion_s(fake)
    assert dur == 3600.5


def test_decide_chunks_si_audio_largo(tmp_path, monkeypatch):
    """Si audio > 30 min, debe planificar chunking."""
    from backend.workflow_steps.transcribir import _necesita_chunking
    monkeypatch.setenv("AUDIO_CHUNK_DURATION_S", "1500")
    assert _necesita_chunking(1400.0) is False  # 23 min: no chunking
    assert _necesita_chunking(2000.0) is True   # 33 min: sí chunking


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="needs ffmpeg")
def test_dividir_audio_en_chunks(tmp_path):
    """Audio de 60s se divide en chunks de 25s → 3 chunks."""
    import subprocess
    audio = tmp_path / "input.wav"
    # Generar audio sintético de 60s
    subprocess.run([
        "ffmpeg", "-f", "lavfi", "-i", "sine=frequency=440:duration=60",
        "-ar", "16000", str(audio), "-y"
    ], capture_output=True, check=True)
    
    from backend.workflow_steps.transcribir import _dividir_en_chunks
    chunks = _dividir_en_chunks(audio, chunk_dur_s=25, output_dir=tmp_path)
    assert len(chunks) == 3
    assert all(c.exists() for c in chunks)
```

- [ ] **Step 2: Test debe fallar (módulo no existe)**

```bash
pytest tests/test_workflow_steps/test_transcribir.py -v
```

Expected: FAIL ModuleNotFoundError.

- [ ] **Step 3: Implementar `backend/workflow_steps/transcribir.py`**

```python
"""
Paso 1 del workflow: transcribir audio con Deepgram nova-2.

Si el audio dura >30 min, se divide en chunks de 25 min con ffmpeg
y cada chunk se transcribe por separado. Resultados se concatenan
manteniendo timestamps relativos.
"""
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict


def _log(msg: str):
    print(f"[TRANSCRIBIR {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _calcular_duracion_s(audio_path: Path) -> float:
    """Devuelve duración en segundos usando ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True, timeout=30,
    )
    return float(result.stdout.strip())


def _necesita_chunking(duracion_s: float) -> bool:
    chunk_dur = int(os.getenv("AUDIO_CHUNK_DURATION_S", "1500"))
    return duracion_s > chunk_dur


def _dividir_en_chunks(audio_path: Path, chunk_dur_s: int, output_dir: Path) -> List[Path]:
    """Divide audio en chunks .wav de chunk_dur_s segundos. Retorna lista ordenada."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = output_dir / f"{audio_path.stem}_chunk_%03d.wav"
    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-f", "segment", "-segment_time", str(chunk_dur_s),
        "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1",
        "-loglevel", "error",
        str(output_pattern), "-y"
    ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=600)
    chunks = sorted(output_dir.glob(f"{audio_path.stem}_chunk_*.wav"))
    return chunks


def transcribir_audio_largo(audio_path: str, paciente_cc: str) -> Dict:
    """
    Transcribe audio. Si dura más de AUDIO_CHUNK_DURATION_S, chunkea con ffmpeg.
    Retorna dict {texto, segmentos, duracion, confianza_global, chunks_procesados, warnings}.
    """
    from backend.flujo_audio import transcribir_audio
    
    audio = Path(audio_path)
    if not audio.exists():
        raise FileNotFoundError(f"Audio no existe: {audio_path}")
    
    duracion = _calcular_duracion_s(audio)
    _log(f"Audio: {audio.name} ({duracion:.0f}s = {duracion/60:.1f} min)")
    
    warnings = []
    if not _necesita_chunking(duracion):
        _log("Sin chunking — un solo Deepgram")
        resultado = transcribir_audio(str(audio))
        confianza = resultado.get("confianza", 0)
        if confianza < 0.6:
            warnings.append(f"Confianza baja del audio: {confianza:.2f}")
        return {
            "texto": resultado["texto"],
            "segmentos": resultado["segmentos"],
            "duracion": duracion,
            "confianza_global": confianza,
            "chunks_procesados": 1,
            "warnings": warnings,
        }
    
    # Chunking
    chunk_dur = int(os.getenv("AUDIO_CHUNK_DURATION_S", "1500"))
    temp_dir = Path(os.getenv("AUDIO_TEMP_DIR", "./storage/audios_temp")) / paciente_cc
    chunks = _dividir_en_chunks(audio, chunk_dur, temp_dir)
    _log(f"Chunks: {len(chunks)} de {chunk_dur}s c/u")
    
    textos = []
    segmentos_global = []
    confianzas = []
    offset = 0.0
    
    for i, chunk_path in enumerate(chunks):
        _log(f"Chunk {i+1}/{len(chunks)}: {chunk_path.name}")
        try:
            r = transcribir_audio(str(chunk_path))
            textos.append(r["texto"])
            confianzas.append(r.get("confianza", 0))
            # Ajustar timestamps de segmentos al offset global
            for seg in r["segmentos"]:
                segmentos_global.append({
                    **seg,
                    "inicio": seg["inicio"] + offset,
                    "fin": seg["fin"] + offset,
                })
            offset += r.get("duracion", chunk_dur)
        except Exception as e:
            _log(f"Chunk {i+1} falló: {e}")
            warnings.append(f"Chunk {i+1} no se pudo transcribir: {e}")
    
    # Limpiar chunks temporales
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass
    
    confianza_global = sum(confianzas) / len(confianzas) if confianzas else 0
    if confianza_global < 0.6:
        warnings.append(f"Confianza global baja: {confianza_global:.2f}")
    
    return {
        "texto": "\n".join(textos),
        "segmentos": segmentos_global,
        "duracion": duracion,
        "confianza_global": confianza_global,
        "chunks_procesados": len(chunks),
        "warnings": warnings,
    }


def ejecutar(audio_path: str, paciente_cc: str) -> Dict:
    """Punto de entrada para workflow_runner."""
    return transcribir_audio_largo(audio_path, paciente_cc)
```

- [ ] **Step 4: Tests pasan**

```bash
pytest tests/test_workflow_steps/test_transcribir.py -v
```

Expected: 3 PASS (o 2 si no hay ffmpeg).

- [ ] **Step 5: Commit**

```bash
git add backend/workflow_steps/transcribir.py tests/test_workflow_steps/test_transcribir.py
git commit -m "🎙️ workflow_steps: transcribir con Deepgram + chunks ffmpeg para audios largos"
```

---

## Task 4: `workflow_steps/resolver_paciente.py` — JSON pre-extraído o Playwright

**Files:**
- Create: `backend/workflow_steps/resolver_paciente.py`
- Create: `tests/test_workflow_steps/test_resolver_paciente.py`

- [ ] **Step 1: Test que falla**

`tests/test_workflow_steps/test_resolver_paciente.py`:

```python
"""Tests para resolver_paciente.py."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_resolver_usa_json_existente(tmp_path, monkeypatch):
    """Si existe storage/data/{cc}-completo.json, lo carga sin Playwright."""
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    json_path = data_dir / "1193143688-completo.json"
    json_path.write_text(json.dumps({"cc": "1193143688", "_meta": {}}), encoding="utf-8")

    from backend.workflow_steps.resolver_paciente import resolver_paciente
    datos, fuente = resolver_paciente("1193143688", forzar_extraer=False)
    assert datos["cc"] == "1193143688"
    assert fuente == "cache"


def test_resolver_dispara_extraccion_si_no_existe(tmp_path, monkeypatch):
    """Si no existe JSON, llama a playwright_real.orquestador."""
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("FASE_A_ENABLED", "true")
    
    with patch("backend.playwright_real.orquestador.extraer_paciente_completo", new_callable=AsyncMock) as mock_extraer:
        mock_extraer.return_value = {"cc": "1193143688", "_meta": {"extraido_en": "now"}}
        from backend.workflow_steps.resolver_paciente import resolver_paciente
        datos, fuente = resolver_paciente("1193143688")
    
    assert mock_extraer.called
    assert fuente == "extraido_al_vuelo"


def test_resolver_devuelve_vacio_si_fase_a_desactivada(tmp_path, monkeypatch):
    """Sin Fase A: devuelve dict vacío con marca."""
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("FASE_A_ENABLED", "false")
    
    from backend.workflow_steps.resolver_paciente import resolver_paciente
    datos, fuente = resolver_paciente("9999")
    assert datos.get("error") or datos.get("_vacio")
    assert fuente == "sin_datos"
```

- [ ] **Step 2: Test debe fallar**

```bash
pytest tests/test_workflow_steps/test_resolver_paciente.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implementar**

```python
"""
Paso 2: Resolver datos del paciente.

1. Si existe JSON pre-extraído reciente (<48h) → usarlo.
2. Si no existe y FASE_A_ENABLED → disparar Playwright en vivo.
3. Si no existe y Fase A desactivada → devolver vacío con marca.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Tuple


def _log(msg: str):
    print(f"[RESOLVER {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _json_path(cc: str) -> Path:
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    matches = sorted((storage / "data").glob(f"*{cc}*completo.json"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _es_reciente(path: Path, horas_max: int = 48) -> bool:
    if not path or not path.exists():
        return False
    edad_h = (time.time() - path.stat().st_mtime) / 3600
    return edad_h < horas_max


def resolver_paciente(cc: str, forzar_extraer: bool = False) -> Tuple[dict, str]:
    """Retorna (datos_dict, fuente: 'cache'|'extraido_al_vuelo'|'sin_datos')."""
    if not forzar_extraer:
        path = _json_path(cc)
        if _es_reciente(path):
            _log(f"CC {cc}: usando cache ({path.name})")
            with open(path, encoding="utf-8") as f:
                return json.load(f), "cache"
    
    if os.getenv("FASE_A_ENABLED", "false").lower() != "true":
        _log(f"CC {cc}: Fase A desactivada, sin datos verificados")
        return {"cc": cc, "_vacio": True, "razon": "FASE_A_ENABLED=false"}, "sin_datos"
    
    _log(f"CC {cc}: extrayendo al vuelo con Playwright")
    try:
        from backend.playwright_real.orquestador import extraer_paciente_completo
        datos = asyncio.run(extraer_paciente_completo(cc, guardar=True))
        return datos, "extraido_al_vuelo"
    except Exception as e:
        _log(f"CC {cc}: error en extracción - {e}")
        return {"cc": cc, "_vacio": True, "error": str(e)}, "sin_datos"


def ejecutar(paciente_cc: str, forzar_extraer: bool = False) -> dict:
    """Punto de entrada para workflow_runner."""
    datos, fuente = resolver_paciente(paciente_cc, forzar_extraer)
    return {"datos_portales": datos, "fuente": fuente}
```

- [ ] **Step 4: Tests pasan**

```bash
pytest tests/test_workflow_steps/test_resolver_paciente.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/workflow_steps/resolver_paciente.py tests/test_workflow_steps/test_resolver_paciente.py
git commit -m "👤 workflow_steps: resolver_paciente (cache JSON o Playwright al vuelo)"
```

---

## Task 5: `workflow_steps/leer_notas_crudas.py`

**Files:**
- Create: `backend/workflow_steps/leer_notas_crudas.py`
- Create: `tests/test_workflow_steps/test_leer_notas_crudas.py`

- [ ] **Step 1: Test**

```python
"""Tests para leer_notas_crudas.py."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_lee_notas_de_workspace_por_cc(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    # Crear notas con el CC en el nombre
    (workspace / "notas_1193143688.txt").write_text("Paciente dice que le duele el hombro", encoding="utf-8")
    (workspace / "consulta_juan_1193143688.txt").write_text("Síntoma adicional: rigidez matutina", encoding="utf-8")
    (workspace / "otro_paciente.txt").write_text("No debería aparecer", encoding="utf-8")
    
    monkeypatch.setenv("WORKSPACE_DIR", str(workspace))
    from backend.workflow_steps.leer_notas_crudas import leer_notas_crudas
    
    notas = leer_notas_crudas("1193143688")
    assert len(notas) == 2
    assert "duele el hombro" in " ".join(n["contenido"] for n in notas)
    assert "rigidez matutina" in " ".join(n["contenido"] for n in notas)


def test_devuelve_vacio_si_no_hay_notas(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("WORKSPACE_DIR", str(workspace))
    from backend.workflow_steps.leer_notas_crudas import leer_notas_crudas
    notas = leer_notas_crudas("9999")
    assert notas == []
```

- [ ] **Step 2: Test debe fallar**

```bash
pytest tests/test_workflow_steps/test_leer_notas_crudas.py -v
```

- [ ] **Step 3: Implementar**

```python
"""
Paso 3: Leer notas crudas que Sandra escribió en su workspace.

Busca archivos .txt, .md, .docx que contengan la CC del paciente en el
nombre o en su contenido (primeros 500 chars). Devuelve hasta 5 archivos
con contenido (~2000 chars c/u).
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict


def _log(msg: str):
    print(f"[NOTAS {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _leer_texto(path: Path, max_chars: int = 2000) -> str:
    """Lee primeros N chars de .txt/.md/.docx."""
    try:
        if path.suffix.lower() in (".txt", ".md"):
            return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        if path.suffix.lower() == ".docx":
            from docx import Document
            doc = Document(str(path))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return text[:max_chars]
    except Exception as e:
        _log(f"Error leyendo {path.name}: {e}")
    return ""


def leer_notas_crudas(cc: str, max_archivos: int = 5) -> List[Dict]:
    """Busca archivos del workspace con el CC en nombre o contenido."""
    workspace = Path(os.getenv("WORKSPACE_DIR", str(Path.home() / "rilo-workspace")))
    if not workspace.exists():
        _log(f"Workspace no existe: {workspace}")
        return []
    
    candidatos = []
    extensiones = (".txt", ".md", ".docx")
    try:
        for path in workspace.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in extensiones:
                continue
            if path.stat().st_size > 5_000_000:  # skip > 5MB
                continue
            
            # Match por nombre
            if cc in path.name:
                contenido = _leer_texto(path)
                if contenido:
                    candidatos.append({"nombre": path.name, "ruta": str(path), "contenido": contenido})
                    continue
            
            # Match por contenido (solo primeros chars)
            contenido = _leer_texto(path, max_chars=500)
            if cc in contenido:
                contenido_completo = _leer_texto(path)
                candidatos.append({"nombre": path.name, "ruta": str(path), "contenido": contenido_completo})
    except Exception as e:
        _log(f"Error escaneando: {e}")
    
    # Ordenar por mtime descendente (más recientes primero)
    candidatos.sort(key=lambda d: Path(d["ruta"]).stat().st_mtime, reverse=True)
    return candidatos[:max_archivos]


def ejecutar(paciente_cc: str) -> dict:
    notas = leer_notas_crudas(paciente_cc)
    return {"notas_crudas": notas, "total": len(notas)}
```

- [ ] **Step 4: Tests pasan**

```bash
pytest tests/test_workflow_steps/test_leer_notas_crudas.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/workflow_steps/leer_notas_crudas.py tests/test_workflow_steps/test_leer_notas_crudas.py
git commit -m "📝 workflow_steps: leer_notas_crudas del workspace de Sandra"
```

---

## Task 6: `workflow_steps/leer_formatos_subidos.py`

**Files:**
- Create: `backend/workflow_steps/leer_formatos_subidos.py`
- Create: `tests/test_workflow_steps/test_leer_formatos_subidos.py`

- [ ] **Step 1: Test**

```python
"""Tests para leer_formatos_subidos.py."""
import sys
from pathlib import Path
from docx import Document
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_lee_formatos_subidos_para_task(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    formato_dir = storage / "formatos_subidos" / "abc12345"
    formato_dir.mkdir(parents=True)
    
    # Crear DOCX de prueba
    doc = Document()
    doc.add_paragraph("Análisis de exigencias antiguo")
    doc.add_paragraph("Datos incompletos del paciente")
    doc.save(str(formato_dir / "analisis_viejo.docx"))
    
    monkeypatch.setenv("STORAGE_DIR", str(storage))
    from backend.workflow_steps.leer_formatos_subidos import leer_formatos_subidos
    
    formatos = leer_formatos_subidos("abc12345")
    assert len(formatos) == 1
    assert "Análisis de exigencias antiguo" in formatos[0]["contenido"]


def test_devuelve_vacio_si_no_hay_formatos(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    from backend.workflow_steps.leer_formatos_subidos import leer_formatos_subidos
    formatos = leer_formatos_subidos("xyz999")
    assert formatos == []
```

- [ ] **Step 2: Test debe fallar**

```bash
pytest tests/test_workflow_steps/test_leer_formatos_subidos.py -v
```

- [ ] **Step 3: Implementar**

```python
"""
Paso 4: Leer formatos DOCX que Sandra subió como referencia para esta task.

Sandra a veces sube un formato antiguo desorganizado para que Tomy lo
use como base de información (que cruzará con verificados).

Archivos se guardan en: storage/formatos_subidos/{task_id}/*.docx
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict


def _log(msg: str):
    print(f"[FORMATOS_SUB {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def leer_formatos_subidos(task_id: str, max_chars: int = 5000) -> List[Dict]:
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    formato_dir = storage / "formatos_subidos" / task_id
    if not formato_dir.exists():
        return []
    
    formatos = []
    try:
        from docx import Document
        for path in formato_dir.glob("*.docx"):
            try:
                doc = Document(str(path))
                texto = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                texto = texto[:max_chars]
                # Agregar tablas resumidas
                for tabla in doc.tables[:3]:
                    for row in tabla.rows[:5]:
                        celdas = [c.text.strip()[:60] for c in row.cells if c.text.strip()]
                        if celdas:
                            texto += "\n" + " | ".join(celdas)
                formatos.append({"nombre": path.name, "ruta": str(path), "contenido": texto[:max_chars]})
            except Exception as e:
                _log(f"Error leyendo {path.name}: {e}")
    except ImportError:
        _log("python-docx no disponible")
    
    return formatos


def ejecutar(task_id: str) -> dict:
    formatos = leer_formatos_subidos(task_id)
    return {"formatos_subidos": formatos, "total": len(formatos)}
```

- [ ] **Step 4: Tests pasan**

```bash
pytest tests/test_workflow_steps/test_leer_formatos_subidos.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/workflow_steps/leer_formatos_subidos.py tests/test_workflow_steps/test_leer_formatos_subidos.py
git commit -m "📎 workflow_steps: leer_formatos_subidos como referencia opcional"
```

---

## Task 7: `workflow_steps/sintetizar_maestro.py` — LLM razonador

**Files:**
- Create: `backend/workflow_steps/sintetizar_maestro.py`
- Create: `tests/test_workflow_steps/test_sintetizar_maestro.py`

- [ ] **Step 1: Test**

```python
"""Tests para sintetizar_maestro.py."""
import json
import sys
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_sintesis_compone_contexto_completo():
    from backend.workflow_steps.sintetizar_maestro import _componer_contexto
    
    transcripcion = {"texto": "Paciente dice que le duele.", "duracion": 60}
    datos_portales = {"cc": "1193143688", "medifolios": {"nombre1": "JUAN"}}
    notas_crudas = [{"nombre": "n.txt", "contenido": "Dolor lumbar"}]
    formatos_subidos = []
    
    ctx = _componer_contexto(transcripcion, datos_portales, notas_crudas, formatos_subidos, paciente_cc="1193143688")
    assert "TRANSCRIPCIÓN DEL AUDIO" in ctx
    assert "DATOS VERIFICADOS" in ctx
    assert "NOTAS CRUDAS" in ctx
    assert "Paciente dice que le duele" in ctx
    assert "JUAN" in ctx


def test_sintesis_llama_subprocess_lote_worker():
    """sintetizar_maestro debe usar lote_worker --tipo sintetizar."""
    from backend.workflow_steps.sintetizar_maestro import sintetizar
    
    with patch("backend.workflow_steps.sintetizar_maestro.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"ok": true, "respuesta": "Datos sintetizados", "tokens": {"total": 1000}}',
            stderr="",
        )
        resultado = sintetizar(
            transcripcion={"texto": "abc"},
            datos_portales={"cc": "123"},
            notas_crudas=[],
            formatos_subidos=[],
            paciente_cc="123",
        )
    
    assert mock_run.called
    args = mock_run.call_args[0][0]
    assert "lote_worker" in " ".join(args)
    assert "sintetizar" in " ".join(args)
    assert resultado["respuesta"] == "Datos sintetizados"


def test_chunking_si_contexto_grande():
    from backend.workflow_steps.sintetizar_maestro import _resumir_si_largo
    
    texto_largo = "Lorem ipsum " * 5000  # ~60K chars
    resumido = _resumir_si_largo(texto_largo, max_chars=10000)
    assert len(resumido) <= 10500  # con margen
    assert "RESUMIDO" in resumido or len(texto_largo) <= 10000
```

- [ ] **Step 2: Tests fallan**

```bash
pytest tests/test_workflow_steps/test_sintetizar_maestro.py -v
```

- [ ] **Step 3: Implementar**

```python
"""
Paso 5: Síntesis maestra — LLM razonador con contexto cruzado.

Compone contexto a partir de:
  - Transcripción del audio (chunked si es necesario)
  - Datos verificados de portales (Medifolios + Positiva)
  - Notas crudas del workspace
  - Formatos antiguos subidos como referencia

Llama al LLM razonador (deepseek-v4-pro) en subprocess aislado vía
lote_worker --tipo sintetizar para evitar OOM.

Si el contexto excede 30K chars, hace resumen progresivo antes.
"""
import json
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List


def _log(msg: str):
    print(f"[SINTESIS {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _formatear_portales(datos: dict) -> str:
    """Formatea datos verificados en bloque legible para el LLM."""
    if not datos or datos.get("_vacio"):
        return "[NO HAY DATOS VERIFICADOS DE PORTALES]"
    
    medi = datos.get("medifolios", {})
    pos = datos.get("positiva", {})
    discrepancias = datos.get("_meta", {}).get("discrepancias", [])
    
    bloques = ["📋 DATOS VERIFICADOS PORTALES:"]
    if medi:
        nombre = " ".join([medi.get("nombre1", ""), medi.get("apellido1", "")]).strip()
        if nombre: bloques.append(f"  Paciente: {nombre}")
        if medi.get("telefono"): bloques.append(f"  Teléfono: {medi['telefono']}")
        if medi.get("direccion"): bloques.append(f"  Dirección: {medi['direccion']}")
        if medi.get("siniestro_medi"): bloques.append(f"  Siniestro (Medi): {medi['siniestro_medi']}")
    if pos.get("siniestros"):
        for s in pos["siniestros"][:2]:
            bloques.append(f"  Siniestro (Pos): {s.get('id','?')} | {s.get('fecha','?')} | {s.get('diagnostico','?')[:50]}")
    if discrepancias:
        bloques.append("\n⚠️ DISCREPANCIAS DETECTADAS:")
        for d in discrepancias:
            bloques.append(f"  - {d.get('campo','?')}: Medi={d.get('medifolios','?')} vs Pos={d.get('positiva','?')}")
    return "\n".join(bloques)


def _formatear_notas(notas: list) -> str:
    if not notas:
        return "[NO HAY NOTAS CRUDAS]"
    bloques = [f"📝 NOTAS CRUDAS ({len(notas)} archivos):"]
    for n in notas[:5]:
        bloques.append(f"\n--- {n['nombre']} ---\n{n['contenido']}")
    return "\n".join(bloques)


def _formatear_formatos_subidos(formatos: list) -> str:
    if not formatos:
        return ""
    bloques = [f"📄 FORMATOS DE REFERENCIA SUBIDOS POR SANDRA ({len(formatos)}):"]
    for f in formatos:
        bloques.append(f"\n--- {f['nombre']} ---\n{f['contenido']}")
    return "\n".join(bloques)


def _resumir_si_largo(texto: str, max_chars: int = 30000) -> str:
    """Si el texto excede max_chars, devuelve [INICIO] ... [RESUMIDO] ... [FIN]."""
    if len(texto) <= max_chars:
        return texto
    inicio_chars = max_chars * 4 // 10
    fin_chars = max_chars * 4 // 10
    return (
        texto[:inicio_chars]
        + f"\n\n[...RESUMIDO: {len(texto) - inicio_chars - fin_chars} chars omitidos del medio...]\n\n"
        + texto[-fin_chars:]
    )


def _componer_contexto(transcripcion, datos_portales, notas_crudas, formatos_subidos, paciente_cc) -> str:
    transcripcion_texto = transcripcion.get("texto", "")
    if len(transcripcion_texto) > 20000:
        transcripcion_texto = _resumir_si_largo(transcripcion_texto, 20000)
    
    bloques = [
        f"═══ PACIENTE CC: {paciente_cc} ═══\n",
        "🎙️ TRANSCRIPCIÓN DEL AUDIO:",
        transcripcion_texto,
        "",
        _formatear_portales(datos_portales),
        "",
        _formatear_notas(notas_crudas),
        "",
        _formatear_formatos_subidos(formatos_subidos),
    ]
    return "\n".join(bloques)


PROMPT_USUARIO_SINTESIS = """Eres Tomy, asistente clínico EXPERTO de Sandra (RILO SAS, ARL Positiva Colombia).

Tu tarea AHORA: a partir del contexto cruzado abajo (audio + portales + notas + formatos), produce un JSON estructurado con TODOS los datos clínicos necesarios para generar los 7 formatos oficiales.

Devuelve SOLO un bloque JSON válido entre ```json ... ```. Estructura esperada:

```json
{
  "paciente": {"documento": "...", "nombre": "...", "edad": "...", "telefono": "...", "direccion": "...", "email": "...", "eps_ips": "...", "afp": "...", "ocupacion": "..."},
  "empresa": {"nombre": "...", "nit": "...", "cargo": "..."},
  "siniestro": {"id_siniestro": "...", "fecha_evento": "...", "tipo_evento": "...", "diagnostico_cie10": "...", "descripcion": "..."},
  "estado_caso": "NUEVO|SEGUIMIENTO|CIERRE|PRUEBA_TRABAJO",
  "metodologia": "...",
  "proceso_productivo": "...",
  "apreciacion_trabajador": "...",
  "materiales": [{"nombre":"...","estado":"..."}],
  "peligros": [{"nombre":"...","descripcion":"...","recomendacion":"..."}],
  "tareas_criticas": [{"tarea":"...","observacion":"...","desempeno":"..."}],
  "concepto_desempeno": "...",
  "recomendaciones": {"trabajador":"...","empresa":"..."},
  "logros": "...",
  "obstaculos": "...",
  "_meta": {
    "campos_faltantes": ["lista de campos críticos sin info"],
    "discrepancias": ["resoluciones tomadas"],
    "confianza_global": 0.0-1.0
  }
}
```

REGLAS:
- Si un dato está en portales Y en audio Y coinciden → úsalo.
- Si discrepan → prevalece portal (es fuente oficial). Marca en _meta.discrepancias.
- Si solo está en audio (subjetivo) → úsalo y marca confianza_global menor.
- Si falta dato crítico → escribe "[FALTA: descripción específica]" y agrégalo a campos_faltantes.
- NUNCA inventes datos clínicos. Si no sabes, di [FALTA].
- Español colombiano clínico.
"""


def sintetizar(transcripcion: Dict, datos_portales: Dict, notas_crudas: List, formatos_subidos: List, paciente_cc: str) -> Dict:
    """Llama a lote_worker --tipo sintetizar con el contexto cruzado."""
    contexto = _componer_contexto(transcripcion, datos_portales, notas_crudas, formatos_subidos, paciente_cc)
    _log(f"Contexto compuesto: {len(contexto)} chars")
    
    # Escribir contexto a archivo temporal (puede ser largo)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write(contexto)
        contexto_file = tmp.name
    
    modelo = os.getenv("LLM_MODEL_SINTESIS", "deepseek-v4-pro")
    
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "backend.lote_worker",
             "--tipo", "sintetizar",
             "--modelo", modelo,
             "--mensaje", PROMPT_USUARIO_SINTESIS,
             "--contexto-file", contexto_file,
             "--cc", paciente_cc],
            capture_output=True, text=True,
            timeout=600,
            cwd=str(Path(__file__).parent.parent.parent),
        )
    finally:
        try: os.unlink(contexto_file)
        except Exception: pass
    
    if proc.returncode != 0:
        _log(f"lote_worker falló: {proc.stderr[:500]}")
        return {"ok": False, "error": proc.stderr[:500]}
    
    try:
        resultado = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "stdout no es JSON"}
    
    respuesta_texto = resultado.get("respuesta", "")
    _log(f"Síntesis: {resultado.get('tokens', {})} tokens en {resultado.get('tiempo_s')}s")
    
    # Intentar extraer el JSON estructurado del bloque ```json ... ```
    import re
    match = re.search(r'```json\s*(\{.*?\})\s*```', respuesta_texto, re.DOTALL)
    datos_clinicos = None
    if match:
        try:
            datos_clinicos = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            _log(f"JSON clinico inválido: {e}")
    
    return {
        "ok": True,
        "respuesta_completa": respuesta_texto,
        "datos_clinicos": datos_clinicos,
        "tokens": resultado.get("tokens", {}),
        "tiempo_s": resultado.get("tiempo_s"),
    }


def ejecutar(transcripcion: Dict, datos_portales: Dict, notas_crudas: List, formatos_subidos: List, paciente_cc: str) -> dict:
    return sintetizar(transcripcion, datos_portales, notas_crudas, formatos_subidos, paciente_cc)
```

- [ ] **Step 4: Tests pasan**

```bash
pytest tests/test_workflow_steps/test_sintetizar_maestro.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/workflow_steps/sintetizar_maestro.py tests/test_workflow_steps/test_sintetizar_maestro.py
git commit -m "🧠 workflow_steps: sintetizar_maestro cruza audio+portales+notas con LLM"
```

---

## Task 8: `workflow_steps/generar_formatos.py`

**Files:**
- Create: `backend/workflow_steps/generar_formatos.py`
- Create: `tests/test_workflow_steps/test_generar_formatos.py`

- [ ] **Step 1: Test**

```python
"""Tests para generar_formatos.py."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_genera_solo_formatos_aplicables_por_estado():
    """Estado NUEVO no debe generar 'cierre' ni 'prueba'."""
    from backend.workflow_steps.generar_formatos import _seleccionar_formatos
    formatos = _seleccionar_formatos("NUEVO")
    assert "analisis" in formatos
    assert "valoracion" in formatos
    assert "cierre" not in formatos
    
    formatos_cierre = _seleccionar_formatos("CIERRE")
    assert "cierre" in formatos_cierre


def test_genera_formatos_llama_a_doc_generator(tmp_path, monkeypatch):
    """generar_formatos debe invocar funciones de doc_generator."""
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    datos = {
        "paciente": {"documento": "1193143688", "nombre": "JUAN DURAN"},
        "siniestro": {"id_siniestro": "503463870"},
        "empresa": {"nombre": "ACME"},
        "estado_caso": "SEGUIMIENTO",
    }
    from backend.workflow_steps.generar_formatos import generar_todos
    
    with patch("backend.workflow_steps.generar_formatos.generar_documento") as mock_gen:
        mock_gen.return_value = str(tmp_path / "fake.docx")
        resultado = generar_todos(datos, task_id="abc123")
    
    assert resultado["ok"]
    assert mock_gen.called
    assert resultado["formatos_generados"]
```

- [ ] **Step 2: Test debe fallar**

```bash
pytest tests/test_workflow_steps/test_generar_formatos.py -v
```

- [ ] **Step 3: Implementar**

```python
"""
Paso 6: Generar los formatos DOCX aplicables.

Wrapper sobre backend.doc_generator (que ya tiene las 7 funciones generar_*).
Selecciona qué formatos generar según el estado del caso (NUEVO, SEGUIMIENTO, CIERRE, PRUEBA_TRABAJO).
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List


def _log(msg: str):
    print(f"[GENERAR_FORMATOS {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


# Mapeo de estado → formatos aplicables (extender según format_selector.py)
FORMATOS_POR_ESTADO = {
    "NUEVO": ["analisis", "medidas", "recomendaciones", "citacion", "valoracion"],
    "SEGUIMIENTO": ["analisis", "medidas", "recomendaciones", "valoracion"],
    "CIERRE": ["analisis", "medidas", "recomendaciones", "cierre", "valoracion"],
    "PRUEBA_TRABAJO": ["analisis", "prueba", "valoracion"],
}

# Mapeo formato → función generadora en doc_generator
FORMATO_FUNC = {
    "analisis": "generar_analisis_exigencia",
    "medidas": "generar_carta_medidas",
    "recomendaciones": "generar_carta_recomendaciones",
    "cierre": "generar_cierre_caso",
    "citacion": "generar_citacion_empresas",
    "prueba": "generar_prueba_trabajo",
    "valoracion": "generar_valoracion_desempeno",
}


def _seleccionar_formatos(estado_caso: str) -> List[str]:
    estado = (estado_caso or "SEGUIMIENTO").upper()
    return FORMATOS_POR_ESTADO.get(estado, FORMATOS_POR_ESTADO["SEGUIMIENTO"])


# Imports diferidos para que tests puedan mockear
def generar_documento(formato_corto: str, datos: dict, output_name: str = None) -> str:
    from backend import doc_generator
    func_name = FORMATO_FUNC[formato_corto]
    func = getattr(doc_generator, func_name, None)
    if not func:
        raise ValueError(f"No existe generador para formato '{formato_corto}'")
    return func(datos, output_name=output_name)


def generar_todos(datos: dict, task_id: str) -> Dict:
    """Genera los formatos aplicables. Retorna dict con generados y errores."""
    estado = datos.get("estado_caso", "SEGUIMIENTO")
    formatos = _seleccionar_formatos(estado)
    _log(f"Estado {estado}: generar {len(formatos)} formatos: {formatos}")
    
    generados = []
    errores = []
    cc = datos.get("paciente", {}).get("documento", "sin_cc")
    
    for fmt in formatos:
        try:
            output_name = f"{fmt}_{cc}_{task_id[:8]}"
            path = generar_documento(fmt, datos, output_name=output_name)
            generados.append({"formato": fmt, "archivo": path})
            _log(f"✅ {fmt}: {Path(path).name}")
        except Exception as e:
            _log(f"❌ {fmt}: {type(e).__name__}: {e}")
            errores.append({"formato": fmt, "error": f"{type(e).__name__}: {e}"})
    
    return {
        "ok": len(generados) > 0,
        "formatos_generados": generados,
        "errores": errores,
        "estado_caso": estado,
    }


def ejecutar(datos_clinicos: dict, task_id: str) -> dict:
    if not datos_clinicos:
        return {"ok": False, "error": "Sin datos_clinicos para generar"}
    return generar_todos(datos_clinicos, task_id)
```

- [ ] **Step 4: Tests pasan**

```bash
pytest tests/test_workflow_steps/test_generar_formatos.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/workflow_steps/generar_formatos.py tests/test_workflow_steps/test_generar_formatos.py
git commit -m "📄 workflow_steps: generar_formatos según estado del caso"
```

---

## Task 9: `workflow_steps/qa_formatos.py` + `convertir_pdf.py` + `notificar_listo.py`

Tres steps cortos juntos.

**Files:**
- Create: `backend/workflow_steps/qa_formatos.py`
- Create: `backend/workflow_steps/convertir_pdf.py`
- Create: `backend/workflow_steps/notificar_listo.py`
- Create: `tests/test_workflow_steps/test_steps_finales.py`

- [ ] **Step 1: Tests**

```python
"""Tests para qa, pdf, notificar (steps finales del workflow)."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_qa_devuelve_warnings_pero_no_falla(tmp_path):
    from backend.workflow_steps.qa_formatos import qa_todos
    fake_doc = tmp_path / "fake.docx"
    from docx import Document
    Document().save(str(fake_doc))
    
    resultado = qa_todos([{"formato": "analisis", "archivo": str(fake_doc)}])
    assert "resultados" in resultado
    assert len(resultado["resultados"]) == 1


def test_convertir_pdf_skipea_si_libreoffice_falta(tmp_path, monkeypatch):
    from backend.workflow_steps.convertir_pdf import convertir_todos
    monkeypatch.setattr("backend.workflow_steps.convertir_pdf._tiene_libreoffice", lambda: False)
    
    formatos = [{"formato": "x", "archivo": str(tmp_path / "fake.docx")}]
    resultado = convertir_todos(formatos)
    assert not resultado["ok"]
    assert "libreoffice" in resultado["error"].lower()


def test_notificar_listo_envia_telegram(monkeypatch):
    from backend.workflow_steps.notificar_listo import notificar
    
    with patch("backend.workflow_steps.notificar_listo.enviar_telegram") as mock_tel:
        mock_tel.return_value = True
        ok = notificar(task_id="abc", paciente_nombre="Juan", paciente_cc="123",
                       formatos_generados=[{"formato":"analisis"}], warnings=[], dashboard_url="http://localhost:3000")
    
    assert mock_tel.called
    mensaje = mock_tel.call_args[0][0]
    assert "Juan" in mensaje
    assert "1 formato" in mensaje or "formatos" in mensaje
    assert "http://localhost:3000" in mensaje
```

- [ ] **Step 2: Tests fallan**

```bash
pytest tests/test_workflow_steps/test_steps_finales.py -v
```

- [ ] **Step 3: Implementar `qa_formatos.py`**

```python
"""
Paso 7: QA 10 capas sobre cada DOCX generado.

Wrapper sobre skills/verificar-documento/scripts/qa_completo.py.
Si el script no existe o falla, devuelve warning (no bloquea).
"""
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List


def _log(msg: str):
    print(f"[QA {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _qa_script_path() -> Path:
    return Path(__file__).parent.parent.parent / "skills" / "verificar-documento" / "scripts" / "qa_completo.py"


def qa_uno(formato: dict) -> dict:
    """Ejecuta qa_completo.py sobre 1 archivo. Retorna dict con resultado + warnings."""
    archivo = formato.get("archivo")
    if not archivo or not Path(archivo).exists():
        return {**formato, "qa_ok": False, "qa_error": "archivo no existe"}
    
    qa_script = _qa_script_path()
    if not qa_script.exists():
        _log(f"qa_completo.py no encontrado, skip")
        return {**formato, "qa_ok": True, "qa_warnings": ["QA script no disponible"]}
    
    try:
        proc = subprocess.run(
            [sys.executable, str(qa_script), archivo],
            capture_output=True, text=True, timeout=60,
        )
        return {
            **formato,
            "qa_ok": proc.returncode == 0,
            "qa_output": proc.stdout[-500:],
            "qa_warnings": [l for l in proc.stdout.split("\n") if "WARN" in l.upper()][:5],
        }
    except Exception as e:
        return {**formato, "qa_ok": False, "qa_error": str(e)}


def qa_todos(formatos: List[dict]) -> Dict:
    resultados = [qa_uno(f) for f in formatos]
    return {
        "ok": True,
        "resultados": resultados,
        "total": len(formatos),
        "exitosos": sum(1 for r in resultados if r.get("qa_ok")),
        "con_warnings": sum(1 for r in resultados if r.get("qa_warnings")),
    }


def ejecutar(formatos_generados: List[dict]) -> dict:
    return qa_todos(formatos_generados)
```

- [ ] **Step 4: Implementar `convertir_pdf.py`**

```python
"""
Paso 8: Convertir cada DOCX aprobado por QA a PDF/A.

Usa LibreOffice en modo headless si está instalado.
Si no está, deja un warning pero no bloquea.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List


def _log(msg: str):
    print(f"[PDF {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _tiene_libreoffice() -> bool:
    return shutil.which("libreoffice") is not None or shutil.which("soffice") is not None


def _convertir_uno(docx_path: str, output_dir: Path) -> str:
    """Convierte 1 docx a pdf usando libreoffice headless. Retorna path al PDF."""
    bin_lo = shutil.which("libreoffice") or shutil.which("soffice")
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [bin_lo, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), docx_path]
    subprocess.run(cmd, capture_output=True, check=True, timeout=120)
    pdf_name = Path(docx_path).stem + ".pdf"
    return str(output_dir / pdf_name)


def convertir_todos(formatos: List[dict]) -> Dict:
    if not _tiene_libreoffice():
        return {"ok": False, "error": "LibreOffice no instalado", "pdfs": []}
    
    pdfs = []
    errores = []
    output_dir = Path(os.getenv("STORAGE_DIR", "./storage")) / "pdfs"
    for f in formatos:
        if not f.get("qa_ok"):
            continue
        try:
            pdf = _convertir_uno(f["archivo"], output_dir)
            pdfs.append({**f, "pdf": pdf})
            _log(f"✅ PDF: {Path(pdf).name}")
        except Exception as e:
            _log(f"❌ {f.get('formato','?')}: {e}")
            errores.append({"formato": f.get("formato"), "error": str(e)})
    
    return {"ok": True, "pdfs": pdfs, "errores": errores}


def ejecutar(qa_resultados: List[dict]) -> dict:
    return convertir_todos(qa_resultados)
```

- [ ] **Step 5: Implementar `notificar_listo.py`**

```python
"""
Paso 9: Telegram a Sandra cuando el workflow termina.

Mensaje incluye:
  - Nombre del paciente
  - Cantidad de formatos generados
  - Warnings (si los hay)
  - URL del dashboard para revisar
"""
import os
from datetime import datetime
from typing import List


def _log(msg: str):
    import sys
    print(f"[NOTIFICAR {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def notificar(task_id: str, paciente_nombre: str, paciente_cc: str,
              formatos_generados: List[dict], warnings: List[str],
              dashboard_url: str = None) -> bool:
    """Envía mensaje Telegram a Sandra. Retorna True si OK."""
    from backend.notificador import enviar_telegram
    
    url = dashboard_url or os.getenv("DASHBOARD_URL", "http://localhost:3000")
    url_paciente = f"{url}/paciente/{paciente_cc}"
    
    cantidad = len(formatos_generados)
    nombre = paciente_nombre or f"CC {paciente_cc}"
    
    lines = [f"✅ Listo! Procesé los datos de {nombre}."]
    if cantidad == 1:
        lines.append("1 formato generado.")
    else:
        lines.append(f"{cantidad} formatos generados.")
    
    if warnings:
        lines.append(f"\n⚠️ {len(warnings)} advertencia(s):")
        for w in warnings[:3]:
            lines.append(f"  • {w[:100]}")
    
    lines.append(f"\nRevisalos en: {url_paciente}")
    
    mensaje = "\n".join(lines)
    return enviar_telegram(mensaje)


def ejecutar(task_id: str, paciente_nombre: str, paciente_cc: str,
             formatos_generados: list, warnings: list) -> dict:
    ok = notificar(task_id, paciente_nombre, paciente_cc, formatos_generados, warnings)
    return {"ok": ok, "telegram_enviado": ok}
```

- [ ] **Step 6: Tests pasan**

```bash
pytest tests/test_workflow_steps/test_steps_finales.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/workflow_steps/qa_formatos.py backend/workflow_steps/convertir_pdf.py backend/workflow_steps/notificar_listo.py tests/test_workflow_steps/test_steps_finales.py
git commit -m "✅ workflow_steps: qa + pdf + notificar (steps finales del workflow)"
```

---

## Task 10: `workflow_runner.py` — orquestador end-to-end

**Files:**
- Create: `backend/workflow_runner.py`
- Create: `tests/test_workflow_runner.py`

- [ ] **Step 1: Test del runner completo (mockeado)**

`tests/test_workflow_runner.py`:

```python
"""Tests para workflow_runner.py — orquesta los 9 pasos."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_runner_ejecuta_los_9_pasos_en_orden(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("WORKFLOW_DB_PATH", str(tmp_path / "wf.db"))
    monkeypatch.setenv("TOMY_COMPLETO_ENABLED", "true")
    
    # Mocks para cada step
    with patch("backend.workflow_steps.transcribir.ejecutar") as m1, \
         patch("backend.workflow_steps.resolver_paciente.ejecutar") as m2, \
         patch("backend.workflow_steps.leer_notas_crudas.ejecutar") as m3, \
         patch("backend.workflow_steps.leer_formatos_subidos.ejecutar") as m4, \
         patch("backend.workflow_steps.sintetizar_maestro.ejecutar") as m5, \
         patch("backend.workflow_steps.generar_formatos.ejecutar") as m6, \
         patch("backend.workflow_steps.qa_formatos.ejecutar") as m7, \
         patch("backend.workflow_steps.convertir_pdf.ejecutar") as m8, \
         patch("backend.workflow_steps.notificar_listo.ejecutar") as m9:
        
        m1.return_value = {"texto": "...", "warnings": []}
        m2.return_value = {"datos_portales": {"medifolios": {"nombre1": "JUAN"}}, "fuente": "cache"}
        m3.return_value = {"notas_crudas": [], "total": 0}
        m4.return_value = {"formatos_subidos": [], "total": 0}
        m5.return_value = {"ok": True, "datos_clinicos": {"paciente": {"nombre": "JUAN", "documento": "1193143688"}, "estado_caso": "SEGUIMIENTO"}}
        m6.return_value = {"ok": True, "formatos_generados": [{"formato": "analisis", "archivo": "/tmp/a.docx"}], "errores": []}
        m7.return_value = {"ok": True, "resultados": [{"formato": "analisis", "qa_ok": True}], "exitosos": 1}
        m8.return_value = {"ok": True, "pdfs": [{"formato": "analisis", "pdf": "/tmp/a.pdf"}]}
        m9.return_value = {"ok": True, "telegram_enviado": True}
        
        from backend.workflow_runner import ejecutar_workflow
        resultado = ejecutar_workflow(audio_path="/tmp/a.m4a", paciente_cc="1193143688")
    
    for m in [m1, m2, m3, m4, m5, m6, m7, m8, m9]:
        assert m.called, f"step no fue invocado: {m}"
    
    assert resultado["estado"] == "listo"
    assert resultado["task_id"]


def test_runner_marca_error_si_step_falla(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("WORKFLOW_DB_PATH", str(tmp_path / "wf.db"))
    monkeypatch.setenv("TOMY_COMPLETO_ENABLED", "true")
    
    with patch("backend.workflow_steps.transcribir.ejecutar") as m1:
        m1.side_effect = RuntimeError("Deepgram timeout")
        from backend.workflow_runner import ejecutar_workflow
        resultado = ejecutar_workflow(audio_path="/tmp/a.m4a", paciente_cc="1193143688")
    
    assert "error" in resultado["estado"]
    assert "Deepgram" in resultado.get("error", "")
```

- [ ] **Step 2: Tests fallan**

```bash
pytest tests/test_workflow_runner.py -v
```

- [ ] **Step 3: Implementar `backend/workflow_runner.py`**

```python
"""
Workflow runner — orquesta los 9 pasos del pipeline "Día de Sandra".

Uso:
    from backend.workflow_runner import ejecutar_workflow
    resultado = ejecutar_workflow(audio_path="/path/a.m4a", paciente_cc="1193143688")
    # → {"task_id": "abc12345", "estado": "listo", ...}

También se puede ejecutar en background con asyncio.create_task() desde FastAPI.
"""
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict


def _log(msg: str):
    print(f"[WORKFLOW {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


STEPS = [
    ("transcribir", "transcribiendo", 1),
    ("resolver_paciente", "resolviendo_paciente", 2),
    ("leer_notas_crudas", "leyendo_notas", 3),
    ("leer_formatos_subidos", "leyendo_formatos", 4),
    ("sintetizar_maestro", "sintetizando", 5),
    ("generar_formatos", "generando", 6),
    ("qa_formatos", "qa", 7),
    ("convertir_pdf", "pdf", 8),
    ("notificar_listo", "notificando", 9),
]


def ejecutar_workflow(audio_path: str, paciente_cc: str, task_id_existente: str = None) -> Dict:
    """Ejecuta los 9 pasos secuencialmente. Persiste estado en task_db."""
    if os.getenv("TOMY_COMPLETO_ENABLED", "false").lower() != "true":
        return {"estado": "deshabilitado", "razon": "TOMY_COMPLETO_ENABLED=false"}
    
    from backend.task_db import TaskDB
    
    db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
    db = TaskDB(db_path)
    
    if task_id_existente:
        task_id = task_id_existente
    else:
        task_id = db.crear_task(paciente_cc=paciente_cc, audio_path=audio_path)
    
    _log(f"═══ TASK {task_id} | CC {paciente_cc} ═══")
    contexto = {"audio_path": audio_path, "paciente_cc": paciente_cc, "task_id": task_id}
    t_total = time.time()
    
    for step_name, estado_label, paso_num in STEPS:
        db.actualizar_paso(task_id, paso=paso_num, estado=estado_label)
        _log(f"PASO {paso_num}/9: {step_name}")
        t_step = time.time()
        
        try:
            modulo = __import__(f"backend.workflow_steps.{step_name}", fromlist=["ejecutar"])
            # Cada step recibe el contexto y devuelve dict
            kwargs = _build_kwargs(step_name, contexto)
            resultado_step = modulo.ejecutar(**kwargs)
            contexto[step_name] = resultado_step
            _log(f"PASO {paso_num} OK en {time.time()-t_step:.1f}s")
            
            # Guard: si síntesis o generación falla, abortamos
            if step_name in ("sintetizar_maestro", "generar_formatos") and not resultado_step.get("ok"):
                error = resultado_step.get("error", f"step {step_name} retornó ok=false")
                db.marcar_error(task_id, paso=paso_num, error=error)
                return {"task_id": task_id, "estado": f"error_en_paso_{paso_num}", "error": error}
        
        except Exception as e:
            _log(f"PASO {paso_num} FALLÓ: {type(e).__name__}: {e}")
            db.marcar_error(task_id, paso=paso_num, error=f"{type(e).__name__}: {e}")
            return {"task_id": task_id, "estado": f"error_en_paso_{paso_num}", "error": str(e)}
    
    # Empaquetar resultado
    formatos_generados = contexto.get("generar_formatos", {}).get("formatos_generados", [])
    pdfs = contexto.get("convertir_pdf", {}).get("pdfs", [])
    warnings = contexto.get("transcribir", {}).get("warnings", [])
    qa_warnings = []
    for r in contexto.get("qa_formatos", {}).get("resultados", []):
        qa_warnings.extend(r.get("qa_warnings", []))
    
    resultado_final = {
        "task_id": task_id,
        "estado": "listo",
        "duracion_total_s": round(time.time() - t_total, 1),
        "paciente_cc": paciente_cc,
        "formatos_generados": formatos_generados,
        "pdfs": pdfs,
        "warnings": warnings + qa_warnings,
    }
    db.guardar_resultado(task_id, resultado_final, estado="listo")
    _log(f"═══ TASK {task_id} LISTO en {time.time()-t_total:.1f}s ═══")
    return resultado_final


def _build_kwargs(step_name: str, contexto: dict) -> dict:
    """Construye los kwargs para cada step a partir del contexto acumulado."""
    audio = contexto.get("audio_path")
    cc = contexto.get("paciente_cc")
    task_id = contexto.get("task_id")
    
    if step_name == "transcribir":
        return {"audio_path": audio, "paciente_cc": cc}
    if step_name == "resolver_paciente":
        return {"paciente_cc": cc, "forzar_extraer": False}
    if step_name == "leer_notas_crudas":
        return {"paciente_cc": cc}
    if step_name == "leer_formatos_subidos":
        return {"task_id": task_id}
    if step_name == "sintetizar_maestro":
        return {
            "transcripcion": contexto.get("transcribir", {}),
            "datos_portales": contexto.get("resolver_paciente", {}).get("datos_portales", {}),
            "notas_crudas": contexto.get("leer_notas_crudas", {}).get("notas_crudas", []),
            "formatos_subidos": contexto.get("leer_formatos_subidos", {}).get("formatos_subidos", []),
            "paciente_cc": cc,
        }
    if step_name == "generar_formatos":
        sintesis = contexto.get("sintetizar_maestro", {})
        return {"datos_clinicos": sintesis.get("datos_clinicos") or {}, "task_id": task_id}
    if step_name == "qa_formatos":
        return {"formatos_generados": contexto.get("generar_formatos", {}).get("formatos_generados", [])}
    if step_name == "convertir_pdf":
        return {"qa_resultados": contexto.get("qa_formatos", {}).get("resultados", [])}
    if step_name == "notificar_listo":
        portales = contexto.get("resolver_paciente", {}).get("datos_portales", {})
        nombre = portales.get("medifolios", {}).get("nombre1", "") + " " + portales.get("medifolios", {}).get("apellido1", "")
        return {
            "task_id": task_id,
            "paciente_nombre": nombre.strip() or f"CC {cc}",
            "paciente_cc": cc,
            "formatos_generados": contexto.get("generar_formatos", {}).get("formatos_generados", []),
            "warnings": contexto.get("transcribir", {}).get("warnings", []),
        }
    return {}
```

- [ ] **Step 4: Tests pasan**

```bash
pytest tests/test_workflow_runner.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/workflow_runner.py tests/test_workflow_runner.py
git commit -m "🎬 workflow_runner: orquesta los 9 pasos end-to-end"
```

---

# PARTE 3: Endpoints API para subir audio + monitorear (Task 11)

## Task 11: Endpoints FastAPI para workflow

**Files:**
- Modify: `backend/server.py` (agregar endpoints al final)

- [ ] **Step 1: Test integración del endpoint**

Agregar a `tests/test_workflow_runner.py`:

```python
def test_endpoint_procesar_paciente_crea_task(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMY_COMPLETO_ENABLED", "true")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("WORKFLOW_DB_PATH", str(tmp_path / "wf.db"))
    
    from fastapi.testclient import TestClient
    from backend.server import app
    
    audio = tmp_path / "test.m4a"
    audio.write_bytes(b"\x00" * 100)
    
    client = TestClient(app)
    with patch("backend.server.asyncio.create_task") as mock_bg:
        resp = client.post(
            "/api/procesar-paciente",
            files={"audio": ("test.m4a", open(audio, "rb"), "audio/m4a")},
            data={"paciente_cc": "1193143688"},
        )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["task_id"]


def test_endpoint_estado_task_devuelve_progreso(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKFLOW_DB_PATH", str(tmp_path / "wf.db"))
    from backend.task_db import TaskDB
    db = TaskDB(str(tmp_path / "wf.db"))
    tid = db.crear_task("123", "/tmp/a.m4a")
    db.actualizar_paso(tid, paso=3, estado="leyendo_notas")
    
    from fastapi.testclient import TestClient
    from backend.server import app
    resp = TestClient(app).get(f"/api/tasks/{tid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task"]["estado"] == "leyendo_notas"
    assert data["task"]["paso_actual"] == 3
```

(Necesitas import `from unittest.mock import patch` arriba si no está.)

- [ ] **Step 2: Tests fallan**

```bash
pytest tests/test_workflow_runner.py -v
```

- [ ] **Step 3: Agregar endpoints a `backend/server.py`**

Después de los endpoints existentes, agregar:

```python
# ─── Tomy Completo: workflow endpoints ─────────────────────────

WORKFLOW_AUDIOS_DIR = STORAGE / "workflow_audios"
WORKFLOW_AUDIOS_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/api/procesar-paciente")
async def procesar_paciente(
    audio: UploadFile = File(...),
    paciente_cc: str = Form(...),
):
    """
    Endpoint principal: Sandra sube audio + CC.
    Se crea task, se guarda audio, se dispara workflow en background.
    Devuelve task_id para que el dashboard haga polling.
    """
    if os.getenv("TOMY_COMPLETO_ENABLED", "false").lower() != "true":
        raise HTTPException(503, "Tomy Completo no habilitado (TOMY_COMPLETO_ENABLED=false)")
    
    # Guardar audio en storage/workflow_audios/{cc}_{timestamp}.{ext}
    ext = Path(audio.filename or "audio.m4a").suffix or ".m4a"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_path = WORKFLOW_AUDIOS_DIR / f"{paciente_cc}_{timestamp}{ext}"
    contenido = await audio.read()
    audio_path.write_bytes(contenido)
    
    # Crear task y disparar workflow en background
    from backend.task_db import TaskDB
    from backend.workflow_runner import ejecutar_workflow
    
    db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
    db = TaskDB(db_path)
    task_id = db.crear_task(paciente_cc=paciente_cc, audio_path=str(audio_path))
    
    # Ejecutar en thread separado (workflow es síncrono)
    import threading
    def _runner():
        try:
            ejecutar_workflow(audio_path=str(audio_path), paciente_cc=paciente_cc, task_id_existente=task_id)
        except Exception as e:
            print(f"[WORKFLOW BG] error: {e}", file=__import__("sys").stderr)
    threading.Thread(target=_runner, daemon=True).start()
    
    return {
        "ok": True,
        "task_id": task_id,
        "audio_path": str(audio_path),
        "mensaje": f"Procesamiento iniciado. Te aviso por Telegram en 10-20 min. Mientras, ver progreso en /api/tasks/{task_id}",
    }


@app.get("/api/tasks/{task_id}")
def estado_task(task_id: str):
    """Estado actual de un workflow task."""
    from backend.task_db import TaskDB
    db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
    db = TaskDB(db_path)
    task = db.obtener_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} no encontrada")
    return {"ok": True, "task": task}


@app.get("/api/tasks/paciente/{cc}")
def listar_tasks_paciente(cc: str):
    """Historial de workflows del paciente."""
    from backend.task_db import TaskDB
    db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
    db = TaskDB(db_path)
    return {"ok": True, "tasks": db.listar_tasks_paciente(cc)}


@app.get("/api/tasks/activas")
def listar_activas():
    """Tasks actualmente en proceso (dashboard 'Mi Día')."""
    from backend.task_db import TaskDB
    db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
    db = TaskDB(db_path)
    return {"ok": True, "tasks": db.listar_activos()}


@app.post("/api/tasks/{task_id}/cancelar")
def cancelar_task(task_id: str):
    """Cancela una task (marca como cancelado; el thread sigue pero el dashboard no lo muestra)."""
    from backend.task_db import TaskDB
    db_path = os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db")
    db = TaskDB(db_path)
    db.guardar_resultado(task_id, {"cancelado_por_usuario": True}, estado="cancelado")
    return {"ok": True, "mensaje": "Task cancelada"}
```

- [ ] **Step 4: Tests pasan**

```bash
pytest tests/test_workflow_runner.py -v
```

- [ ] **Step 5: Sanity check**

```bash
python3 -c "
from backend.server import app
routes = [r.path for r in app.routes if hasattr(r, 'path') and 'task' in r.path.lower() or 'procesar' in r.path]
for r in sorted(routes): print(r)
"
```

Expected: imprime `/api/procesar-paciente`, `/api/tasks/{task_id}`, etc.

- [ ] **Step 6: Commit**

```bash
git add backend/server.py tests/test_workflow_runner.py
git commit -m "🔌 server: endpoints workflow (procesar-paciente + tasks)"
```

---

# PARTE 4: Organizar formatos crudos (Task 12)

## Task 12: `organizador_formato.py` + endpoint + acceso desde chat

**Files:**
- Create: `backend/organizador_formato.py`
- Create: `tests/test_organizador_formato.py`
- Modify: `backend/server.py` (endpoint)
- Modify: `backend/chat_handler.py` (detección comando "organiza")

- [ ] **Step 1: Test**

`tests/test_organizador_formato.py`:

```python
"""Tests para organizador_formato.py."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_organiza_formato_crudo(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    
    from docx import Document
    crudo = tmp_path / "crudo.docx"
    doc = Document()
    doc.add_paragraph("Paciente Juan, dolor lumbar, dice que le duele al agacharse")
    doc.add_paragraph("Empresa: ACME")
    doc.save(str(crudo))
    
    with patch("backend.organizador_formato._llamar_llm_organizador") as mock_llm:
        mock_llm.return_value = {
            "ok": True,
            "datos_organizados": {
                "paciente": {"nombre": "JUAN", "documento": "1193143688"},
                "diagnostico": "Dolor lumbar",
            },
            "campos_faltantes": ["empresa.nit", "siniestro.id_siniestro"],
        }
        from backend.organizador_formato import organizar_formato
        resultado = organizar_formato(str(crudo), paciente_cc="1193143688")
    
    assert resultado["ok"]
    assert resultado["datos_organizados"]["paciente"]["nombre"] == "JUAN"
    assert "empresa.nit" in resultado["campos_faltantes"]
```

- [ ] **Step 2: Implementar `backend/organizador_formato.py`**

```python
"""
Organiza un formato crudo (DOCX desorganizado/incompleto que Sandra subió)
cruzándolo con datos verificados (si existen) y devuelve estructura limpia.

Caso de uso: Sandra encuentra un formato antiguo de un paciente con info
suelta y le pide a Tomy "organízame este formato".
"""
import json
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict


def _log(msg: str):
    print(f"[ORGANIZA {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _leer_docx_completo(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    lines = []
    for p in doc.paragraphs:
        if p.text.strip():
            lines.append(p.text)
    for tabla in doc.tables:
        for row in tabla.rows:
            celdas = [c.text.strip()[:80] for c in row.cells if c.text.strip()]
            if celdas:
                lines.append(" | ".join(celdas))
    return "\n".join(lines)


PROMPT_ORGANIZADOR = """Eres Tomy. Sandra te pasó este formato antiguo de un paciente. Está
desorganizado y le falta información. Tu tarea:

1. EXTRAER toda la información estructurada que puedas (datos del paciente, diagnóstico, etc.).
2. CRUZAR con los datos verificados de portales que te paso (si están).
3. DETECTAR campos faltantes críticos.
4. REPORTAR contradicciones (si dice algo distinto al portal).

Devuelve SOLO un JSON entre ```json ... ``` con esta estructura:

```json
{
  "datos_organizados": {
    "paciente": {...},
    "empresa": {...},
    "siniestro": {...},
    "diagnostico": "...",
    "secciones_libres": {"metodologia": "...", "observaciones": "..."}
  },
  "campos_faltantes": ["lista de paths críticos faltantes"],
  "contradicciones": [{"campo": "...", "formato_dice": "...", "portal_dice": "..."}],
  "confianza_global": 0.0-1.0
}
```"""


def _llamar_llm_organizador(contexto: str, paciente_cc: str) -> Dict:
    """Llama lote_worker --tipo sintetizar para organizar."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write(contexto)
        ctx_file = tmp.name
    
    modelo = os.getenv("LLM_MODEL_SINTESIS", "deepseek-v4-pro")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "backend.lote_worker",
             "--tipo", "sintetizar",
             "--modelo", modelo,
             "--mensaje", PROMPT_ORGANIZADOR,
             "--contexto-file", ctx_file,
             "--cc", paciente_cc],
            capture_output=True, text=True, timeout=300,
            cwd=str(Path(__file__).parent.parent),
        )
    finally:
        try: os.unlink(ctx_file)
        except: pass
    
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr[:500]}
    
    resultado = json.loads(proc.stdout)
    respuesta = resultado.get("respuesta", "")
    
    import re
    match = re.search(r'```json\s*(\{.*?\})\s*```', respuesta, re.DOTALL)
    if not match:
        return {"ok": False, "error": "LLM no devolvió JSON parseable"}
    
    datos = json.loads(match.group(1))
    return {
        "ok": True,
        "datos_organizados": datos.get("datos_organizados", {}),
        "campos_faltantes": datos.get("campos_faltantes", []),
        "contradicciones": datos.get("contradicciones", []),
        "confianza_global": datos.get("confianza_global", 0.5),
    }


def organizar_formato(docx_path: str, paciente_cc: str) -> Dict:
    """Función principal. Devuelve dict con datos organizados + reportes."""
    path = Path(docx_path)
    if not path.exists():
        return {"ok": False, "error": f"Archivo no existe: {docx_path}"}
    
    contenido_crudo = _leer_docx_completo(path)
    _log(f"Crudo: {len(contenido_crudo)} chars de {path.name}")
    
    # Cargar datos verificados si existen
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    json_files = sorted((storage / "data").glob(f"*{paciente_cc}*completo.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    datos_verificados = {}
    if json_files:
        with open(json_files[0], encoding="utf-8") as f:
            datos_verificados = json.load(f)
    
    contexto = f"""═══ FORMATO CRUDO DE SANDRA ({path.name}) ═══
{contenido_crudo}

═══ DATOS VERIFICADOS DE PORTALES (CC {paciente_cc}) ═══
{json.dumps(datos_verificados, ensure_ascii=False, indent=2) if datos_verificados else '[NO DISPONIBLES]'}
"""
    
    return _llamar_llm_organizador(contexto, paciente_cc)
```

- [ ] **Step 3: Tests pasan**

```bash
pytest tests/test_organizador_formato.py -v
```

- [ ] **Step 4: Endpoint en `server.py`**

```python
@app.post("/api/organizar-formato")
async def endpoint_organizar_formato(
    archivo: UploadFile = File(...),
    paciente_cc: str = Form(...),
):
    """Sandra sube un formato crudo, Tomy lo organiza."""
    ext = Path(archivo.filename or "f.docx").suffix
    tmp_path = STORAGE / "formatos_subidos" / f"organizar_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_bytes(await archivo.read())
    
    from backend.organizador_formato import organizar_formato
    resultado = organizar_formato(str(tmp_path), paciente_cc)
    return resultado
```

- [ ] **Step 5: Detección en `chat_handler.py`**

En `procesar_mensaje`, antes del paso 5 (llamar LLM):

```python
    # NUEVO: detectar comando "organiza este formato"
    if any(kw in mensaje.lower() for kw in ["organiza este formato", "organízame este", "organizame el formato"]):
        archivo = _buscar_archivo(mensaje)
        if archivo and cc:
            from backend.organizador_formato import organizar_formato
            resultado_org = organizar_formato(str(archivo), cc)
            if resultado_org.get("ok"):
                doc_content = (doc_content or "") + f"\n\n[FORMATO ORGANIZADO]:\n{json.dumps(resultado_org, ensure_ascii=False, indent=2)}"
```

- [ ] **Step 6: Commit**

```bash
git add backend/organizador_formato.py tests/test_organizador_formato.py backend/server.py backend/chat_handler.py
git commit -m "📝 organizador_formato: reorganiza DOCX crudos cruzando con verificados"
```

---

# PARTE 5: Loop de corrección conversacional (Tasks 13-14)

## Task 13: `correction_resolver.py`

**Files:**
- Create: `backend/correction_resolver.py`
- Create: `tests/test_correction_resolver.py`

- [ ] **Step 1: Test**

```python
"""Tests para correction_resolver."""
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_extrae_correccion_simple():
    """'el siniestro no es X es Y' → (siniestro, X, Y)"""
    from backend.correction_resolver import interpretar_correccion
    
    with patch("backend.correction_resolver._llamar_llm_clasificador") as mock_llm:
        mock_llm.return_value = {
            "campo": "siniestro.id_siniestro",
            "valor_nuevo": "503476658",
            "valor_anterior": "503463870",
            "confianza": 0.9,
        }
        r = interpretar_correccion("el siniestro no es 503463870 es 503476658", paciente_cc="1193143688")
    
    assert r["campo"] == "siniestro.id_siniestro"
    assert r["valor_nuevo"] == "503476658"


def test_extrae_correccion_campo_libre():
    from backend.correction_resolver import interpretar_correccion
    with patch("backend.correction_resolver._llamar_llm_clasificador") as mock_llm:
        mock_llm.return_value = {
            "campo": "metodologia",
            "valor_nuevo": "Observación directa de la tarea por 2 horas",
            "valor_anterior": None,
            "confianza": 0.7,
        }
        r = interpretar_correccion("la metodología es observación directa por 2 horas", paciente_cc="1193143688")
    assert r["campo"] == "metodologia"
```

- [ ] **Step 2: Tests fallan**

```bash
pytest tests/test_correction_resolver.py -v
```

- [ ] **Step 3: Implementar `backend/correction_resolver.py`**

```python
"""
Resolver de correcciones conversacionales.

Sandra escribe en el chat algo como "el siniestro no es X es Y", y este
módulo identifica:
  - Qué campo en la estructura clínica
  - Cuál es el nuevo valor
  - Cuál era el valor anterior (para validar)
  - Nivel de confianza

Usa LLM clasificador (deepseek-v4-flash, sin razonamiento).
"""
import json
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional


def _log(msg: str):
    print(f"[CORRECTION {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


PROMPT_CLASIFICADOR = """Eres Tomy. Sandra acaba de escribirte una corrección sobre un paciente.

Tu tarea: identificar QUÉ campo de la estructura clínica está corrigiendo, cuál es el valor nuevo,
y opcionalmente cuál era el valor anterior. Devuelve SOLO un JSON entre ```json ... ```.

Estructura clínica posible (campos válidos):
  paciente.documento, paciente.nombre, paciente.edad, paciente.telefono, paciente.direccion,
  paciente.email, paciente.eps_ips, paciente.afp, paciente.ocupacion,
  empresa.nombre, empresa.nit, empresa.cargo,
  siniestro.id_siniestro, siniestro.fecha_evento, siniestro.tipo_evento, siniestro.diagnostico_cie10,
  estado_caso,
  metodologia, proceso_productivo, apreciacion_trabajador,
  concepto_desempeno, recomendaciones.trabajador, recomendaciones.empresa,
  logros, obstaculos

Formato salida:
```json
{
  "campo": "siniestro.id_siniestro",
  "valor_nuevo": "503476658",
  "valor_anterior": "503463870",
  "confianza": 0.9,
  "razonamiento": "1 línea"
}
```

Si no logras identificar el campo o el valor, pon confianza < 0.5."""


def _llamar_llm_clasificador(mensaje: str, paciente_cc: str) -> Dict:
    modelo = os.getenv("LLM_MODEL_EXTRACCION", "deepseek-v4-flash")
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write(f"Mensaje de Sandra: \"{mensaje}\"\nCC del paciente: {paciente_cc}")
        ctx_file = tmp.name
    
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "backend.lote_worker",
             "--tipo", "sintetizar",
             "--modelo", modelo,
             "--mensaje", PROMPT_CLASIFICADOR,
             "--contexto-file", ctx_file,
             "--cc", paciente_cc],
            capture_output=True, text=True, timeout=60,
            cwd=str(Path(__file__).parent.parent),
        )
    finally:
        try: os.unlink(ctx_file)
        except: pass
    
    if proc.returncode != 0:
        return {"campo": None, "confianza": 0, "error": proc.stderr[:200]}
    
    resultado = json.loads(proc.stdout)
    respuesta = resultado.get("respuesta", "")
    
    import re
    match = re.search(r'```json\s*(\{.*?\})\s*```', respuesta, re.DOTALL)
    if not match:
        return {"campo": None, "confianza": 0, "error": "no JSON"}
    
    return json.loads(match.group(1))


def interpretar_correccion(mensaje: str, paciente_cc: str) -> Dict:
    """Interpreta el mensaje y devuelve dict {campo, valor_nuevo, valor_anterior, confianza}."""
    return _llamar_llm_clasificador(mensaje, paciente_cc)
```

- [ ] **Step 4: Tests pasan**

```bash
pytest tests/test_correction_resolver.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/correction_resolver.py tests/test_correction_resolver.py
git commit -m "🔍 correction_resolver: interpreta correcciones conversacionales de Sandra"
```

---

## Task 14: `aplicador_correccion.py` — actualiza JSON + regenera formatos

**Files:**
- Create: `backend/aplicador_correccion.py`
- Create: `tests/test_aplicador_correccion.py`
- Modify: `backend/server.py` (endpoint)

- [ ] **Step 1: Test**

```python
"""Tests para aplicador_correccion."""
import json
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_aplica_correccion_simple(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    json_path = data_dir / "1193143688-completo.json"
    json_path.write_text(json.dumps({
        "cc": "1193143688",
        "siniestro": {"id_siniestro": "503463870"},
        "_meta": {"correcciones": []}
    }), encoding="utf-8")
    
    from backend.aplicador_correccion import aplicar_correccion
    correccion = {"campo": "siniestro.id_siniestro", "valor_nuevo": "503476658", "valor_anterior": "503463870"}
    
    with patch("backend.aplicador_correccion._regenerar_formatos_afectados") as mock_regen:
        mock_regen.return_value = {"regenerados": [], "errores": []}
        resultado = aplicar_correccion(paciente_cc="1193143688", correccion=correccion)
    
    assert resultado["ok"]
    nuevo = json.loads(json_path.read_text())
    assert nuevo["siniestro"]["id_siniestro"] == "503476658"
    assert len(nuevo["_meta"]["correcciones"]) == 1


def test_aplicar_correccion_campo_inexistente_crea_ruta(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    json_path = data_dir / "123-completo.json"
    json_path.write_text(json.dumps({"cc": "123"}), encoding="utf-8")
    
    from backend.aplicador_correccion import aplicar_correccion
    correccion = {"campo": "metodologia", "valor_nuevo": "Nueva metodología"}
    
    with patch("backend.aplicador_correccion._regenerar_formatos_afectados") as mock_regen:
        mock_regen.return_value = {"regenerados": [], "errores": []}
        resultado = aplicar_correccion(paciente_cc="123", correccion=correccion)
    
    assert resultado["ok"]
    nuevo = json.loads(json_path.read_text())
    assert nuevo["metodologia"] == "Nueva metodología"
```

- [ ] **Step 2: Implementar**

```python
"""
Aplicador de correcciones a JSON del paciente + regenera formatos afectados.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def _log(msg: str):
    print(f"[APLICADOR {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


# Mapeo campo → formatos que lo usan (para regenerar solo los afectados)
CAMPO_FORMATOS = {
    "siniestro.": ["analisis", "medidas", "recomendaciones", "cierre", "prueba", "valoracion"],
    "paciente.": ["analisis", "medidas", "recomendaciones", "cierre", "citacion", "prueba", "valoracion"],
    "empresa.": ["analisis", "citacion", "valoracion"],
    "metodologia": ["analisis", "prueba"],
    "concepto_desempeno": ["valoracion", "cierre"],
    "recomendaciones.": ["medidas", "recomendaciones"],
    "logros": ["cierre"],
    "obstaculos": ["cierre"],
}


def _formatos_afectados(campo: str) -> List[str]:
    for key, formatos in CAMPO_FORMATOS.items():
        if campo.startswith(key) or campo == key.rstrip("."):
            return formatos
    return []  # campo desconocido → no regenera nada


def _set_anidado(d: dict, path: str, valor):
    """Asigna d.foo.bar = valor dado path = 'foo.bar'."""
    keys = path.split(".")
    cur = d
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = valor


def _regenerar_formatos_afectados(paciente_cc: str, formatos: List[str], datos: dict) -> Dict:
    """Regenera los formatos indicados con los datos actualizados."""
    if not formatos:
        return {"regenerados": [], "errores": []}
    
    from backend.workflow_steps.generar_formatos import generar_documento
    
    regenerados = []
    errores = []
    for fmt in formatos:
        try:
            output_name = f"{fmt}_{paciente_cc}_correccion_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            path = generar_documento(fmt, datos, output_name=output_name)
            regenerados.append({"formato": fmt, "archivo": path})
            _log(f"✅ regenerado {fmt}: {Path(path).name}")
        except Exception as e:
            errores.append({"formato": fmt, "error": f"{type(e).__name__}: {e}"})
            _log(f"❌ {fmt}: {e}")
    
    return {"regenerados": regenerados, "errores": errores}


def aplicar_correccion(paciente_cc: str, correccion: Dict) -> Dict:
    """
    Aplica corrección al JSON del paciente, regenera formatos afectados.
    correccion: {"campo": "siniestro.id_siniestro", "valor_nuevo": "...", "valor_anterior": "..."}
    """
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    json_files = sorted((storage / "data").glob(f"*{paciente_cc}*completo.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    if not json_files:
        return {"ok": False, "error": f"No hay JSON para CC {paciente_cc}"}
    
    json_path = json_files[0]
    with open(json_path, encoding="utf-8") as f:
        datos = json.load(f)
    
    campo = correccion.get("campo")
    valor_nuevo = correccion.get("valor_nuevo")
    
    if not campo or valor_nuevo is None:
        return {"ok": False, "error": "Corrección sin campo o valor_nuevo"}
    
    _set_anidado(datos, campo, valor_nuevo)
    
    # Registrar en _meta.correcciones
    meta = datos.setdefault("_meta", {})
    correcciones = meta.setdefault("correcciones", [])
    correcciones.append({
        "campo": campo,
        "valor_nuevo": valor_nuevo,
        "valor_anterior": correccion.get("valor_anterior"),
        "fuente": "manual_sandra",
        "timestamp": datetime.now().isoformat(),
    })
    
    json_path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"JSON actualizado: {campo} = {valor_nuevo}")
    
    # Regenerar formatos afectados
    formatos = _formatos_afectados(campo)
    regen = _regenerar_formatos_afectados(paciente_cc, formatos, datos)
    
    return {
        "ok": True,
        "campo_corregido": campo,
        "valor_nuevo": valor_nuevo,
        "formatos_regenerados": regen["regenerados"],
        "errores": regen["errores"],
    }
```

- [ ] **Step 3: Endpoint en `server.py`**

```python
class CorreccionRequest(BaseModel):
    mensaje: str


@app.post("/api/corregir-paciente/{cc}")
async def endpoint_corregir(cc: str, req: CorreccionRequest):
    """Sandra envía corrección por chat → Tomy interpreta y aplica."""
    from backend.correction_resolver import interpretar_correccion
    from backend.aplicador_correccion import aplicar_correccion
    
    correccion = interpretar_correccion(req.mensaje, paciente_cc=cc)
    if correccion.get("confianza", 0) < 0.5:
        return {
            "ok": False,
            "estado": "confianza_baja",
            "mensaje": "No entendí qué corregir. ¿Me lo decís de otra forma? Por ejemplo: 'el siniestro es 503476658'.",
            "interpretacion": correccion,
        }
    
    resultado = aplicar_correccion(cc, correccion)
    return resultado
```

- [ ] **Step 4: Tests pasan**

```bash
pytest tests/test_aplicador_correccion.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/aplicador_correccion.py tests/test_aplicador_correccion.py backend/server.py
git commit -m "✏️ aplicador_correccion: actualiza JSON + regenera formatos afectados"
```

---

# PARTE 6: Dashboard Sandra-first (Tasks 15-20)

## Task 15: Tipografía boomer-friendly + Sidebar limpio

**Files:**
- Modify: `dashboard/app/layout.tsx`
- Modify: `dashboard/components/Sidebar.tsx`
- Modify: `dashboard/app/globals.css`

- [ ] **Step 1: Modificar `dashboard/app/globals.css`**

Agregar al final:

```css
/* Tomy Completo — tipografía boomer-friendly */
:root {
  --tomy-text-base: 18px;
  --tomy-text-lg: 22px;
  --tomy-text-xl: 28px;
  --tomy-text-2xl: 36px;
}

html, body {
  font-size: var(--tomy-text-base);
  line-height: 1.6;
}

h1 { font-size: var(--tomy-text-2xl); font-weight: 700; }
h2 { font-size: var(--tomy-text-xl); font-weight: 600; }
h3 { font-size: var(--tomy-text-lg); font-weight: 600; }

button, a.button {
  min-height: 48px;
  padding: 12px 24px;
  font-size: var(--tomy-text-base);
}

input, textarea, select {
  font-size: var(--tomy-text-base);
  min-height: 48px;
  padding: 12px 16px;
}

.tomy-status-grande {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  font-size: var(--tomy-text-lg);
  padding: 8px 16px;
  border-radius: 12px;
}
.tomy-status-grande.ok { background: #dcfce7; color: #166534; }
.tomy-status-grande.warn { background: #fef3c7; color: #92400e; }
.tomy-status-grande.error { background: #fee2e2; color: #991b1b; }
.tomy-status-grande.progreso { background: #dbeafe; color: #1e40af; }
```

- [ ] **Step 2: Modificar Sidebar para iconos más grandes + sin jerga**

Editar `dashboard/components/Sidebar.tsx` — cambiar las etiquetas y aumentar iconos:

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

export default function Sidebar() {
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
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-4 px-4 py-3 rounded-xl text-lg transition-colors ${
              active
                ? "bg-blue-600 text-white"
                : "text-slate-700 hover:bg-slate-100"
            }`}
          >
            <Icon size={26} />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 3: Sanity check (compila Next.js)**

```bash
cd dashboard && npm run lint 2>&1 | tail -10
```

Expected: sin errores de TypeScript.

- [ ] **Step 4: Commit**

```bash
git add dashboard/app/globals.css dashboard/components/Sidebar.tsx
git commit -m "🎨 dashboard: tipografía boomer + sidebar con iconos grandes"
```

---

## Task 16: Componente `<BotonGigante />` + `<EstadoVisual />`

**Files:**
- Create: `dashboard/components/BotonGigante.tsx`
- Create: `dashboard/components/EstadoVisual.tsx`

- [ ] **Step 1: Crear `BotonGigante.tsx`**

```tsx
import { LucideIcon } from "lucide-react";

interface Props {
  label: string;
  sublabel?: string;
  icon?: LucideIcon;
  onClick?: () => void;
  href?: string;
  color?: "azul" | "verde" | "rojo" | "amarillo";
  disabled?: boolean;
  loading?: boolean;
}

const COLORS = {
  azul: "bg-blue-600 hover:bg-blue-700 text-white",
  verde: "bg-green-600 hover:bg-green-700 text-white",
  rojo: "bg-red-600 hover:bg-red-700 text-white",
  amarillo: "bg-amber-500 hover:bg-amber-600 text-white",
};

export function BotonGigante({ label, sublabel, icon: Icon, onClick, href, color = "azul", disabled, loading }: Props) {
  const className = `flex items-center justify-center gap-4 px-8 py-6 rounded-2xl shadow-md transition-all ${COLORS[color]} ${disabled || loading ? "opacity-50 cursor-not-allowed" : "active:scale-95"}`;
  
  const content = (
    <>
      {Icon && <Icon size={32} />}
      <div className="text-left">
        <p className="text-xl font-bold">{loading ? "Procesando..." : label}</p>
        {sublabel && <p className="text-sm opacity-90">{sublabel}</p>}
      </div>
    </>
  );
  
  if (href && !disabled) {
    return <a href={href} className={className}>{content}</a>;
  }
  return <button onClick={onClick} disabled={disabled || loading} className={className}>{content}</button>;
}
```

- [ ] **Step 2: Crear `EstadoVisual.tsx`**

```tsx
import { CheckCircle, AlertCircle, Clock, XCircle, Loader2 } from "lucide-react";

type Estado = "ok" | "progreso" | "warn" | "error";

interface Props {
  estado: Estado;
  titulo: string;
  detalle?: string;
}

export function EstadoVisual({ estado, titulo, detalle }: Props) {
  const config = {
    ok: { Icon: CheckCircle, color: "text-green-600", bg: "bg-green-50 border-green-200" },
    progreso: { Icon: Loader2, color: "text-blue-600 animate-spin", bg: "bg-blue-50 border-blue-200" },
    warn: { Icon: AlertCircle, color: "text-amber-600", bg: "bg-amber-50 border-amber-200" },
    error: { Icon: XCircle, color: "text-red-600", bg: "bg-red-50 border-red-200" },
  }[estado];
  
  return (
    <div className={`flex items-start gap-4 p-5 rounded-xl border-2 ${config.bg}`}>
      <config.Icon size={36} className={config.color} />
      <div>
        <p className="text-xl font-semibold text-slate-800">{titulo}</p>
        {detalle && <p className="text-base text-slate-600 mt-1">{detalle}</p>}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/BotonGigante.tsx dashboard/components/EstadoVisual.tsx
git commit -m "🎨 components: BotonGigante + EstadoVisual (boomer-friendly)"
```

---

## Task 17: Vista "Mi Día" (`/hoy`)

**Files:**
- Create: `dashboard/app/hoy/page.tsx`

- [ ] **Step 1: Crear `dashboard/app/hoy/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { EstadoVisual } from "@/components/EstadoVisual";
import { BotonGigante } from "@/components/BotonGigante";
import { Mic, Calendar, User } from "lucide-react";

interface Cita {
  hora: string;
  paciente: string;
  cc?: string;
  procesado?: boolean;
}

interface TaskActiva {
  task_id: string;
  paciente_cc: string;
  estado: string;
  paso_actual: number;
}

export default function HoyPage() {
  const [citas, setCitas] = useState<Cita[]>([]);
  const [tasksActivas, setTasksActivas] = useState<TaskActiva[]>([]);
  const [cargando, setCargando] = useState(true);
  
  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [rAgenda, rTasks] = await Promise.all([
          fetch("http://localhost:8000/api/agenda"),
          fetch("http://localhost:8000/api/tasks/activas"),
        ]);
        const agenda = rAgenda.ok ? await rAgenda.json() : {citas:[]};
        const tasks = rTasks.ok ? await rTasks.json() : {tasks:[]};
        setCitas(agenda.citas || []);
        setTasksActivas(tasks.tasks || []);
      } finally { setCargando(false); }
    };
    fetchAll();
    const intervalo = setInterval(fetchAll, 5000); // refresh cada 5s
    return () => clearInterval(intervalo);
  }, []);
  
  return (
    <div className="space-y-8 max-w-5xl mx-auto p-6">
      <header>
        <h1 className="text-4xl font-bold text-slate-800 mb-2">Mi día, Sandra</h1>
        <p className="text-lg text-slate-500">
          {new Date().toLocaleDateString("es-CO", {weekday: "long", day: "numeric", month: "long"})}
        </p>
      </header>
      
      <section>
        <BotonGigante
          label="Subir audio de una consulta"
          sublabel="Toma 10-20 min en procesarse"
          icon={Mic}
          href="/subir-audio"
          color="azul"
        />
      </section>
      
      {tasksActivas.length > 0 && (
        <section>
          <h2 className="text-2xl font-semibold mb-4">⏳ Procesando ahora</h2>
          <div className="space-y-3">
            {tasksActivas.map(t => (
              <div key={t.task_id} className="bg-blue-50 border-2 border-blue-200 p-5 rounded-xl">
                <p className="text-lg font-medium">CC {t.paciente_cc}</p>
                <p className="text-base text-blue-700">Paso {t.paso_actual}/9: {t.estado}</p>
                <a href={`/paciente/${t.paciente_cc}`} className="text-blue-600 underline mt-2 inline-block">
                  Ver progreso →
                </a>
              </div>
            ))}
          </div>
        </section>
      )}
      
      <section>
        <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
          <Calendar size={28} /> Citas de hoy
        </h2>
        {cargando ? (
          <p className="text-slate-500">Cargando agenda...</p>
        ) : citas.length === 0 ? (
          <EstadoVisual estado="warn" titulo="No tengo agenda cargada" detalle="¿Querés revisar tu Gmail?" />
        ) : (
          <div className="space-y-3">
            {citas.map((c, i) => (
              <a key={i} href={c.cc ? `/paciente/${c.cc}` : "#"} className="flex items-center gap-4 p-5 bg-white border-2 border-slate-200 rounded-xl hover:border-blue-400 transition-colors">
                <div className="bg-blue-100 text-blue-700 px-4 py-2 rounded-lg text-xl font-bold">{c.hora}</div>
                <div className="flex-1">
                  <p className="text-xl font-medium">{c.paciente}</p>
                  {c.cc && <p className="text-sm text-slate-500">CC {c.cc}</p>}
                </div>
                {c.procesado && <span className="text-green-600 text-lg">✅ Listo</span>}
              </a>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/app/hoy/page.tsx
git commit -m "🎨 dashboard: vista 'Mi día' con citas + tasks activas en tiempo real"
```

---

## Task 18: Vista Paciente 360 (`/paciente/[cc]`)

**Files:**
- Create: `dashboard/app/paciente/[cc]/page.tsx`
- Create: `dashboard/components/TimelinePaciente.tsx`
- Create: `dashboard/components/FormatoCard.tsx`

- [ ] **Step 1: Crear `TimelinePaciente.tsx`**

```tsx
import { CheckCircle, Circle, Loader2 } from "lucide-react";

const PASOS = [
  "Pendiente",
  "Transcribiendo audio",
  "Buscando en portales",
  "Leyendo notas",
  "Leyendo formatos subidos",
  "Cruzando información",
  "Generando documentos",
  "Verificando calidad",
  "Generando PDFs",
  "Notificando",
];

export function TimelinePaciente({ pasoActual, estado }: { pasoActual: number; estado: string }) {
  return (
    <div className="space-y-2">
      {PASOS.slice(1).map((paso, idx) => {
        const num = idx + 1;
        const completo = num < pasoActual;
        const actual = num === pasoActual;
        const Icon = completo ? CheckCircle : actual ? Loader2 : Circle;
        return (
          <div key={num} className={`flex items-center gap-3 ${completo ? "text-green-600" : actual ? "text-blue-600" : "text-slate-400"}`}>
            <Icon size={22} className={actual ? "animate-spin" : ""} />
            <span className={`text-base ${actual ? "font-semibold" : ""}`}>
              {num}. {paso}
            </span>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Crear `FormatoCard.tsx`**

```tsx
import { useState } from "react";
import { FileText, Download, CheckCircle, AlertCircle, Edit3 } from "lucide-react";

interface Props {
  nombre: string;
  archivoDocx?: string;
  archivoPdf?: string;
  qaOk?: boolean;
  qaWarnings?: string[];
  onAprobar?: () => void;
  onCorregir?: () => void;
}

export function FormatoCard({ nombre, archivoDocx, archivoPdf, qaOk, qaWarnings, onAprobar, onCorregir }: Props) {
  const [aprobado, setAprobado] = useState(false);
  
  return (
    <div className={`p-6 bg-white border-2 rounded-2xl shadow-sm ${aprobado ? "border-green-400 bg-green-50" : qaOk === false ? "border-amber-400" : "border-slate-200"}`}>
      <div className="flex items-start gap-4">
        <FileText size={36} className={aprobado ? "text-green-600" : "text-blue-600"} />
        <div className="flex-1">
          <h3 className="text-xl font-semibold text-slate-800">{nombre}</h3>
          {qaWarnings && qaWarnings.length > 0 && (
            <p className="text-sm text-amber-600 mt-1 flex items-center gap-1">
              <AlertCircle size={14} /> {qaWarnings.length} advertencia(s)
            </p>
          )}
          {aprobado && (
            <p className="text-sm text-green-600 mt-1 flex items-center gap-1">
              <CheckCircle size={14} /> Aprobado
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {archivoDocx && (
            <a href={`http://localhost:8000/api/download/${encodeURIComponent(archivoDocx.split("/").pop() || "")}`} download
               className="p-3 bg-slate-100 hover:bg-slate-200 rounded-lg" title="Descargar DOCX">
              <Download size={20} />
            </a>
          )}
        </div>
      </div>
      
      {!aprobado && (
        <div className="flex gap-3 mt-4">
          <button onClick={() => { setAprobado(true); onAprobar?.(); }}
                  className="flex-1 px-6 py-3 bg-green-600 hover:bg-green-700 text-white rounded-xl text-lg font-semibold flex items-center justify-center gap-2">
            <CheckCircle size={20} /> Aprobar
          </button>
          <button onClick={onCorregir}
                  className="flex-1 px-6 py-3 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-lg font-semibold flex items-center justify-center gap-2">
            <Edit3 size={20} /> Corregir
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Crear `dashboard/app/paciente/[cc]/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { EstadoVisual } from "@/components/EstadoVisual";
import { TimelinePaciente } from "@/components/TimelinePaciente";
import { FormatoCard } from "@/components/FormatoCard";

export default function PacientePage() {
  const { cc } = useParams<{cc: string}>();
  const [paciente, setPaciente] = useState<any>(null);
  const [tasks, setTasks] = useState<any[]>([]);
  const [taskActiva, setTaskActiva] = useState<any>(null);
  const [correccion, setCorreccion] = useState("");
  const [enviandoCorreccion, setEnviandoCorreccion] = useState(false);
  
  useEffect(() => {
    const cargar = async () => {
      const [rP, rT] = await Promise.all([
        fetch(`http://localhost:8000/api/pacientes/${cc}`),
        fetch(`http://localhost:8000/api/tasks/paciente/${cc}`),
      ]);
      if (rP.ok) setPaciente(await rP.json());
      if (rT.ok) {
        const data = await rT.json();
        setTasks(data.tasks || []);
        const activa = (data.tasks || []).find((t: any) =>
          !["listo", "cancelado"].includes(t.estado) && !t.estado.startsWith("error_")
        );
        setTaskActiva(activa);
      }
    };
    cargar();
    const interval = setInterval(cargar, 3000);
    return () => clearInterval(interval);
  }, [cc]);
  
  const enviarCorreccion = async () => {
    if (!correccion.trim()) return;
    setEnviandoCorreccion(true);
    try {
      const resp = await fetch(`http://localhost:8000/api/corregir-paciente/${cc}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensaje: correccion }),
      });
      const data = await resp.json();
      if (data.ok) {
        alert(`✅ Corregí "${data.campo_corregido}". Se regeneraron ${data.formatos_regenerados?.length || 0} formatos.`);
        setCorreccion("");
      } else {
        alert(`No entendí. ${data.mensaje || ""}`);
      }
    } finally {
      setEnviandoCorreccion(false);
    }
  };
  
  if (!paciente) return <div className="p-8 text-xl">Cargando paciente...</div>;
  
  const ultimaTask = tasks[0];
  const formatos = ultimaTask?.resultado?.formatos_generados || [];
  
  return (
    <div className="max-w-5xl mx-auto p-6 space-y-8">
      {/* Header del paciente */}
      <header className="bg-gradient-to-r from-blue-600 to-blue-700 text-white p-6 rounded-2xl">
        <h1 className="text-3xl font-bold">{paciente.nombre || `CC ${cc}`}</h1>
        <p className="text-blue-100 text-lg mt-1">CC {cc} · {paciente.edad || "?"} años</p>
        {paciente.empresa && <p className="text-blue-100">Empresa: {paciente.empresa}</p>}
      </header>
      
      {/* Task activa */}
      {taskActiva && (
        <section className="bg-blue-50 border-2 border-blue-200 p-6 rounded-2xl">
          <h2 className="text-2xl font-semibold mb-4">⏳ Tomy está trabajando…</h2>
          <TimelinePaciente pasoActual={taskActiva.paso_actual} estado={taskActiva.estado} />
        </section>
      )}
      
      {/* Formatos generados */}
      {formatos.length > 0 && (
        <section>
          <h2 className="text-2xl font-semibold mb-4">Documentos generados</h2>
          <div className="space-y-4">
            {formatos.map((f: any, i: number) => (
              <FormatoCard
                key={i}
                nombre={f.formato}
                archivoDocx={f.archivo}
                qaOk={f.qa_ok}
                qaWarnings={f.qa_warnings}
                onCorregir={() => {
                  const el = document.getElementById("correccion-input");
                  el?.scrollIntoView({ behavior: "smooth" });
                  el?.focus();
                }}
              />
            ))}
          </div>
        </section>
      )}
      
      {/* Corrección rápida */}
      <section>
        <h2 className="text-2xl font-semibold mb-4">Corregir algo</h2>
        <p className="text-base text-slate-600 mb-2">
          Decime qué corregir, por ejemplo: "el siniestro es 503476658" o "la empresa se llama Acme S.A.S."
        </p>
        <textarea
          id="correccion-input"
          value={correccion}
          onChange={(e) => setCorreccion(e.target.value)}
          className="w-full p-4 border-2 border-slate-300 rounded-xl text-lg"
          rows={3}
          placeholder="Escribe la corrección aquí…"
        />
        <button
          onClick={enviarCorreccion}
          disabled={enviandoCorreccion || !correccion.trim()}
          className="mt-3 px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-lg font-semibold disabled:opacity-50"
        >
          {enviandoCorreccion ? "Aplicando..." : "Aplicar corrección"}
        </button>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Sanity check Next.js compila**

```bash
cd dashboard && npm run lint 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/app/paciente/ dashboard/components/TimelinePaciente.tsx dashboard/components/FormatoCard.tsx
git commit -m "🎨 dashboard: vista Paciente 360 (timeline + formatos + correcciones)"
```

---

## Task 19: Simplificar `/subir-audio` (drag & drop gigante)

**Files:**
- Modify: `dashboard/app/subir-audio/page.tsx`

- [ ] **Step 1: Reescribir `dashboard/app/subir-audio/page.tsx`**

Reemplazo total para UX gigante boomer-friendly:

```tsx
"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Upload, Mic, Loader2 } from "lucide-react";
import { BotonGigante } from "@/components/BotonGigante";
import { EstadoVisual } from "@/components/EstadoVisual";

export default function SubirAudioPage() {
  const router = useRouter();
  const [archivo, setArchivo] = useState<File | null>(null);
  const [cc, setCc] = useState("");
  const [subiendo, setSubiendo] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  
  const handleFile = (file: File | null) => {
    if (!file) return;
    setArchivo(file);
    setError("");
  };
  
  const subir = async () => {
    if (!archivo || !cc.trim()) {
      setError("Necesito el audio y la cédula del paciente.");
      return;
    }
    setSubiendo(true);
    setError("");
    try {
      const form = new FormData();
      form.append("audio", archivo);
      form.append("paciente_cc", cc.trim());
      
      const resp = await fetch("http://localhost:8000/api/procesar-paciente", {
        method: "POST",
        body: form,
      });
      if (!resp.ok) throw new Error(`Error ${resp.status}`);
      const data = await resp.json();
      
      // Redirigir a la vista 360 del paciente
      router.push(`/paciente/${cc.trim()}`);
    } catch (e) {
      setError(`No pude subir el audio. ${e instanceof Error ? e.message : ""}`);
      setSubiendo(false);
    }
  };
  
  return (
    <div className="max-w-3xl mx-auto p-6 space-y-8">
      <header>
        <h1 className="text-4xl font-bold">Subir audio de una consulta</h1>
        <p className="text-lg text-slate-600 mt-2">
          Voy a transcribir, organizar y generar los documentos. Toma 10-20 minutos.
          Te aviso por Telegram cuando esté listo.
        </p>
      </header>
      
      {/* Paso 1: CC */}
      <section>
        <label className="block text-xl font-semibold mb-3">
          1. ¿De qué paciente es este audio?
        </label>
        <input
          type="text"
          value={cc}
          onChange={(e) => setCc(e.target.value)}
          placeholder="Escribe la cédula"
          className="w-full p-5 text-2xl border-2 border-slate-300 rounded-xl focus:border-blue-500 outline-none"
        />
      </section>
      
      {/* Paso 2: Audio */}
      <section>
        <label className="block text-xl font-semibold mb-3">
          2. Carga el audio de la consulta
        </label>
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); handleFile(e.dataTransfer.files?.[0] || null); }}
          onClick={() => inputRef.current?.click()}
          className="border-4 border-dashed border-slate-300 hover:border-blue-400 rounded-3xl p-16 text-center cursor-pointer transition-colors"
        >
          <input
            ref={inputRef}
            type="file"
            accept="audio/*,.m4a,.mp3,.wav"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0] || null)}
          />
          {archivo ? (
            <div className="space-y-4">
              <Mic size={80} className="text-green-600 mx-auto" />
              <p className="text-2xl font-semibold">{archivo.name}</p>
              <p className="text-lg text-slate-500">
                {(archivo.size / 1024 / 1024).toFixed(1)} MB · Listo para procesar
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <Upload size={80} className="text-slate-400 mx-auto" />
              <p className="text-2xl font-semibold text-slate-700">
                Arrastra el audio aquí o haz click
              </p>
              <p className="text-lg text-slate-500">M4A, MP3, WAV — sin límite de tamaño</p>
            </div>
          )}
        </div>
      </section>
      
      {error && <EstadoVisual estado="error" titulo="Algo salió mal" detalle={error} />}
      
      <BotonGigante
        label="Procesar paciente"
        sublabel="Tomy hace todo el resto"
        icon={Mic}
        color="verde"
        onClick={subir}
        disabled={!archivo || !cc.trim()}
        loading={subiendo}
      />
    </div>
  );
}
```

- [ ] **Step 2: Sanity check + Commit**

```bash
cd dashboard && npm run lint 2>&1 | tail -5 && cd ..
git add dashboard/app/subir-audio/page.tsx
git commit -m "🎨 subir-audio: drag&drop gigante + redirige a paciente 360"
```

---

## Task 20: Ajustar Home → redirigir a `/hoy`

**Files:**
- Modify: `dashboard/app/page.tsx`

- [ ] **Step 1: Reemplazar Home con redirect**

`dashboard/app/page.tsx`:

```tsx
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
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/app/page.tsx
git commit -m "🎨 home: redirige a /hoy como landing principal"
```

---

# PARTE 7: Casos alternos (Tasks 21-22)

## Task 21: Workflow maneja paciente fuera de agenda + portal caído

Ya implícito en `resolver_paciente.py` (Task 4) y `playwright_real/session.py`. Esta task valida con tests.

**Files:**
- Create: `tests/test_casos_alternos.py`

- [ ] **Step 1: Tests**

```python
"""Tests para casos alternos del workflow."""
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_workflow_continua_sin_portales_si_falla(tmp_path, monkeypatch):
    """Si Playwright falla, resolver_paciente devuelve vacío y el workflow continúa."""
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("FASE_A_ENABLED", "true")
    
    with patch("backend.playwright_real.orquestador.extraer_paciente_completo", new_callable=AsyncMock) as mock_ex:
        mock_ex.side_effect = RuntimeError("Portal caído")
        from backend.workflow_steps.resolver_paciente import resolver_paciente
        datos, fuente = resolver_paciente("9999")
    
    assert fuente == "sin_datos"
    assert datos["_vacio"] is True


def test_audio_baja_calidad_marca_warning(tmp_path, monkeypatch):
    """Si confianza < 0.6, transcribir devuelve warning."""
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    
    with patch("backend.workflow_steps.transcribir.transcribir_audio") as mock_t, \
         patch("backend.workflow_steps.transcribir._calcular_duracion_s") as mock_dur:
        mock_dur.return_value = 600.0  # 10 min, no chunking
        mock_t.return_value = {"texto": "blabla", "segmentos": [], "confianza": 0.4, "duracion": 600.0}
        from backend.workflow_steps.transcribir import transcribir_audio_largo
        resultado = transcribir_audio_largo("/tmp/fake.m4a", "123")
    
    assert resultado["warnings"]
    assert "Confianza baja" in resultado["warnings"][0]
```

- [ ] **Step 2: Tests pasan**

```bash
pytest tests/test_casos_alternos.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_casos_alternos.py
git commit -m "✅ tests: casos alternos (portal caído + audio mala calidad)"
```

---

## Task 22: Pregunta inteligente cuando faltan datos críticos

**Files:**
- Modify: `backend/workflow_runner.py` (agregar lógica)
- Modify: `backend/workflow_steps/notificar_listo.py`

- [ ] **Step 1: Modificar `workflow_runner.py` después del paso síntesis**

En `ejecutar_workflow`, agregar después del paso 5 (sintetizar):

```python
        # NUEVO: Si faltan datos críticos tras síntesis, notificar y pausar
        if step_name == "sintetizar_maestro":
            datos_clinicos = resultado_step.get("datos_clinicos") or {}
            faltantes = datos_clinicos.get("_meta", {}).get("campos_faltantes", [])
            criticos = [f for f in faltantes if any(c in f.lower() for c in ["siniestro", "cc", "nombre", "diagnostico"])]
            if criticos:
                _log(f"⚠️ Datos críticos faltantes: {criticos}")
                from backend.notificador import enviar_telegram
                enviar_telegram(
                    f"⚠️ Procesé el audio de CC {paciente_cc} pero me faltan datos críticos:\n" +
                    "\n".join(f"  • {c}" for c in criticos[:5]) +
                    f"\n\n¿Me los das?: http://localhost:3000/paciente/{paciente_cc}"
                )
                db.guardar_resultado(task_id, {"campos_faltantes": criticos, "datos_parciales": datos_clinicos}, estado="esperando_datos")
                return {"task_id": task_id, "estado": "esperando_datos", "campos_faltantes": criticos}
```

- [ ] **Step 2: Commit**

```bash
git add backend/workflow_runner.py
git commit -m "🤔 workflow: detecta datos críticos faltantes y pregunta a Sandra"
```

---

# PARTE 8: Auth básica + Backup + Health (Tasks 23-25)

## Task 23: `auth_simple.py` — PIN + cookie HMAC

**Files:**
- Create: `backend/auth_simple.py`
- Create: `tests/test_auth_simple.py`
- Modify: `backend/server.py` (agregar middleware opcional)

- [ ] **Step 1: Test**

```python
"""Tests para auth_simple."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_genera_y_valida_token(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "test-secret")
    from backend.auth_simple import generar_token, validar_token
    token = generar_token("Sandra")
    assert token
    user = validar_token(token)
    assert user == "Sandra"


def test_token_invalido_devuelve_none(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "test-secret")
    from backend.auth_simple import validar_token
    assert validar_token("bla-bla-bla") is None
    assert validar_token("") is None


def test_validar_pin(monkeypatch):
    monkeypatch.setenv("AUTH_PIN", "5678")
    from backend.auth_simple import validar_pin
    assert validar_pin("5678") is True
    assert validar_pin("0000") is False
```

- [ ] **Step 2: Implementar `backend/auth_simple.py`**

```python
"""
Auth básica para uso doméstico de Sandra.

PIN de 4 dígitos en .env (AUTH_PIN). Endpoint /api/login recibe PIN,
devuelve cookie firmada con HMAC. Endpoints protegidos validan la cookie.

Para producción más seria: migrar a OAuth o JWT con expiración.
"""
import os
from typing import Optional
from itsdangerous import URLSafeSerializer, BadSignature


def _serializer() -> URLSafeSerializer:
    secret = os.getenv("AUTH_SECRET", "cambiar-este-secret-en-prod")
    return URLSafeSerializer(secret, salt="rilo-sas-auth")


def validar_pin(pin: str) -> bool:
    return pin == os.getenv("AUTH_PIN", "1234")


def generar_token(usuario: str = "Sandra") -> str:
    return _serializer().dumps({"usuario": usuario})


def validar_token(token: str) -> Optional[str]:
    if not token:
        return None
    try:
        data = _serializer().loads(token)
        return data.get("usuario")
    except BadSignature:
        return None
```

- [ ] **Step 3: Endpoints en `server.py`**

```python
from fastapi import Cookie, Response

class LoginRequest(BaseModel):
    pin: str


@app.post("/api/login")
async def login(req: LoginRequest, response: Response):
    from backend.auth_simple import validar_pin, generar_token
    if not validar_pin(req.pin):
        raise HTTPException(401, "PIN incorrecto")
    token = generar_token("Sandra")
    response.set_cookie("rilo_session", token, httponly=True, samesite="lax", max_age=86400 * 30)
    return {"ok": True, "usuario": "Sandra"}


@app.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie("rilo_session")
    return {"ok": True}


@app.get("/api/whoami")
async def whoami(rilo_session: Optional[str] = Cookie(None)):
    from backend.auth_simple import validar_token
    usuario = validar_token(rilo_session) if rilo_session else None
    return {"autenticado": bool(usuario), "usuario": usuario}
```

- [ ] **Step 4: Tests pasan + Commit**

```bash
pytest tests/test_auth_simple.py -v
git add backend/auth_simple.py tests/test_auth_simple.py backend/server.py
git commit -m "🔐 auth_simple: PIN + cookie HMAC para Sandra"
```

---

## Task 24: `backup_diario.py` + agregar a cron

**Files:**
- Create: `backend/backup_diario.py`
- Modify: `backend/cron_pre_extraccion.py` (agregar job)

- [ ] **Step 1: Implementar `backend/backup_diario.py`**

```python
"""
Backup diario de storage/ (excluye audios pesados).
Sube a destino local (./storage/backups/YYYYMMDD.tar.gz) y notifica a Manu.
"""
import os
import sys
import tarfile
import shutil
from pathlib import Path
from datetime import datetime


def _log(msg: str):
    print(f"[BACKUP {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def crear_backup() -> Path:
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    backup_dir = Path(os.getenv("BACKUP_DESTINO", "./storage/backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    archivo = backup_dir / f"backup_{fecha}.tar.gz"
    
    excluir = {"backups", "audios_temp", "workflow_audios", "playwright_sessions", "screenshots"}
    
    with tarfile.open(archivo, "w:gz") as tar:
        for item in storage.iterdir():
            if item.name in excluir:
                continue
            tar.add(item, arcname=item.name)
    
    tamano_mb = archivo.stat().st_size / 1024 / 1024
    _log(f"backup OK: {archivo.name} ({tamano_mb:.1f} MB)")
    return archivo


def limpiar_backups_viejos(retener: int = 14):
    """Conserva solo los últimos N backups."""
    backup_dir = Path(os.getenv("BACKUP_DESTINO", "./storage/backups"))
    archivos = sorted(backup_dir.glob("backup_*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    for viejo in archivos[retener:]:
        viejo.unlink()
        _log(f"borrado: {viejo.name}")


async def ejecutar_backup():
    try:
        archivo = crear_backup()
        limpiar_backups_viejos()
        from backend.notificador import enviar_telegram
        tamano_mb = archivo.stat().st_size / 1024 / 1024
        enviar_telegram(f"💾 Backup diario OK: {archivo.name} ({tamano_mb:.1f} MB). Backups retenidos: 14.")
    except Exception as e:
        _log(f"error: {e}")
        try:
            from backend.notificador import enviar_telegram
            enviar_telegram(f"⚠️ Backup diario FALLÓ: {e}")
        except Exception:
            pass
```

- [ ] **Step 2: Agregar job al cron en `cron_pre_extraccion.py`**

En `iniciar_scheduler()`, agregar:

```python
    scheduler.add_job(
        ejecutar_backup_diario,
        CronTrigger(hour=int(os.getenv("BACKUP_HORA", "23")), minute=0, timezone=COL),
        id="backup_diario",
        misfire_grace_time=3600,
    )
```

Y arriba, después de los imports:

```python
async def ejecutar_backup_diario():
    from backend.backup_diario import ejecutar_backup
    await ejecutar_backup()
```

- [ ] **Step 3: Commit**

```bash
git add backend/backup_diario.py backend/cron_pre_extraccion.py
git commit -m "💾 backup_diario: tar.gz nocturno + notif Telegram"
```

---

## Task 25: Health endpoint + costos_tracker

**Files:**
- Create: `backend/costos_tracker.py`
- Modify: `backend/server.py` (endpoint /api/system/health)
- Modify: `backend/lote_worker.py` (log de tokens)

- [ ] **Step 1: Crear `backend/costos_tracker.py`**

```python
"""
Tracker simple de costos LLM. Cuenta tokens por día y alerta si supera umbral.
Persiste en SQLite (storage/workflow.db, tabla costos).
"""
import os
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Dict


SCHEMA = """
CREATE TABLE IF NOT EXISTS costos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha DATE NOT NULL,
    modelo TEXT NOT NULL,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    tokens_reasoning INTEGER DEFAULT 0,
    paciente_cc TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fecha ON costos(fecha);
"""


def _db_path() -> Path:
    return Path(os.getenv("WORKFLOW_DB_PATH", "./storage/workflow.db"))


def _conn():
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(db))
    c.executescript(SCHEMA)
    c.row_factory = sqlite3.Row
    return c


def registrar_uso(modelo: str, tokens: Dict, paciente_cc: str = ""):
    with _conn() as c:
        c.execute(
            "INSERT INTO costos (fecha, modelo, tokens_input, tokens_output, tokens_reasoning, paciente_cc) VALUES (?, ?, ?, ?, ?, ?)",
            (date.today().isoformat(), modelo,
             tokens.get("input", 0), tokens.get("output", 0), tokens.get("reasoning", 0), paciente_cc),
        )


def resumen_dia(fecha: date = None) -> Dict:
    f = fecha or date.today()
    with _conn() as c:
        rows = c.execute(
            "SELECT modelo, SUM(tokens_input) as ti, SUM(tokens_output) as to_, SUM(tokens_reasoning) as tr, COUNT(*) as n FROM costos WHERE fecha = ? GROUP BY modelo",
            (f.isoformat(),)
        ).fetchall()
    return {
        "fecha": f.isoformat(),
        "modelos": [dict(r) for r in rows],
        "total_llamadas": sum(r["n"] for r in rows),
        "total_tokens": sum((r["ti"] or 0) + (r["to_"] or 0) + (r["tr"] or 0) for r in rows),
    }
```

- [ ] **Step 2: Integrar en `lote_worker.py`**

Al final de `_llamar_llm`, antes del return, agregar:

```python
    # Registrar uso para tracking de costos
    try:
        from backend.costos_tracker import registrar_uso
        registrar_uso(modelo, {
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
            "reasoning": usage.get("reasoning_tokens", 0),
        })
    except Exception:
        pass
```

- [ ] **Step 3: Endpoint en `server.py`**

```python
import shutil

@app.get("/api/system/health")
def system_health():
    """Estado del sistema completo."""
    from backend.costos_tracker import resumen_dia
    
    storage = Path(os.getenv("STORAGE_DIR", "./storage"))
    disk = shutil.disk_usage(str(storage))
    
    return {
        "ok": True,
        "fase_a_habilitada": os.getenv("FASE_A_ENABLED", "false").lower() == "true",
        "tomy_completo_habilitado": os.getenv("TOMY_COMPLETO_ENABLED", "false").lower() == "true",
        "disk": {
            "total_gb": round(disk.total / 1024**3, 1),
            "libre_gb": round(disk.free / 1024**3, 1),
            "porcentaje_uso": round(100 * (disk.total - disk.free) / disk.total, 1),
        },
        "credenciales": {
            "deepgram": bool(os.getenv("DEEPGRAM_API_KEY")),
            "opencode_go": bool(os.getenv("OPENCODE_GO_API_KEY")),
            "telegram": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
            "medifolios": bool(os.getenv("MEDIFOLIOS_USER")),
            "positiva": bool(os.getenv("POSITIVA_USER")),
        },
        "costos_hoy": resumen_dia(),
    }
```

- [ ] **Step 4: Commit**

```bash
git add backend/costos_tracker.py backend/lote_worker.py backend/server.py
git commit -m "📊 costos_tracker + /api/system/health (disk + creds + tokens diarios)"
```

---

# PARTE 9: Tests E2E completos y rollout (Tasks 26-28)

## Task 26: Test E2E del flujo completo (mockeado)

**Files:**
- Modify: `tests/test_e2e.py` (extender)

- [ ] **Step 1: Agregar test E2E del workflow completo**

```python
def test_e2e_workflow_completo_mockeado(tmp_path, monkeypatch):
    """
    Simula: Sandra sube audio → workflow corre todos los pasos → JSON final tiene
    formatos generados. Sin tocar Deepgram, Playwright, LLM, doc_generator (mocks).
    """
    from unittest.mock import patch, MagicMock, AsyncMock
    monkeypatch.setenv("TOMY_COMPLETO_ENABLED", "true")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("WORKFLOW_DB_PATH", str(tmp_path / "wf.db"))
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path / "workspace"))
    (tmp_path / "workspace").mkdir(exist_ok=True)
    (tmp_path / "storage" / "data").mkdir(parents=True, exist_ok=True)
    
    # Mock cada step
    with patch("backend.flujo_audio.transcribir_audio") as m_trans, \
         patch("backend.playwright_real.orquestador.extraer_paciente_completo", new_callable=AsyncMock) as m_pw, \
         patch("backend.workflow_steps.generar_formatos.generar_documento") as m_gen, \
         patch("backend.workflow_steps.transcribir._calcular_duracion_s") as m_dur, \
         patch("backend.workflow_steps.qa_formatos._qa_script_path") as m_qa, \
         patch("backend.workflow_steps.convertir_pdf._tiene_libreoffice") as m_libre, \
         patch("backend.notificador.enviar_telegram") as m_tel, \
         patch("backend.lote_worker._llamar_llm") as m_llm:
        
        m_dur.return_value = 600.0
        m_trans.return_value = {"texto": "Paciente dice que le duele.", "segmentos": [], "confianza": 0.9, "duracion": 600}
        m_pw.return_value = {
            "cc": "1193143688",
            "medifolios": {"nombre1": "JUAN", "apellido1": "DURAN"},
            "positiva": {"siniestros": [{"id": "503463870"}]},
            "_meta": {"discrepancias": []},
        }
        m_qa.return_value = tmp_path / "noexiste.py"  # qa script no disponible → warning, no falla
        m_libre.return_value = False  # libreoffice no instalado → skip pdfs
        m_tel.return_value = True
        m_gen.return_value = str(tmp_path / "fake.docx")
        m_llm.return_value = {
            "content": '```json\n{"paciente":{"documento":"1193143688","nombre":"JUAN"},"estado_caso":"SEGUIMIENTO","_meta":{"campos_faltantes":[]}}\n```',
            "reasoning": "",
            "finish": "stop",
            "tokens": {"input": 100, "output": 50, "reasoning": 0, "total": 150},
            "tiempo_s": 2.0,
        }
        
        # Crear audio dummy
        audio = tmp_path / "test.m4a"
        audio.write_bytes(b"\x00" * 100)
        
        from backend.workflow_runner import ejecutar_workflow
        resultado = ejecutar_workflow(audio_path=str(audio), paciente_cc="1193143688")
    
    assert resultado["estado"] == "listo"
    assert resultado["task_id"]
    assert m_tel.called  # Telegram enviado
```

- [ ] **Step 2: Test pasa**

```bash
pytest tests/test_e2e.py::test_e2e_workflow_completo_mockeado -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_e2e.py
git commit -m "✅ tests: e2e workflow completo mockeado (9 pasos + Telegram)"
```

---

## Task 27: Suite completa pasa + verificar build dashboard

**Files:** (sin cambios de código, solo validación)

- [ ] **Step 1: Suite completa pasa**

```bash
pytest tests/ -v --tb=short
```

Expected: TODOS pasan o skippean. Si falla algo, arreglar antes de continuar.

- [ ] **Step 2: Build de Next.js sin errores**

```bash
cd dashboard
npm run build 2>&1 | tail -20
cd ..
```

Expected: build completo sin errores TypeScript.

- [ ] **Step 3: Smoke con uvicorn**

```bash
uvicorn backend.server:app --port 8000 &
sleep 3
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/system/health | head -50
pkill -f "uvicorn.*server:app"
```

Expected: ambos endpoints responden 200.

---

## Task 28: Rollout en WSL (manual)

- [ ] **Step 1: Pull en WSL + deps**

```bash
ssh manu@wsl
cd ~/rilo-backend
git pull origin main
pip install -r backend/requirements.txt
# si faltan tools del sistema:
sudo apt-get install -y ffmpeg libreoffice
```

- [ ] **Step 2: Editar `.env` en WSL (apagado)**

```bash
TOMY_COMPLETO_ENABLED=false   # arrancar apagado
FASE_A_ENABLED=true            # mantenido de Fase A
FASE_A_CRON_ENABLED=true
```

- [ ] **Step 3: Restart FastAPI + verificar**

```bash
pkill -f "uvicorn.*server:app" || true
nohup uvicorn backend.server:app --host 0.0.0.0 --port 8000 > /tmp/rilo.log 2>&1 &
sleep 3
curl -s http://localhost:8000/api/system/health | python3 -m json.tool
```

Esperado: campo `tomy_completo_habilitado: false`, resto OK.

- [ ] **Step 4: Activar Tomy Completo en sombra**

```bash
sed -i 's/TOMY_COMPLETO_ENABLED=false/TOMY_COMPLETO_ENABLED=true/' .env
pkill -f "uvicorn.*server:app"
nohup uvicorn backend.server:app --host 0.0.0.0 --port 8000 > /tmp/rilo.log 2>&1 &
```

- [ ] **Step 5: Smoke con audio de prueba**

```bash
# Necesitas un audio.m4a de prueba (1-5 min para test rápido)
curl -X POST http://localhost:8000/api/procesar-paciente \
  -F "audio=@/tmp/audio_prueba.m4a" \
  -F "paciente_cc=1193143688"
# Devuelve task_id
# Esperar 5 min:
curl -s http://localhost:8000/api/tasks/<task_id> | python3 -m json.tool
```

- [ ] **Step 6: Test dashboard**

Abrir en navegador: `http://localhost:3000/hoy`
- Debe mostrar agenda + tasks activas.
- Click "Subir audio" → vista grande con drag-and-drop.
- Subir audio + CC → redirige a `/paciente/1193143688` con timeline en vivo.

- [ ] **Step 7: Tag + commit final**

```bash
cd ~/rilo-backend
git tag tomy-completo-v1.0
git log --oneline -5
```

---

# Self-Review (al terminar el plan)

**Spec coverage:**
- ✅ Pipeline asíncrono e2e → Tasks 1-11
- ✅ Organizar formatos crudos → Task 12
- ✅ Loop de corrección → Tasks 13-14
- ✅ Casos alternos → Tasks 21-22 + integraciones en 4, 5, 21
- ✅ Dashboard Sandra-first → Tasks 15-20
- ✅ Producción → Tasks 23-25
- ✅ Tests E2E → Tasks 13, 26, 27
- ✅ Rollout → Task 28

**Placeholders:** Sin TBDs/TODOs vagos. Cada step tiene código real.

**Consistencia:** `workflow_runner`, `task_db`, `workflow_steps/*` y endpoints usan los mismos nombres en todas las tasks. `TOMY_COMPLETO_ENABLED` consistente.

**Estimación total:** ~28 tasks, ~25 sesiones de OpenCode, distribuible 2-3 semanas.

**Métricas de éxito tras rollout (de la spec):**
- ✅ Sandra usa el flujo end-to-end en ≥80% de pacientes en 2 semanas
- ✅ Tiempo medio workflow: <20 min/paciente
- ✅ Tasa aprobación sin corrección: >60%
- ✅ Costo LLM/paciente: <$0.10
- ✅ Cero crashes OOM
