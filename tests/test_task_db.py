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
