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
