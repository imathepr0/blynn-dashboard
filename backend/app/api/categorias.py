"""
Endpoints de categorías.

    GET    /api/v1/categories            lista las del usuario
    POST   /api/v1/categories            crea una (409 si el nombre ya existe)
    POST   /api/v1/categories/defaults   crea las por defecto que falten (idempotente)
    GET    /api/v1/categories/{id}
    PATCH  /api/v1/categories/{id}       (renombrar actualiza también sus gastos)
    DELETE /api/v1/categories/{id}       los gastos conservan el nombre
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.comun import Paginacion, ordenar, paginacion
from app.auth.dependencies import usuario_actual
from app.db.models import Category, User
from app.db.session import get_db
from app.schemas.categorias import CategoriaIn, CategoriaOut, CategoriaPatch
from app.services.acceso import obtener_propio
from app.services.categorias import (
    asegurar_categorias_por_defecto,
    renombrar_categoria_en_gastos,
)
from app.services.errores import Conflicto

router = APIRouter(prefix="/categories", tags=["Categorías"])

ORDEN = {
    "created_date": Category.created_date,
    "name": Category.name,
    "budget": Category.budget,
}
_MSG_DUPLICADA = "Ya existe una categoría con ese nombre."


def _nombre_ya_existe(db: Session, usuario_id: uuid.UUID, nombre: str) -> bool:
    """Misma comparación que el índice único de la base de datos:
    `lower(nombre)`, calculada por la propia base de datos en ambos lados."""
    return (
        db.scalar(
            select(Category.id).where(
                Category.user_id == usuario_id, func.lower(Category.name) == func.lower(nombre)
            )
        )
        is not None
    )


@router.get("", response_model=list[CategoriaOut])
def listar(
    sort: str | None = Query(None, description="created_date, name o budget; '-' para descendente."),
    pag: Paginacion = Depends(paginacion),
    usuario: User = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    consulta = select(Category).where(Category.user_id == usuario.id)
    consulta = ordenar(consulta, sort, ORDEN, "created_date", (Category.id,))
    return db.scalars(consulta.limit(pag.limit).offset(pag.offset)).all()


@router.post("", response_model=CategoriaOut, status_code=201)
def crear(datos: CategoriaIn, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    categoria = Category(user_id=usuario.id, **datos.model_dump())
    db.add(categoria)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if _nombre_ya_existe(db, usuario.id, datos.name):
            raise Conflicto(_MSG_DUPLICADA) from None
        raise
    return categoria


@router.post("/defaults", response_model=list[CategoriaOut])
def crear_por_defecto(usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Crea las categorías por defecto que falten. Se puede llamar cuantas
    veces sea (también desde dos pestañas a la vez) sin duplicar nada."""
    asegurar_categorias_por_defecto(db, usuario.id)
    consulta = select(Category).where(Category.user_id == usuario.id)
    return db.scalars(ordenar(consulta, None, ORDEN, "created_date", (Category.id,))).all()


@router.get("/{categoria_id}", response_model=CategoriaOut)
def obtener(categoria_id: uuid.UUID, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    return obtener_propio(db, Category, categoria_id, usuario.id)


@router.patch("/{categoria_id}", response_model=CategoriaOut)
def actualizar(
    categoria_id: uuid.UUID,
    datos: CategoriaPatch,
    usuario: User = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    categoria = obtener_propio(db, Category, categoria_id, usuario.id, bloquear=True)
    cambios = datos.model_dump(exclude_unset=True)
    nombre_anterior = categoria.name
    for campo, valor in cambios.items():
        setattr(categoria, campo, valor)
    try:
        if "name" in cambios and cambios["name"] != nombre_anterior:
            renombrar_categoria_en_gastos(db, usuario.id, nombre_anterior, cambios["name"])
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflicto(_MSG_DUPLICADA) from None
    return categoria


@router.delete("/{categoria_id}", status_code=204)
def borrar(categoria_id: uuid.UUID, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    categoria = obtener_propio(db, Category, categoria_id, usuario.id)
    db.delete(categoria)
    db.commit()
    return Response(status_code=204)
