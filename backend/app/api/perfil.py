"""
Endpoints del perfil del usuario (lo que en la plataforma anterior era `auth.me` y
`auth.updateMe`).

    GET   /api/v1/me            mismo dato que /api/v1/auth/me
    PATCH /api/v1/me            nombre, preferencias, encuesta y presupuesto
    POST  /api/v1/me/reset      borra los datos y deja la cuenta como nueva
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import usuario_actual
from app.auth.schemas import UsuarioOut
from app.db.models import User
from app.db.session import get_db
from app.schemas.perfil import PerfilPatch, ReinicioIn
from app.services.datos_usuario import reiniciar_cuenta

router = APIRouter(prefix="/me", tags=["Perfil"])


@router.get("", response_model=UsuarioOut)
def mi_perfil(usuario: User = Depends(usuario_actual)):
    return usuario


@router.patch("", response_model=UsuarioOut)
def actualizar_perfil(
    datos: PerfilPatch, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)
):
    """Solo cambia los campos enviados. `email`, `role`, `is_active` y la
    contraseña NO se pueden cambiar desde aquí (el esquema los rechaza)."""
    cambios = datos.model_dump(exclude_unset=True)
    preferencias = cambios.pop("preferences", None)
    for campo, valor in cambios.items():
        setattr(usuario, campo, valor)
    if preferencias is not None:
        # Se combina con lo ya guardado (no se pisa todo el objeto).
        usuario.preferences = {**(usuario.preferences or {}), **preferencias}
    db.commit()
    return usuario


@router.post("/reset", response_model=UsuarioOut)
def reiniciar(
    _: ReinicioIn, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)
):
    """Operación destructiva: exige `{"confirm": true}` en el cuerpo."""
    reiniciar_cuenta(db, usuario)
    return usuario
