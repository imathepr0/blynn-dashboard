"""
Conexión a la base de datos y sesiones por petición.

Diseñado para funcionar con el Postgres de Supabase (plan gratuito):

* Acepta la cadena de conexión tal como la entrega Supabase
  ("postgresql://..." o "postgres://...") y la convierte al formato de
  SQLAlchemy + psycopg 3.
* Desactiva las "prepared statements" del servidor: el pooler de Supabase
  en modo transacción (puerto 6543) no las soporta.
* Fuerza SSL cuando el destino es Supabase.
* El motor se crea de forma perezosa (la primera vez que se usa), así que
  importar la aplicación no exige tener base de datos (útil para las
  pruebas y para comandos que no la necesitan).
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_HOSTS_SUPABASE = ("supabase.com", "supabase.co")


class BaseDeDatosNoConfiguradaError(RuntimeError):
    """Se intentó usar la base de datos sin haber definido DATABASE_URL."""


def normalizar_database_url(url: str) -> URL:
    """Convierte la URL que entrega el proveedor al formato de SQLAlchemy.

    * "postgres://" y "postgresql://" -> "postgresql+psycopg://" (psycopg 3).
    * Si el host es de Supabase y no se indicó `sslmode`, agrega
      `sslmode=require` (Supabase exige conexión cifrada).
    * Otros motores (p. ej. "sqlite://" en pruebas) se dejan como están.
    """
    parsed = make_url(url)
    # SQLAlchemy 2 ya no reconoce "postgres://" (el nombre corto que usan
    # varios proveedores, incluida la documentación de Supabase).
    if parsed.drivername == "postgres":
        parsed = parsed.set(drivername="postgresql")
    if parsed.get_backend_name() != "postgresql":
        return parsed

    if parsed.drivername == "postgresql":
        parsed = parsed.set(drivername="postgresql+psycopg")

    host = parsed.host or ""
    if any(host.endswith(h) for h in _HOSTS_SUPABASE) and "sslmode" not in parsed.query:
        parsed = parsed.update_query_dict({"sslmode": "require"})
    return parsed


def crear_motor(database_url: str, settings: Settings) -> Engine:
    """Crea un motor SQLAlchemy con los parámetros seguros para Supabase."""
    url = normalizar_database_url(database_url)

    if url.get_backend_name() == "sqlite":
        kwargs: dict = {
            "connect_args": {"check_same_thread": False},
            "hide_parameters": True,
        }
        if url.database in (None, "", ":memory:"):
            kwargs["poolclass"] = StaticPool  # una única conexión compartida
        motor = create_engine(url, **kwargs)

        # SQLite NO hace cumplir las claves foráneas (ni los borrados en
        # cascada) salvo que se le pida en cada conexión. Postgres sí.
        @event.listens_for(motor, "connect")
        def _activar_claves_foraneas(conexion_dbapi, _registro):
            cursor = conexion_dbapi.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return motor

    kwargs = {
        # Los mensajes de error de SQLAlchemy incluyen por defecto los
        # VALORES de la consulta (correos, hashes de contraseña, huellas de
        # tokens). Con esto no llegan a los logs.
        "hide_parameters": True,
        "pool_pre_ping": True,  # descarta conexiones que el pooler ya cerró
        # prepare_threshold=None -> sin prepared statements en el servidor
        # (obligatorio para el pooler en modo transacción de Supabase;
        # inofensivo en conexiones directas).
        "connect_args": {"prepare_threshold": None},
    }
    if settings.DB_USE_NULL_POOL:
        kwargs["poolclass"] = NullPool
    else:
        kwargs.update(
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
            pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
        )
    return create_engine(url, **kwargs)


@lru_cache
def obtener_motor() -> Engine:
    """Motor único del proceso (se crea la primera vez que se pide)."""
    settings = get_settings()
    if settings.DATABASE_URL is None:
        raise BaseDeDatosNoConfiguradaError(
            "DATABASE_URL no está definida. Configúrala en el archivo .env "
            "(ver .env.example)."
        )
    return crear_motor(settings.DATABASE_URL.get_secret_value(), settings)


@lru_cache
def _fabrica_de_sesiones() -> sessionmaker[Session]:
    # expire_on_commit=False: después de un commit los objetos siguen
    # siendo legibles sin volver a consultar la base de datos.
    return sessionmaker(bind=obtener_motor(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición.

    Si el código lanza una excepción sin haber hecho commit, se deshace
    (rollback) todo lo pendiente; la sesión siempre se cierra.
    """
    db = _fabrica_de_sesiones()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
