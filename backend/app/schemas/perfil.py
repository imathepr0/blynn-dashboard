"""Esquemas del perfil del usuario (`updateMe` de la plataforma anterior)."""
from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator, field_validator

from app.schemas.comunes import (
    Booleano,
    EntradaEstricta,
    EntradaParcial,
    Monto,
    Texto120,
    _vacio_a_nulo,
)

class PreferenciasIn(EntradaEstricta):
    """Preferencias que hoy usa la app. Una clave nueva del frontend
    exige agregarla aquí a propósito (así el JSON no crece sin control)."""

    notifications: Booleano


class PerfilPatch(EntradaParcial):
    # `email`, `role`, `is_active`, `id`... NO están: no se pueden cambiar
    # desde aquí. Tampoco hay foto de perfil: se quitó (todos usan el mismo avatar).
    NO_NULOS = frozenset({"onboarded", "monthly_budget", "preferences"})

    full_name: Annotated[Texto120 | None, BeforeValidator(_vacio_a_nulo)] = None
    onboarded: Booleano | None = None
    monthly_budget: Monto | None = None
    preferences: PreferenciasIn | None = None


class ReinicioIn(EntradaEstricta):
    """Confirmación explícita para una operación que borra datos: solo vale
    el `true` exacto de JSON (ni `1`, ni `"true"`, ni `"yes"`)."""

    confirm: Booleano

    @field_validator("confirm")
    @classmethod
    def _debe_ser_verdadero(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Debes enviar 'confirm': true para reiniciar la cuenta.")
        return v
