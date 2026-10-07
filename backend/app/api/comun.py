"""Piezas compartidas por los routers de datos: paginación y orden."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query
from sqlalchemy import Select
from sqlalchemy.orm import InstrumentedAttribute

from app.services.errores import DatoInvalido


@dataclass
class Paginacion:
    limit: int
    offset: int


def paginacion(
    limit: int = Query(500, ge=1, le=1000, description="Máximo de registros a devolver."),
    offset: int = Query(0, ge=0, le=100_000, description="Cuántos registros saltar."),
) -> Paginacion:
    return Paginacion(limit=limit, offset=offset)


def ordenar(
    consulta: Select,
    sort: str | None,
    permitidos: dict[str, InstrumentedAttribute],
    por_defecto: str,
    desempate: tuple[InstrumentedAttribute, ...],
) -> Select:
    """Aplica `sort` ("campo" ascendente o "-campo" descendente) SOLO si el
    campo está en la lista blanca. `desempate` fija un orden estable
    cuando varios registros empatan (paginar sin él puede repetir o saltar
    filas)."""
    criterio = sort or por_defecto
    descendente = criterio.startswith("-")
    campo = criterio.lstrip("-")
    if campo not in permitidos:
        opciones = ", ".join(sorted(permitidos))
        raise DatoInvalido(f"No se puede ordenar por '{campo}'. Opciones: {opciones}.")
    columna = permitidos[campo]
    principal = columna.desc() if descendente else columna.asc()
    return consulta.order_by(principal, *[c.desc() for c in desempate])
