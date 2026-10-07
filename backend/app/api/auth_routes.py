"""
Endpoints de autenticación (Etapa 2).

    POST /api/v1/auth/register     crea la cuenta y abre sesión
    POST /api/v1/auth/login        abre sesión
    POST /api/v1/auth/refresh      cambia un refresh token por un par nuevo
    POST /api/v1/auth/logout       cierra la sesión del refresh token dado
    POST /api/v1/auth/logout-all   cierra TODAS las sesiones (requiere token)
    GET  /api/v1/auth/me           datos del usuario autenticado

Esta capa solo traduce HTTP <-> servicio: la lógica está en
`app/auth/service.py`.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.dependencies import usuario_actual
from app.auth.rate_limit import exigir_disponible, ip_cliente, obtener_limitadores
from app.auth.schemas import AuthOut, LoginIn, RefreshIn, RegistroIn, TokensOut, UsuarioOut
from app.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _sin_cache(response: Response) -> None:
    # Las respuestas con tokens nunca deben guardarse en cachés (RFC 6749).
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _error_http(exc: service.ErrorDeAutenticacion) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.mensaje)


@router.post("/register", response_model=AuthOut, status_code=201)
def registrar(
    datos: RegistroIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthOut:
    """Crea una cuenta nueva (correo + contraseña) e inicia sesión."""
    ip = ip_cliente(request, settings)
    limitadores = obtener_limitadores(settings)
    if settings.AUTH_RATE_LIMIT_ENABLED:
        exigir_disponible(db, limitadores.registros_por_ip, ip)
        limitadores.registros_por_ip.registrar(db, ip)  # cuenta todos los intentos

    try:
        usuario = service.registrar_usuario(
            db,
            email=datos.email,
            password=datos.password,
            full_name=datos.full_name,
            settings=settings,
        )
    except service.ErrorDeAutenticacion as exc:
        raise _error_http(exc) from None

    tokens = service.iniciar_sesion(db, usuario, settings)
    _sin_cache(response)
    return AuthOut(**tokens.__dict__, user=UsuarioOut.model_validate(usuario))


@router.post("/login", response_model=AuthOut)
def iniciar_sesion(
    datos: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthOut:
    """Abre sesión con correo y contraseña."""
    ip = ip_cliente(request, settings)
    clave_cuenta = f"{service.normalizar_email(datos.email)}|{ip}"
    limitadores = obtener_limitadores(settings)
    if settings.AUTH_RATE_LIMIT_ENABLED:
        # Se revisa ANTES de gastar tiempo en bcrypt.
        exigir_disponible(db, limitadores.fallos_por_ip, ip)
        exigir_disponible(db, limitadores.fallos_por_cuenta, clave_cuenta)

    try:
        usuario = service.autenticar(
            db, email=datos.email, password=datos.password, settings=settings
        )
    except service.CredencialesInvalidasError as exc:
        if settings.AUTH_RATE_LIMIT_ENABLED:
            limitadores.fallos_por_ip.registrar(db, ip)
            limitadores.fallos_por_cuenta.registrar(db, clave_cuenta)
        logger.warning("Intento de inicio de sesión fallido (ip=%s)", ip)
        raise _error_http(exc) from None

    limitadores.fallos_por_cuenta.reiniciar(db, clave_cuenta)
    tokens = service.iniciar_sesion(db, usuario, settings)
    _sin_cache(response)
    return AuthOut(**tokens.__dict__, user=UsuarioOut.model_validate(usuario))


@router.post("/refresh", response_model=TokensOut)
def renovar_sesion(
    datos: RefreshIn,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokensOut:
    """Cambia un refresh token por un access token nuevo y un refresh
    token nuevo. El refresh token anterior queda inutilizable."""
    try:
        _, tokens = service.rotar_refresh_token(db, datos.refresh_token, settings)
    except service.ErrorDeAutenticacion as exc:
        raise _error_http(exc) from None
    _sin_cache(response)
    return TokensOut(**tokens.__dict__)


@router.post("/logout", status_code=204)
def cerrar_sesion(datos: RefreshIn, db: Session = Depends(get_db)) -> Response:
    """Cierra la sesión del refresh token indicado. Siempre responde 204,
    exista o no el token."""
    service.cerrar_sesion(db, datos.refresh_token)
    return Response(status_code=204)


@router.post("/logout-all", status_code=204)
def cerrar_todas_las_sesiones(
    usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)
) -> Response:
    """Cierra todas las sesiones del usuario (p. ej. si perdió un
    dispositivo). Los access tokens ya emitidos siguen valiendo hasta que
    venzan (máx. 15 min por defecto)."""
    service.cerrar_todas_las_sesiones(db, usuario.id)
    return Response(status_code=204)


@router.get("/me", response_model=UsuarioOut)
def mi_perfil(usuario: User = Depends(usuario_actual)) -> User:
    """Datos del usuario autenticado."""
    return usuario
