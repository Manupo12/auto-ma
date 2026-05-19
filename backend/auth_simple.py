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
