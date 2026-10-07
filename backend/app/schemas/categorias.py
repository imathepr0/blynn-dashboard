"""Esquemas de categorías."""
from __future__ import annotations

import datetime as dt
import uuid

from app.schemas.comunes import (
    Color,
    EntradaEstricta,
    EntradaParcial,
    Icono,
    Monto,
    Salida,
    Texto100,
)


class CategoriaIn(EntradaEstricta):
    name: Texto100
    color: Color
    icon: Icono | None = None
    budget: Monto = 0


class CategoriaPatch(EntradaParcial):
    NO_NULOS = frozenset({"name", "color", "budget"})

    name: Texto100 | None = None
    color: Color | None = None
    icon: Icono | None = None
    budget: Monto | None = None


class CategoriaOut(Salida):
    id: uuid.UUID
    name: str
    color: str
    icon: str | None
    budget: int
    created_date: dt.datetime
    updated_date: dt.datetime
