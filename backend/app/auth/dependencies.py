"""
Dependencia de FastAPI que exige un usuario autenticado.

Uso en cualquier endpoint protegido:

    def mi_endpoint(usuario: User = Depends(usuario_actual)): ...

En cada petición se valida el token Y se consulta el usuario en la base
de datos: si la cuenta fue borrada o desactivada, el token deja de
servir de inmediato aunque todavía no haya vencido.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.tokens import TokenInvalidoError, decodificar_access_token
from app.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db

# auto_error=False para responder SIEMPRE 401 (y no 403) sin credenciales.
_esquema_bearer = HTTPBearer(auto_error=False, description="Access token (JWT)")


def _no_autorizado() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="No autorizado.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_esquema_bearer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if credenciales is None or credenciales.scheme.lower() != "bearer":
        raise _no_autorizado()
    try:
        user_id = decodificar_access_token(credenciales.credentials, settings)
    except TokenInvalidoError:
        raise _no_autorizado() from None

    usuario = db.get(User, user_id)
    if usuario is None or not usuario.is_active:
        raise _no_autorizado()
    return usuario
