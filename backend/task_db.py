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
