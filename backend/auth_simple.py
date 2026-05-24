"""
Auth básica para uso doméstico de Sandra.

PIN de 4 dígitos en .env (AUTH_PIN). Endpoint /api/login recibe PIN,
devuelve cookie firmada con HMAC. Endpoints protegidos validan la cookie.

Para producción más seria: migrar a OAuth o JWT con expiración.
"""
import os
from secrets import compare_digest
from typing import Optional
from itsdangerous import URLSafeSerializer, BadSignature

from fastapi import HTTPException, Cookie, Depends


def _serializer() -> URLSafeSerializer:
    secret = os.getenv("AUTH_SECRET", "cambiar-este-secret-en-prod")
    return URLSafeSerializer(secret, salt="rilo-sas-auth")


AUTH_PIN = os.getenv("AUTH_PIN")
if not AUTH_PIN:
    raise RuntimeError("AUTH_PIN no configurado en .env - el servidor no puede iniciar")

def validar_pin(pin: str) -> bool:
    return compare_digest(pin, AUTH_PIN)


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


async def verificar_sesion(rilo_session: Optional[str] = Cookie(None)):
    if not rilo_session:
        raise HTTPException(status_code=401, detail="No autenticado. Usa /api/login para iniciar sesion.")
    usuario = validar_token(rilo_session)
    if not usuario:
        raise HTTPException(status_code=401, detail="Sesion invalida o expirada. Vuelve a iniciar sesion.")
    return usuario
