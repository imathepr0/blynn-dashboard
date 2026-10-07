"""
Endpoints de metas de ahorro y de sus aportes.

    GET    /api/v1/goals                        lista
    POST   /api/v1/goals
    GET    /api/v1/goals/{id}
    PATCH  /api/v1/goals/{id}
    DELETE /api/v1/goals/{id}                   borra también sus aportes
    POST   /api/v1/goals/{id}/contributions     registra un aporte (atómico)

    GET    /api/v1/contributions                lista (filtro: goal_id)
    DELETE /api/v1/contributions/{id}           deshace un aporte (atómico);
                                                devuelve la meta actualizada
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.comun import Paginacion, ordenar, paginacion
from app.auth.dependencies import usuario_actual
from app.db.models import Contribution, Goal, User
from app.db.session import get_db
from app.schemas.metas import (
    AporteIn,
    AporteOut,
    AporteRegistradoOut,
    MetaIn,
    MetaOut,
    MetaPatch,
    _validar_modo,
)
from app.services import metas as servicio
from app.services.acceso import obtener_propio
from app.services.errores import DatoInvalido

router = APIRouter(prefix="/goals", tags=["Metas"])
router_aportes = APIRouter(prefix="/contributions", tags=["Aportes"])

ORDEN_METAS = {
    "created_date": Goal.created_date,
    "deadline": Goal.deadline,
    "target_amount": Goal.target_amount,
}
ORDEN_APORTES = {"date": Contribution.date, "created_date": Contribution.created_date}


@router.get("", response_model=list[MetaOut])
def listar(
    sort: str | None = Query(None, description="created_date, deadline o target_amount; '-' para descendente."),
    pag: Paginacion = Depends(paginacion),
    usuario: User = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    consulta = select(Goal).where(Goal.user_id == usuario.id)
    consulta = ordenar(consulta, sort, ORDEN_METAS, "-created_date", (Goal.id,))
    return db.scalars(consulta.limit(pag.limit).offset(pag.offset)).all()


@router.post("", response_model=MetaOut, status_code=201)
def crear(datos: MetaIn, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    meta = Goal(user_id=usuario.id, **datos.model_dump())
    db.add(meta)
    db.commit()
    return meta


@router.get("/{meta_id}", response_model=MetaOut)
def obtener(meta_id: uuid.UUID, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    return obtener_propio(db, Goal, meta_id, usuario.id)


@router.patch("/{meta_id}", response_model=MetaOut)
def actualizar(
    meta_id: uuid.UUID,
    datos: MetaPatch,
    usuario: User = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    meta = obtener_propio(db, Goal, meta_id, usuario.id, bloquear=True)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(meta, campo, valor)
    # Coherencia del registro completo: un modo automático necesita el dato
    # con el que se calcula el aporte.
    try:
        _validar_modo(meta.contribution_mode, meta.contribution_percent, meta.contribution_amount)
    except ValueError as exc:
        db.rollback()
        raise DatoInvalido(str(exc)) from None
    db.commit()
    return meta


@router.delete("/{meta_id}", status_code=204)
def borrar(meta_id: uuid.UUID, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    # Los aportes se borran solos (ON DELETE CASCADE en la base de datos).
    db.delete(obtener_propio(db, Goal, meta_id, usuario.id))
    db.commit()
    return Response(status_code=204)


@router.post("/{meta_id}/contributions", response_model=AporteRegistradoOut, status_code=201)
def registrar_aporte(
    meta_id: uuid.UUID,
    datos: AporteIn,
    usuario: User = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    """Registra un aporte y suma su monto a la meta en una sola operación."""
    aporte, meta = servicio.registrar_aporte(db, usuario.id, meta_id, datos)
    return AporteRegistradoOut(contribution=aporte, goal=meta)


@router_aportes.get("", response_model=list[AporteOut])
def listar_aportes(
    goal_id: uuid.UUID | None = Query(None),
    sort: str | None = Query(None, description="date o created_date; '-' para descendente."),
    pag: Paginacion = Depends(paginacion),
    usuario: User = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    consulta = select(Contribution).where(Contribution.user_id == usuario.id)
    if goal_id is not None:
        consulta = consulta.where(Contribution.goal_id == goal_id)
    consulta = ordenar(consulta, sort, ORDEN_APORTES, "-date", (Contribution.created_date, Contribution.id))
    return db.scalars(consulta.limit(pag.limit).offset(pag.offset)).all()


@router_aportes.delete("/{aporte_id}", response_model=MetaOut)
def deshacer_aporte(aporte_id: uuid.UUID, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Borra el aporte y descuenta su monto de la meta; devuelve la meta."""
    return servicio.deshacer_aporte(db, usuario.id, aporte_id)
