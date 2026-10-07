"""
Endpoints de gastos.

    GET    /api/v1/expenses          lista (filtros: date_from, date_to, category,
                                     is_recurring, recurring_active; orden y paginación)
    POST   /api/v1/expenses          crea uno
    POST   /api/v1/expenses/bulk     crea hasta 50 a la vez (todos o ninguno)
    GET    /api/v1/expenses/{id}
    PATCH  /api/v1/expenses/{id}
    DELETE /api/v1/expenses/{id}
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.comun import Paginacion, ordenar, paginacion
from app.auth.dependencies import usuario_actual
from app.db.models import Expense, User
from app.db.session import get_db
from app.schemas.gastos import GastoIn, GastoLoteIn, GastoOut, GastoPatch
from app.services.acceso import obtener_propio
from app.services.errores import DatoInvalido

router = APIRouter(prefix="/expenses", tags=["Gastos"])

ORDEN = {
    "date": Expense.date,
    "created_date": Expense.created_date,
    "amount": Expense.amount,
}


@router.get("", response_model=list[GastoOut])
def listar(
    sort: str | None = Query(None, description="date, created_date o amount; '-' para descendente."),
    date_from: dt.date | None = Query(None),
    date_to: dt.date | None = Query(None),
    category: str | None = Query(None, max_length=100),
    is_recurring: bool | None = Query(None),
    recurring_active: bool | None = Query(None),
    pag: Paginacion = Depends(paginacion),
    usuario: User = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    consulta = select(Expense).where(Expense.user_id == usuario.id)
    if date_from is not None:
        consulta = consulta.where(Expense.date >= date_from)
    if date_to is not None:
        consulta = consulta.where(Expense.date <= date_to)
    if category is not None:
        consulta = consulta.where(Expense.category == category)
    if is_recurring is not None:
        consulta = consulta.where(Expense.is_recurring == is_recurring)
    if recurring_active is not None:
        consulta = consulta.where(Expense.recurring_active == recurring_active)
    consulta = ordenar(consulta, sort, ORDEN, "-date", (Expense.created_date, Expense.id))
    return db.scalars(consulta.limit(pag.limit).offset(pag.offset)).all()


@router.post("", response_model=GastoOut, status_code=201)
def crear(datos: GastoIn, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    gasto = Expense(user_id=usuario.id, **datos.model_dump())
    db.add(gasto)
    db.commit()
    return gasto


@router.post("/bulk", response_model=list[GastoOut], status_code=201)
def crear_en_lote(datos: GastoLoteIn, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    gastos = [Expense(user_id=usuario.id, **item.model_dump()) for item in datos.items]
    db.add_all(gastos)
    db.commit()
    return gastos


@router.get("/{gasto_id}", response_model=GastoOut)
def obtener(gasto_id: uuid.UUID, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    return obtener_propio(db, Expense, gasto_id, usuario.id)


@router.patch("/{gasto_id}", response_model=GastoOut)
def actualizar(
    gasto_id: uuid.UUID,
    datos: GastoPatch,
    usuario: User = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    gasto = obtener_propio(db, Expense, gasto_id, usuario.id, bloquear=True)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(gasto, campo, valor)
    # Regla del registro completo (no solo de lo enviado).
    if gasto.recurring_active and not gasto.is_recurring:
        db.rollback()
        raise DatoInvalido("'recurring_active' requiere 'is_recurring'.")
    db.commit()
    return gasto


@router.delete("/{gasto_id}", status_code=204)
def borrar(gasto_id: uuid.UUID, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    db.delete(obtener_propio(db, Expense, gasto_id, usuario.id))
    db.commit()
    return Response(status_code=204)
