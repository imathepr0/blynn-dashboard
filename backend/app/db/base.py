"""
Base declarativa de SQLAlchemy y tipos compartidos por todos los modelos.

Convención de nombres: SQLAlchemy/Alembic nombran así los índices y
restricciones (ix_, uq_, ck_, fk_, pk_). Sin esto, cada motor inventa sus
propios nombres y las migraciones dejan de ser reproducibles entre
SQLite (pruebas) y Postgres (Supabase).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class FechaHoraUTC(TypeDecorator):
    """Fecha y hora SIEMPRE con zona horaria UTC, en cualquier motor.

    Postgres guarda `timestamptz` y devuelve fechas con zona horaria;
    SQLite (que usamos en las pruebas rápidas) las devuelve "ingenuas"
    (sin zona). Mezclar ambas rompe comparaciones con `TypeError`. Este
    tipo obliga a guardar fechas con zona y las devuelve siempre en UTC,
    así el código de negocio es idéntico en los dos motores.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "Se intentó guardar una fecha sin zona horaria; usa datetime.now(timezone.utc)."
            )
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def ahora_utc() -> datetime:
    """Momento actual con zona UTC (única fuente de "ahora" del backend)."""
    return datetime.now(timezone.utc)
