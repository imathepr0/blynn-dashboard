"""
Acceso a datos con dueño.

REGLA DE ORO del backend: nunca se busca un registro solo por su id. Toda
consulta de un recurso del usuario pasa por `obtener_propio`, que exige
también `user_id == usuario`. Si el registro es de otra persona, el
resultado es idéntico a que no exista (404).
"""
from __future__ import annotations

import uuid
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.errores import NoEncontrado

M = TypeVar("M")


def obtener_propio(
    db: Session, modelo: type[M], recurso_id: uuid.UUID, usuario_id: uuid.UUID, *, bloquear: bool = False
) -> M:
    """Devuelve el registro del usuario o lanza `NoEncontrado`.

    `bloquear=True` toma un bloqueo de fila (`SELECT ... FOR UPDATE` en
    Postgres) para modificar el registro sin que otra petición simultánea
    lo cambie a la vez (p. ej. el monto acumulado de una meta).
    """
    consulta = select(modelo).where(modelo.id == recurso_id, modelo.user_id == usuario_id)  # type: ignore[attr-defined]
    if bloquear:
        consulta = consulta.with_for_update()
    registro = db.scalar(consulta)
    if registro is None:
        raise NoEncontrado()
    return registro
