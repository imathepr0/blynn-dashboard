"""
Modelos de la base de datos (Etapas 1 y 2).

Replican lo que modelaban las entidades originales
(`respaldo-original/entities/*.jsonc`), con los MISMOS nombres de campo que ya usa
el frontend (`merchant`, `payment_method`, `target_amount`, `created_date`,
...) para que migrar las pantallas después sea un cambio de origen de
datos y no un rediseño.

Decisiones de diseño (todas pensadas para Postgres/Supabase, y para que
las pruebas rápidas con SQLite se comporten igual):

* Ids UUID generados por la aplicación (no numéricos autoincrementales):
  no se pueden adivinar recorriendo 1, 2, 3...
* Montos en pesos chilenos como ENTEROS (`BigInteger`): el frontend solo
  produce enteros (`parseAmount` descarta todo lo que no sea dígito) y
  evita errores de redondeo de los decimales flotantes.
* Valores permitidos ("efectivo", "debito"...) con `CHECK` en la base de
  datos en vez de tipos ENUM de Postgres: cambiarlos después es una
  migración simple, no un `ALTER TYPE`.
* Cada dato de negocio pertenece a un usuario (`user_id`, con borrado en
  cascada). Toda consulta de las etapas siguientes DEBE filtrar por el
  usuario autenticado; la base de datos refuerza lo que puede (ver la
  clave foránea compuesta de `Contribution`).
* Tablas creadas SIN "Row Level Security" abierto: ver la migración
  (`migrations/versions/`), que activa RLS para que el Data API público
  de Supabase no exponga estas tablas.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, FechaHoraUTC

# JSON genérico en SQLite (pruebas) y JSONB en Postgres (producción).
JsonPortable = JSON().with_variant(JSONB(), "postgresql")

METODOS_PAGO = ("efectivo", "debito", "credito", "transferencia")
TIPOS_INGRESO = ("sueldo", "bono", "transferencia", "efectivo", "otros")
MODOS_APORTE_META = ("manual", "percent_surplus", "fixed")
FRECUENCIAS_APORTE = ("dias", "semanas", "meses")
MODOS_APORTE = ("manual", "aprobado", "auto")
ROLES = ("user", "admin")


def _en(columna: str, valores: tuple[str, ...]) -> str:
    """Arma la expresión `columna IN ('a', 'b', ...)` para un CHECK."""
    lista = ", ".join(f"'{v}'" for v in valores)
    return f"{columna} IN ({lista})"


class _Fechas:
    """Columnas de auditoría comunes (mismos nombres que la plataforma anterior)."""

    created_date: Mapped[dt.datetime] = mapped_column(
        FechaHoraUTC, server_default=func.now(), nullable=False
    )
    updated_date: Mapped[dt.datetime] = mapped_column(
        FechaHoraUTC, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(_Fechas, Base):
    """Cuenta de usuario (entidad `User` original + credenciales propias)."""

    __tablename__ = "users"
    __table_args__ = (
        # El correo se guarda SIEMPRE en minúsculas (lo hace el servicio);
        # este CHECK lo garantiza aunque alguien inserte a mano.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint(_en("role", ROLES), name="role_valido"),
        CheckConstraint("monthly_budget >= 0", name="monthly_budget_no_negativo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    # Hash bcrypt de la contraseña. NUNCA la contraseña. Nunca sale en
    # ninguna respuesta de la API (los esquemas de salida son listas
    # blancas explícitas).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="user", server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    monthly_budget: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    preferences: Mapped[dict] = mapped_column(
        JsonPortable, default=dict, server_default=text("'{}'"), nullable=False
    )
    last_login_date: Mapped[dt.datetime | None] = mapped_column(FechaHoraUTC)

    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Category(_Fechas, Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("budget >= 0", name="budget_no_negativo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50))  # nombre de icono lucide
    budget: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")


# No puede haber dos categorías con el mismo nombre para un mismo usuario
# (sin distinguir mayúsculas): los gastos referencian la categoría por su
# NOMBRE, así que un duplicado dejaría gastos ambiguos. El frontend ya lo
# impedía (Categorias.jsx); ahora también lo garantiza la base de datos.
Index(
    "uq_categories_user_id_lower_name",
    Category.user_id,
    func.lower(Category.name),
    unique=True,
)


class Expense(_Fechas, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_no_negativo"),
        CheckConstraint(_en("payment_method", METODOS_PAGO), name="payment_method_valido"),
        Index("ix_expenses_user_id_date", "user_id", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    merchant: Mapped[str] = mapped_column(String(255), nullable=False)
    # Detalle del gasto: items con precio, uno por línea.
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Nombre de la categoría (no id), igual que hoy en el frontend.
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str] = mapped_column(
        String(20), default="debito", server_default="debito"
    )
    color: Mapped[str | None] = mapped_column(String(20))
    is_recurring: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    recurring_active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )


class Income(_Fechas, Base):
    __tablename__ = "incomes"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_no_negativo"),
        CheckConstraint(_en("type", TIPOS_INGRESO), name="type_valido"),
        Index("ix_incomes_user_id_date", "user_id", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(255), nullable=False)  # quién pagó
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="otros", server_default="otros")
    color: Mapped[str | None] = mapped_column(String(20))


class Goal(_Fechas, Base):
    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("target_amount >= 0", name="target_amount_no_negativo"),
        CheckConstraint("current_amount >= 0", name="current_amount_no_negativo"),
        CheckConstraint(_en("contribution_mode", MODOS_APORTE_META), name="contribution_mode_valido"),
        CheckConstraint(
            _en("contribution_frequency", FRECUENCIAS_APORTE), name="contribution_frequency_valida"
        ),
        # Permite que `Contribution` apunte a (id, user_id) y así la base
        # de datos impida que un aporte cuelgue de la meta de OTRO usuario.
        UniqueConstraint("id", "user_id", name="uq_goals_id_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_amount: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    deadline: Mapped[dt.date | None] = mapped_column(Date)
    color: Mapped[str] = mapped_column(String(20), default="#22c55e", server_default="#22c55e")
    contribution_mode: Mapped[str] = mapped_column(
        String(20), default="manual", server_default="manual"
    )
    # Porcentaje del excedente mensual a aportar (p. ej. 12.5).
    contribution_percent: Mapped[float | None] = mapped_column(Float)
    contribution_amount: Mapped[int | None] = mapped_column(BigInteger)
    contribution_frequency: Mapped[str] = mapped_column(
        String(20), default="meses", server_default="meses"
    )
    next_contribution_date: Mapped[dt.date | None] = mapped_column(Date)
    auto_approved_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Contribution(_Fechas, Base):
    __tablename__ = "contributions"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_no_negativo"),
        CheckConstraint(_en("mode", MODOS_APORTE), name="mode_valido"),
        # Clave foránea COMPUESTA: (goal_id, user_id) debe existir junto en
        # `goals`. Un aporte solo puede colgar de una meta del mismo dueño;
        # aunque un endpoint futuro tuviera un descuido, la base de datos
        # lo rechaza. Al borrar la meta se borran sus aportes.
        ForeignKeyConstraint(
            ["goal_id", "user_id"],
            ["goals.id", "goals.user_id"],
            ondelete="CASCADE",
            name="fk_contributions_goal_owner",
        ),
        Index("ix_contributions_user_id_date", "user_id", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    goal_title: Mapped[str | None] = mapped_column(String(255))
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")


class RefreshToken(Base):
    """Sesión renovable (Etapa 2).

    El token real es un texto aleatorio que solo conoce el cliente; aquí
    se guarda únicamente su HUELLA (SHA-256). Si alguien copiara la base
    de datos, no podría usar los tokens. Todos los tokens que descienden
    de un mismo login comparten `family_id`, lo que permite revocar la
    sesión completa si se detecta reutilización (posible robo).
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_expires_at", "expires_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_date: Mapped[dt.datetime] = mapped_column(
        FechaHoraUTC, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[dt.datetime] = mapped_column(FechaHoraUTC, nullable=False)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(FechaHoraUTC)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class IntentoLimitado(Base):
    """Un evento contado por un límite de intentos (inicios de sesión fallidos, registros,
    escaneos...). Vive en la base de datos y no en la memoria del proceso para que el
    límite valga aunque el servidor corra en varias instancias (Vercel, Cloud Run).

    `clave` es una HUELLA (SHA-256) de "límite|correo+IP": ni el correo ni la IP quedan
    guardados en claro. `ts` son segundos desde 1970 (número simple, igual en Postgres y SQLite).
    """

    __tablename__ = "intentos_limitados"
    __table_args__ = (Index("ix_intentos_limitados_nombre_clave_ts", "nombre", "clave", "ts"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(40), nullable=False)
    clave: Mapped[str] = mapped_column(String(64), nullable=False)
    ts: Mapped[float] = mapped_column(Float, nullable=False)


class EscaneoActivo(Base):
    """Un escaneo de boleta en curso. La clave primaria es el usuario: tomar el turno es un
    INSERT que falla si ya hay uno, de forma atómica aunque dos peticiones lleguen a
    instancias distintas. Si un proceso muere sin liberarlo, el turno vence solo."""

    __tablename__ = "escaneos_en_curso"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    iniciado_ts: Mapped[float] = mapped_column(Float, nullable=False)
