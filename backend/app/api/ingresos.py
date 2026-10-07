"""
Endpoints de ingresos.

    GET    /api/v1/incomes        lista (filtros: date_from, date_to, type)
    POST   /api/v1/incomes
    GET    /api/v1/incomes/{id}
    PATCH  /api/v1/incomes/{id}
    DELETE /api/v1/incomes/{id}
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.comun import Paginacion, ordenar, paginacion
from app.auth.dependencies import usuario_actual
from app.db.models import Income, User
from app.db.session import get_db
from app.schemas.ingresos import IngresoIn, IngresoOut, IngresoPatch, TipoIngreso
from app.services.acceso import obtener_propio

router = APIRouter(prefix="/incomes", tags=["Ingresos"])

ORDEN = {
    "date": Income.date,
    "created_date": Income.created_date,
    "amount": Income.amount,
}


@router.get("", response_model=list[IngresoOut])
def listar(
    sort: str | None = Query(None, description="date, created_date o amount; '-' para descendente."),
    date_from: dt.date | None = Query(None),
    date_to: dt.date | None = Query(None),
    type: TipoIngreso | None = Query(None),
    pag: Paginacion = Depends(paginacion),
    usuario: User = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    consulta = select(Income).where(Income.user_id == usuario.id)
    if date_from is not None:
        consulta = consulta.where(Income.date >= date_from)
    if date_to is not None:
        consulta = consulta.where(Income.date <= date_to)
    if type is not None:
        consulta = consulta.where(Income.type == type)
    consulta = ordenar(consulta, sort, ORDEN, "-date", (Income.created_date, Income.id))
    return db.scalars(consulta.limit(pag.limit).offset(pag.offset)).all()


@router.post("", response_model=IngresoOut, status_code=201)
def crear(datos: IngresoIn, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    ingreso = Income(user_id=usuario.id, **datos.model_dump())
    db.add(ingreso)
    db.commit()
    return ingreso


@router.get("/{ingreso_id}", response_model=IngresoOut)
def obtener(ingreso_id: uuid.UUID, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    return obtener_propio(db, Income, ingreso_id, usuario.id)


@router.patch("/{ingreso_id}", response_model=IngresoOut)
def actualizar(
    ingreso_id: uuid.UUID,
    datos: IngresoPatch,
    usuario: User = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    ingreso = obtener_propio(db, Income, ingreso_id, usuario.id, bloquear=True)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(ingreso, campo, valor)
    db.commit()
    return ingreso


@router.delete("/{ingreso_id}", status_code=204)
def borrar(ingreso_id: uuid.UUID, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    db.delete(obtener_propio(db, Income, ingreso_id, usuario.id))
    db.commit()
    return Response(status_code=204)
