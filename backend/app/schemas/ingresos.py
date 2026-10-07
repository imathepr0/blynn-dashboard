"""Esquemas de ingresos."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from app.schemas.comunes import (
    ColorOpcional,
    EntradaEstricta,
    EntradaParcial,
    Fecha,
    MontoPositivo,
    Salida,
    Texto255,
    TextoLargoOpcional,
)

TipoIngreso = Literal["sueldo", "bono", "transferencia", "efectivo", "otros"]


class IngresoIn(EntradaEstricta):
    source: Texto255
    description: TextoLargoOpcional = None
    amount: MontoPositivo
    date: Fecha
    type: TipoIngreso = "otros"
    color: ColorOpcional = None


class IngresoPatch(EntradaParcial):
    NO_NULOS = frozenset({"source", "amount", "date", "type"})

    source: Texto255 | None = None
    description: TextoLargoOpcional = None
    amount: MontoPositivo | None = None
    date: Fecha | None = None
    type: TipoIngreso | None = None
    color: ColorOpcional = None


class IngresoOut(Salida):
    id: uuid.UUID
    source: str
    description: str | None
    amount: int
    date: dt.date
    type: str
    color: str | None
    created_date: dt.datetime
    updated_date: dt.datetime
