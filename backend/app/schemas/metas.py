"""Esquemas de metas de ahorro y de sus aportes."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.schemas.comunes import (
    Color,
    EntradaEstricta,
    EntradaParcial,
    Fecha,
    Monto,
    MontoPositivo,
    Salida,
    Texto255,
)

ModoAporteMeta = Literal["manual", "percent_surplus", "fixed"]
FrecuenciaAporte = Literal["dias", "semanas", "meses"]
ModoAporte = Literal["manual", "aprobado", "auto"]
# Porcentaje del excedente mensual (0 < p <= 100). `allow_inf_nan=False`
# evita NaN/Infinity, que no son JSON válido pero algunos clientes envían.
Porcentaje = Annotated[float, Field(strict=True, gt=0, le=100, allow_inf_nan=False)]


def _validar_modo(modo: str, porcentaje, monto) -> None:
    """Un modo automático exige el dato con el que se calcula el aporte."""
    if modo == "percent_surplus" and porcentaje is None:
        raise ValueError("El modo 'percent_surplus' requiere 'contribution_percent'.")
    if modo == "fixed" and monto is None:
        raise ValueError("El modo 'fixed' requiere 'contribution_amount'.")


class MetaIn(EntradaEstricta):
    title: Texto255
    target_amount: MontoPositivo
    current_amount: Monto = 0
    deadline: Fecha | None = None
    color: Color = "#22c55e"
    contribution_mode: ModoAporteMeta = "manual"
    contribution_percent: Porcentaje | None = None
    contribution_amount: MontoPositivo | None = None
    contribution_frequency: FrecuenciaAporte = "meses"
    next_contribution_date: Fecha | None = None

    @model_validator(mode="after")
    def _modo_coherente(self):
        _validar_modo(self.contribution_mode, self.contribution_percent, self.contribution_amount)
        return self


class MetaPatch(EntradaParcial):
    # `auto_approved_count` no se puede enviar: lo lleva el servidor al
    # registrar aportes aprobados.
    NO_NULOS = frozenset(
        {"title", "target_amount", "current_amount", "color", "contribution_mode", "contribution_frequency"}
    )

    title: Texto255 | None = None
    target_amount: MontoPositivo | None = None
    current_amount: Monto | None = None
    deadline: Fecha | None = None
    color: Color | None = None
    contribution_mode: ModoAporteMeta | None = None
    contribution_percent: Porcentaje | None = None
    contribution_amount: MontoPositivo | None = None
    contribution_frequency: FrecuenciaAporte | None = None
    next_contribution_date: Fecha | None = None


class MetaOut(Salida):
    id: uuid.UUID
    title: str
    target_amount: int
    current_amount: int
    deadline: dt.date | None
    color: str
    contribution_mode: str
    contribution_percent: float | None
    contribution_amount: int | None
    contribution_frequency: str
    next_contribution_date: dt.date | None
    auto_approved_count: int
    created_date: dt.datetime
    updated_date: dt.datetime


class AporteIn(EntradaEstricta):
    amount: MontoPositivo
    date: Fecha
    mode: ModoAporte = "manual"
    # Próxima fecha de aporte automático (la calcula el cliente según la
    # frecuencia de la meta); si no se envía, no se toca.
    next_contribution_date: Fecha | None = None


class AporteOut(Salida):
    id: uuid.UUID
    goal_id: uuid.UUID
    goal_title: str | None
    amount: int
    date: dt.date
    mode: str
    created_date: dt.datetime


class AporteRegistradoOut(Salida):
    """Resultado de registrar un aporte: el aporte y la meta ya actualizada."""

    contribution: AporteOut
    goal: MetaOut
