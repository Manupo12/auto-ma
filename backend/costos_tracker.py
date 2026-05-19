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
