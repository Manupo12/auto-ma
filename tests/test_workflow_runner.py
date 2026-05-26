"""Tests para workflow_runner.py — orquesta los 9 pasos."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_endpoint_procesar_paciente_crea_task(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMY_COMPLETO_ENABLED", "true")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("WORKFLOW_DB_PATH", str(tmp_path / "wf.db"))

    from fastapi.testclient import TestClient
    from backend.server import app

    audio = tmp_path / "test.m4a"
    audio.write_bytes(b"\x00" * 100)

    client = TestClient(app)
    with patch("backend.workflow_runner.ejecutar_workflow") as mock_wf:
        mock_wf.return_value = {"task_id": "abc", "estado": "listo"}
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


def test_runner_ejecuta_los_9_pasos_en_orden(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("WORKFLOW_DB_PATH", str(tmp_path / "wf.db"))
    monkeypatch.setenv("TOMY_COMPLETO_ENABLED", "true")

    with patch("backend.workflow_steps.transcribir.ejecutar") as m1, \
         patch("backend.workflow_steps.resolver_paciente.ejecutar") as m2, \
         patch("backend.workflow_steps.leer_notas_crudas.ejecutar") as m3, \
         patch("backend.workflow_steps.leer_formatos_subidos.ejecutar") as m4, \
         patch("backend.workflow_steps.sintetizar_maestro.ejecutar") as m5, \
         patch("backend.workflow_steps.generar_formatos.ejecutar") as m6, \
         patch("backend.workflow_steps.qa_formatos.ejecutar") as m7, \
         patch("backend.workflow_steps.convertir_pdf.ejecutar") as m8, \
         patch("backend.workflow_steps.notificar_listo.ejecutar") as m9:

        m1.return_value = {"ok": True, "texto": "...", "warnings": []}
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


def test_cadena_completa_no_mezcla_pacientes():
    """Simula el workflow para Maribel y verifica que no salen datos de Juan Carlos."""
    import sys, json, tempfile, os
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from backend.workflow_steps.generar_formatos import _merge_paciente_con_llm
    from backend.workflow_steps.leer_notas_crudas import _tiene_cc

    # 1. Verificar que _tiene_cc encuentra CC en contenido con saltos de línea
    contenido_voi = "3\n6\n2\n8\n0\n2\n2\n8"
    assert _tiene_cc(Path("VOI_prueba.docx"), "36280228") is False # matching name only
    assert _tiene_cc(Path("prueba.txt"), "36280228") is False # content empty
    
    # Create temp text file for _tiene_cc
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmpf:
        tmpf.write(contenido_voi)
        tmpf_name = tmpf.name
    try:
        assert _tiene_cc(Path(tmpf_name), "36280228") is True, "VOI con CC dígito a dígito no se encuentra"
    finally:
        os.unlink(tmpf_name)

    # 2. Verificar merge no mezcla pacientes
    datos_llm = {
        "paciente": {"nombre": "JUAN LLM", "documento": "36280228"},
        "empresa": {"nombre": "EMPRESA LLM"},
        "siniestro": {"id_siniestro": "503000000"},
    }

    json_sintetizado = {
        "paciente": {"nombre": "JUAN LLM", "documento": "36280228"},
        "_portales": {
            "medifolios": {
                "nombre1": "MARIBEL", "apellido1": "FUENTES", "apellido2": "MEDINA",
                "numero_id": "36280228", "telefono": "3001234567",
            },
            "positiva": {
                "datos_asegurado": {"empresa": "ALCALDIA PITALITO", "cargo_asegurado": "TECNICA ADMINISTRATIVA", "nit": "900123456"},
                "autorizaciones": [{"descripcion": "503375273", "estado": "23/05/2025"}],
            },
        },
    }

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["STORAGE_DIR"] = tmp
        data_dir = Path(tmp) / "data"
        data_dir.mkdir()
        (data_dir / "36280228-completo.json").write_text(json.dumps(json_sintetizado), encoding="utf-8")

        resultado = _merge_paciente_con_llm(datos_llm, "36280228")

    assert resultado["paciente"]["nombre"] == "MARIBEL FUENTES MEDINA"
    assert resultado["empresa"]["nombre"] == "ALCALDIA PITALITO"
    assert resultado["laboral"]["cargo"] == "TECNICA ADMINISTRATIVA"
    assert resultado["siniestro"]["id_siniestro"] == "503375273"
    assert resultado["siniestro"]["fecha_evento"] == "23/05/2025"
    assert "Obrero de tratamiento roca" not in str(resultado)
    assert "BOLIVARIANA DE MINERALES" not in str(resultado)
