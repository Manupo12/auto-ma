"""Tests para cron_pre_extraccion."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_obtener_estado_scheduler():
    """Scheduler debe devolver estado sin errores."""
    from backend.cron_pre_extraccion import obtener_estado
    estado = obtener_estado()
    assert isinstance(estado, dict)
    assert "activo" in estado
    assert "jobs" in estado
