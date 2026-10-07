"""
Entorno de Alembic: cómo se conectan las migraciones a la base de datos.

Usa la MISMA configuración que la aplicación (DATABASE_URL), y la misma
normalización de URL, así que sirve tal cual con la cadena de Supabase.

Para Supabase: ejecuta las migraciones con la conexión "Session pooler"
(puerto 5432) o la directa, no con la de modo transacción (6543). Ver la
sección "Base de datos y Supabase" del README.
"""
from __future__ import annotations

from alembic import context

from app.config import get_settings
from app.db.base import Base
from app.db import models as _modelos  # noqa: F401  (importarlo registra las tablas en Base.metadata)
from app.db.session import BaseDeDatosNoConfiguradaError, crear_motor, normalizar_database_url

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    settings = get_settings()
    if settings.DATABASE_URL is None:
        raise BaseDeDatosNoConfiguradaError(
            "DATABASE_URL no está definida. Configúrala en el archivo .env "
            "(ver .env.example) antes de correr las migraciones."
        )
    return settings.DATABASE_URL.get_secret_value()


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse (alembic upgrade head --sql)."""
    context.configure(
        url=normalizar_database_url(_url()).render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Las pruebas pasan una conexión ya abierta; en uso normal se crea una.
    conexion = config.attributes.get("connection")
    if conexion is not None:
        context.configure(connection=conexion, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    motor = crear_motor(_url(), get_settings())
    with motor.connect() as conexion:
        context.configure(connection=conexion, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    motor.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
