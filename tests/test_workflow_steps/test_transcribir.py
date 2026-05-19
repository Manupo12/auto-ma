"""Tests para transcribir.py."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_calcular_duracion_devuelve_segundos(tmp_path):
    from backend.workflow_steps.transcribir import _calcular_duracion_s
    fake = tmp_path / "fake.wav"
    fake.write_bytes(b"RIFF" + b"\x00" * 100)
    with patch("backend.workflow_steps.transcribir.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="3600.5\n")
        dur = _calcular_duracion_s(fake)
    assert dur == 3600.5


def test_decide_chunks_si_audio_largo(tmp_path, monkeypatch):
    from backend.workflow_steps.transcribir import _necesita_chunking
    monkeypatch.setenv("AUDIO_CHUNK_DURATION_S", "1500")
    assert _necesita_chunking(1400.0) is False
    assert _necesita_chunking(2000.0) is True


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="needs ffmpeg")
def test_dividir_audio_en_chunks(tmp_path):
    import subprocess
    audio = tmp_path / "input.wav"
    subprocess.run([
        "ffmpeg", "-f", "lavfi", "-i", "sine=frequency=440:duration=60",
        "-ar", "16000", str(audio), "-y"
    ], capture_output=True, check=True)

    from backend.workflow_steps.transcribir import _dividir_en_chunks
    chunks = _dividir_en_chunks(audio, chunk_dur_s=25, output_dir=tmp_path)
    assert len(chunks) == 3
    assert all(c.exists() for c in chunks)
