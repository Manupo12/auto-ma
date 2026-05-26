"""Tests para leer_notas_crudas.py."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_lee_notas_de_workspace_por_cc(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "notas_1193143688.txt").write_text("Paciente dice que le duele el hombro", encoding="utf-8")
    (workspace / "consulta_juan_1193143688.txt").write_text("Síntoma adicional: rigidez matutina", encoding="utf-8")
    (workspace / "otro_paciente.txt").write_text("No debería aparecer", encoding="utf-8")

    monkeypatch.setenv("WORKSPACE_DIR", str(workspace))
    from backend.workflow_steps.leer_notas_crudas import leer_notas_crudas

    notas, completo = leer_notas_crudas("1193143688")
    assert len(notas) == 2
    assert "duele el hombro" in " ".join(n["contenido"] for n in notas)
    assert "rigidez matutina" in " ".join(n["contenido"] for n in notas)


def test_devuelve_vacio_si_no_hay_notas(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("WORKSPACE_DIR", str(workspace))
    from backend.workflow_steps.leer_notas_crudas import leer_notas_crudas
    notas, completo = leer_notas_crudas("9999")
    assert notas == []
