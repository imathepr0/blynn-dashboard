"""Categorías: creación de las de por defecto y renombrado seguro."""
from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Category, Expense

# Fuente única de las categorías por defecto. El frontend ya no tiene una copia:
# las pide con `POST /categories/defaults`.
CATEGORIAS_POR_DEFECTO: tuple[dict, ...] = (
    {"name": "Alimentación", "color": "#3b82f6", "icon": "ShoppingBag", "budget": 0},
    {"name": "Transporte", "color": "#a78bfa", "icon": "Car", "budget": 0},
    {"name": "Hogar", "color": "#fb923c", "icon": "Home", "budget": 0},
    {"name": "Suscripciones", "color": "#facc15", "icon": "RefreshCw", "budget": 0},
    {"name": "Salud", "color": "#22c55e", "icon": "HeartPulse", "budget": 0},
    {"name": "Ropa", "color": "#ec4899", "icon": "Shirt", "budget": 0},
    {"name": "Arriendo", "color": "#14b8a6", "icon": "Building2", "budget": 0},
    {"name": "Educación", "color": "#8b5cf6", "icon": "GraduationCap", "budget": 0},
    {"name": "Entretenimiento", "color": "#f97316", "icon": "Clapperboard", "budget": 0},
    {"name": "Transferencias", "color": "#06b6d4", "icon": "ArrowLeftRight", "budget": 0},
    {"name": "Tecnología", "color": "#6366f1", "icon": "Laptop", "budget": 0},
    {"name": "Otros", "color": "#f87171", "icon": "Package", "budget": 0},
)


def agregar_categorias_faltantes(db: Session, usuario_id: uuid.UUID) -> int:
    """Agrega (sin confirmar) las categorías por defecto que el usuario aún
    no tiene, comparando el nombre sin distinguir mayúsculas. Devuelve
    cuántas agregó."""
    existentes = {n.lower() for n in db.scalars(select(Category.name).where(Category.user_id == usuario_id))}
    faltantes = [c for c in CATEGORIAS_POR_DEFECTO if c["name"].lower() not in existentes]
    db.add_all(Category(user_id=usuario_id, **c) for c in faltantes)
    db.flush()
    return len(faltantes)


def asegurar_categorias_por_defecto(db: Session, usuario_id: uuid.UUID) -> None:
    """Operación IDEMPOTENTE: llamarla una, dos o diez veces (incluso desde
    dos pestañas a la vez) deja exactamente las mismas categorías.

    Si una petición simultánea ganó la carrera, la restricción única de la
    base de datos hace fallar nuestro INSERT; se deshace y se reintenta
    leyendo lo que ya quedó guardado.
    """
    ultimo_error: IntegrityError | None = None
    for _ in range(3):
        try:
            if agregar_categorias_faltantes(db, usuario_id) == 0:
                db.rollback()  # nada que confirmar
                return
            db.commit()
            return
        except IntegrityError as exc:
            db.rollback()
            ultimo_error = exc
    raise ultimo_error  # type: ignore[misc]


def renombrar_categoria_en_gastos(
    db: Session, usuario_id: uuid.UUID, nombre_anterior: str, nombre_nuevo: str
) -> None:
    """Los gastos referencian la categoría por su NOMBRE. Al renombrarla,
    los gastos del MISMO usuario con el nombre anterior pasan al nuevo; si
    no, quedarían huérfanos (sin categoría en el listado)."""
    db.execute(
        update(Expense)
        .where(Expense.user_id == usuario_id, Expense.category == nombre_anterior)
        .values(category=nombre_nuevo)
    )
