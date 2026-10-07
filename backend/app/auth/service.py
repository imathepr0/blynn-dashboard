"""
Lógica de negocio de autenticación (sin HTTP): registrar, autenticar,
emitir/rotar/revocar sesiones.

Reglas clave:
* Toda función que escribe hace `commit` ella misma antes de terminar;
  los endpoints solo traducen errores a respuestas HTTP.
* Mensajes de error genéricos: "Correo o contraseña incorrectos" sea
  cual sea el motivo (correo inexistente, contraseña mala, cuenta
  desactivada).
* Refresh tokens con rotación y detección de reutilización: cada uso
  invalida el token y entrega uno nuevo de la misma "familia". Si llega
  un token ya usado o revocado, se asume robo y se revoca la familia
  completa (el ladrón y el usuario legítimo quedan fuera; el usuario
  inicia sesión de nuevo).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import (
    ContrasenaInvalidaError,
    gastar_tiempo_de_verificacion,
    hash_password,
    validar_politica,
    verify_password,
)
from app.auth.tokens import (
    crear_access_token,
    generar_refresh_token,
    huella_refresh_token,
)
from app.config import Settings
from app.db.base import ahora_utc
from app.db.models import RefreshToken, User

logger = logging.getLogger(__name__)

# Los refresh tokens vencidos se conservan un día más antes de borrarse.
_GRACIA_LIMPIEZA = timedelta(days=1)


class ErrorDeAutenticacion(Exception):
    status_code = 401
    mensaje = "No autorizado."

    def __init__(self, mensaje: str | None = None) -> None:
        super().__init__(mensaje or self.mensaje)
        self.mensaje = mensaje or self.mensaje


class CredencialesInvalidasError(ErrorDeAutenticacion):
    mensaje = "Correo o contraseña incorrectos."


class RefreshTokenInvalidoError(ErrorDeAutenticacion):
    mensaje = "Sesión inválida o expirada. Inicia sesión nuevamente."


class EmailYaRegistradoError(ErrorDeAutenticacion):
    status_code = 409
    mensaje = "Ya existe una cuenta con ese correo."


class ContrasenaNoValidaError(ErrorDeAutenticacion):
    status_code = 422


@dataclass
class TokensEmitidos:
    access_token: str
    refresh_token: str
    expires_in: int


def normalizar_email(email: str) -> str:
    return email.strip().lower()


# --------------------------------------------------------------------- #
# Registro e inicio de sesión
# --------------------------------------------------------------------- #
def registrar_usuario(
    db: Session, *, email: str, password: str, full_name: str | None, settings: Settings
) -> User:
    email = normalizar_email(email)
    try:
        validar_politica(password, largo_minimo=settings.PASSWORD_MIN_LENGTH, email=email)
    except ContrasenaInvalidaError as exc:
        raise ContrasenaNoValidaError(str(exc)) from exc

    usuario = User(
        email=email,
        password_hash=hash_password(password, rounds=settings.BCRYPT_ROUNDS),
        full_name=full_name or None,
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        # Dos registros simultáneos con el mismo correo: gana el primero
        # (la restricción UNIQUE de la base de datos es la que decide).
        db.rollback()
        if db.scalar(select(User.id).where(User.email == email)) is not None:
            raise EmailYaRegistradoError() from None
        raise
    return usuario


def autenticar(db: Session, *, email: str, password: str, settings: Settings) -> User:
    """Devuelve el usuario si las credenciales son correctas."""
    email = normalizar_email(email)
    usuario = db.scalar(select(User).where(User.email == email))

    if usuario is None:
        # Mismo costo de tiempo que con un correo real (ver passwords.py).
        gastar_tiempo_de_verificacion(password, rounds=settings.BCRYPT_ROUNDS)
        raise CredencialesInvalidasError()
    if not verify_password(password, usuario.password_hash):
        raise CredencialesInvalidasError()
    # La cuenta desactivada se revisa DESPUÉS de la contraseña y con el
    # mismo mensaje, para no revelar su estado a quien no la conoce.
    if not usuario.is_active:
        raise CredencialesInvalidasError()
    return usuario


def iniciar_sesion(db: Session, usuario: User, settings: Settings) -> TokensEmitidos:
    ahora = ahora_utc()
    usuario.last_login_date = ahora
    _limpiar_tokens_vencidos(db, ahora)
    tokens = _emitir_tokens(db, usuario, settings, ahora=ahora)
    db.commit()
    return tokens


# --------------------------------------------------------------------- #
# Refresh tokens
# --------------------------------------------------------------------- #
def rotar_refresh_token(
    db: Session, refresh_token: str, settings: Settings
) -> tuple[User, TokensEmitidos]:
    ahora = ahora_utc()
    fila = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == huella_refresh_token(refresh_token))
        # Bloquea la fila (en Postgres): dos usos simultáneos del mismo
        # token se atienden uno tras otro, y el segundo se ve como reuso.
        .with_for_update()
    )
    if fila is None:
        raise RefreshTokenInvalidoError()

    if fila.revoked_at is not None:
        # Token ya usado o revocado que vuelve a presentarse: posible robo.
        logger.warning(
            "Reutilización de refresh token detectada; se revoca la sesión (user_id=%s)",
            fila.user_id,
        )
        _revocar_familia(db, fila.family_id, ahora)
        db.commit()
        raise RefreshTokenInvalidoError()

    if fila.expires_at <= ahora:
        raise RefreshTokenInvalidoError()

    usuario = db.get(User, fila.user_id)
    if usuario is None or not usuario.is_active:
        _revocar_familia(db, fila.family_id, ahora)
        db.commit()
        raise RefreshTokenInvalidoError()

    fila.revoked_at = ahora  # este token ya no sirve
    tokens = _emitir_tokens(db, usuario, settings, ahora=ahora, family_id=fila.family_id)
    db.commit()
    return usuario, tokens


def cerrar_sesion(db: Session, refresh_token: str) -> None:
    """Revoca la sesión a la que pertenece el token. Idempotente: no dice
    si el token existía, así no sirve para sondear tokens."""
    fila = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == huella_refresh_token(refresh_token))
    )
    if fila is not None:
        _revocar_familia(db, fila.family_id, ahora_utc())
        db.commit()


def cerrar_todas_las_sesiones(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=ahora_utc())
    )
    db.commit()


# --------------------------------------------------------------------- #
# Internos
# --------------------------------------------------------------------- #
def _emitir_tokens(
    db: Session,
    usuario: User,
    settings: Settings,
    *,
    ahora: datetime,
    family_id: uuid.UUID | None = None,
) -> TokensEmitidos:
    refresh = generar_refresh_token()
    db.add(
        RefreshToken(
            user_id=usuario.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=huella_refresh_token(refresh),
            expires_at=ahora + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    access, expires_in = crear_access_token(usuario.id, settings, ahora=ahora)
    return TokensEmitidos(access_token=access, refresh_token=refresh, expires_in=expires_in)


def _revocar_familia(db: Session, family_id: uuid.UUID, ahora: datetime) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=ahora)
    )


def _limpiar_tokens_vencidos(db: Session, ahora: datetime) -> None:
    """Mantiene chica la tabla (el plan gratuito de Supabase da 500 MB)."""
    db.execute(delete(RefreshToken).where(RefreshToken.expires_at < ahora - _GRACIA_LIMPIEZA))
