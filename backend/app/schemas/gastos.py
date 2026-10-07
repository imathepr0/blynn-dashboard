"""Esquemas de gastos."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.comunes import (
    Booleano,
    ColorOpcional,
    EntradaEstricta,
    EntradaParcial,
    Fecha,
    MontoPositivo,
    Salida,
    Texto100,
    Texto255,
    TextoLargoOpcional,
)

MetodoPago = Literal["efectivo", "debito", "credito", "transferencia"]
MAX_GASTOS_POR_LOTE = 50


class GastoIn(EntradaEstricta):
    merchant: Texto255
    description: TextoLargoOpcional = None
    amount: MontoPositivo
    category: Texto100
    date: Fecha
    payment_method: MetodoPago = "debito"
    color: ColorOpcional = None
    is_recurring: Booleano = False
    recurring_active: Booleano = False

    @model_validator(mode="after")
    def _recurrente_activo_requiere_recurrente(self):
        if self.recurring_active and not self.is_recurring:
            raise ValueError("'recurring_active' requiere 'is_recurring'.")
        return self


class GastoLoteIn(EntradaEstricta):
    """Varios gastos a la vez (p. ej. los cobros recurrentes del mes).
    Se guardan todos o ninguno."""

    items: list[GastoIn] = Field(min_length=1, max_length=MAX_GASTOS_POR_LOTE)


class GastoPatch(EntradaParcial):
    NO_NULOS = frozenset(
        {"merchant", "amount", "category", "date", "payment_method", "is_recurring", "recurring_active"}
    )

    merchant: Texto255 | None = None
    description: TextoLargoOpcional = None
    amount: MontoPositivo | None = None
    category: Texto100 | None = None
    date: Fecha | None = None
    payment_method: MetodoPago | None = None
    color: ColorOpcional = None
    is_recurring: Booleano | None = None
    recurring_active: Booleano | None = None


class GastoOut(Salida):
    id: uuid.UUID
    merchant: str
    description: str | None
    amount: int
    category: str
    date: dt.date
    payment_method: str
    color: str | None
    is_recurring: bool
    recurring_active: bool
    created_date: dt.datetime
    updated_date: dt.datetime
