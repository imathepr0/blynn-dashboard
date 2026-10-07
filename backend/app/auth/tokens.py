"""
Tokens de sesión.

* Token de acceso: JWT firmado (HS256), vida corta (15 min por defecto).
  Es "sin estado": una vez emitido no se puede anular antes de que
  venza, por eso dura poco.
* Refresh token: NO es un JWT, es un texto aleatorio opaco (384 bits) que
  se guarda en la base de datos solo como huella SHA-256. Como está en la
  base de datos SÍ se puede revocar (logout, robo detectado). Se rota en
  cada uso.

Verificación del JWT (lo que evita los ataques clásicos):
* El algoritmo se fija en el servidor (`algorithms=["HS256"]`): un token
  que declare `alg: none` o cualquier otro se rechaza.
* Se exigen las claims exp, iat, sub, iss y jti, y se comprueba el
  emisor y que sea de tipo "access".
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

import jwt

from app.config import Settings
from app.db.base import ahora_utc

ALGORITMO = "HS256"  # fijo a propósito: no es configurable


class TokenInvalidoError(Exception):
    """El token no es válido (firma, vencimiento, formato, emisor o tipo)."""


def _clave(settings: Settings) -> str:
    if settings.JWT_SECRET_KEY is None:
        raise RuntimeError("JWT_SECRET_KEY no está configurada.")
    return settings.JWT_SECRET_KEY.get_secret_value()


def crear_access_token(
    user_id: uuid.UUID, settings: Settings, *, ahora: datetime | None = None
) -> tuple[str, int]:
    """Devuelve (token, segundos_de_vida)."""
    ahora = ahora or ahora_utc()
    vida = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "iss": settings.JWT_ISSUER,
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + vida).timestamp()),
        "jti": uuid.uuid4().hex,
        "typ": "access",
    }
    token = jwt.encode(payload, _clave(settings), algorithm=ALGORITMO)
    return token, int(vida.total_seconds())


def decodificar_access_token(token: str, settings: Settings) -> uuid.UUID:
    """Devuelve el id de usuario del token o lanza `TokenInvalidoError`."""
    try:
        payload = jwt.decode(
            token,
            _clave(settings),
            algorithms=[ALGORITMO],
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "iss", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenInvalidoError("Token inválido o expirado.") from exc

    if payload.get("typ") != "access":
        raise TokenInvalidoError("Tipo de token incorrecto.")
    try:
        return uuid.UUID(str(payload["sub"]))
    except (ValueError, KeyError) as exc:
        raise TokenInvalidoError("Identificador de usuario inválido.") from exc


def generar_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def huella_refresh_token(token: str) -> str:
    """SHA-256 en hexadecimal. Basta un hash rápido (no bcrypt) porque el
    token es aleatorio de 384 bits: no se puede adivinar ni probar por
    diccionario."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
