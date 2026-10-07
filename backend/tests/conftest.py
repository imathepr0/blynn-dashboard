"""
Fixtures compartidas por toda la suite de pruebas.

Por defecto las pruebas usan SQLite en memoria (no hay que instalar
nada). Para probar contra Postgres real (lo que importa para Supabase:
bloqueo de filas, RLS, migraciones):

    TEST_DATABASE_URL="postgresql://usuario@host/nombre_test" pytest

SEGURIDAD: con Postgres, el fixture BORRA todo el esquema `public`. Por
eso se niega a correr si el nombre de la base de datos no termina en
"_test" (así no se puede apuntar por error a Supabase de verdad).
"""
import os

# Valores SOLO para pruebas, definidos antes de importar la app: la clave
# JWT es obligatoria al arrancar y bcrypt a costo mínimo hace la suite
# rápida. No afectan a ningún despliegue real.
os.environ.setdefault("JWT_SECRET_KEY", "clave-solo-para-pruebas-" + "x" * 40)
os.environ.setdefault("BCRYPT_ROUNDS", "4")

import pytest  # noqa: E402
from alembic import command as alembic_command  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import make_url, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.auth.rate_limit import reiniciar_limitadores  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402
from app.db import models as _modelos  # noqa: E402,F401  (registra las tablas)
from app.db.base import Base  # noqa: E402
from app.db.session import crear_motor, get_db, normalizar_database_url  # noqa: E402

URL_BD_PRUEBAS = os.environ.get("TEST_DATABASE_URL", "sqlite://")
USA_POSTGRES = normalizar_database_url(URL_BD_PRUEBAS).get_backend_name() == "postgresql"


def migrar_a_head(motor) -> None:
    """Aplica las migraciones de Alembic sobre `motor`."""
    cfg = AlembicConfig("alembic.ini")
    with motor.begin() as conexion:
        cfg.attributes["connection"] = conexion
        alembic_command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def motor_bd():
    settings = Settings()
    if USA_POSTGRES:
        nombre = make_url(URL_BD_PRUEBAS).database or ""
        assert nombre.endswith("_test"), (
            f"Por seguridad, la base de datos de pruebas debe terminar en '_test' (es '{nombre}'). "
            "Este fixture borra todo el esquema public."
        )
        motor = crear_motor(URL_BD_PRUEBAS, settings)
        with motor.begin() as conexion:
            conexion.execute(text("DROP SCHEMA public CASCADE"))
            conexion.execute(text("CREATE SCHEMA public"))
        migrar_a_head(motor)  # en Postgres se prueban las migraciones reales
    else:
        motor = crear_motor(URL_BD_PRUEBAS, settings)
        Base.metadata.create_all(motor)
    yield motor
    motor.dispose()


@pytest.fixture
def fabrica_sesiones(motor_bd):
    fabrica = sessionmaker(bind=motor_bd, autoflush=False, expire_on_commit=False)
    yield fabrica
    # Deja las tablas vacías para la prueba siguiente.
    with motor_bd.begin() as conexion:
        for tabla in reversed(Base.metadata.sorted_tables):
            conexion.execute(tabla.delete())


@pytest.fixture
def db(fabrica_sesiones):
    sesion = fabrica_sesiones()
    yield sesion
    sesion.close()


@pytest.fixture
def settings_auth() -> Settings:
    return Settings(
        JWT_SECRET_KEY="clave-solo-para-pruebas-" + "x" * 40,
        BCRYPT_ROUNDS=4,
        AUTH_RATE_LIMIT_ENABLED=False,
    )


@pytest.fixture
def crear_cliente(fabrica_sesiones, settings_auth):
    """Fábrica de TestClient con la base de datos de pruebas y la
    configuración de `settings_auth` (más los cambios que pida la prueba)."""
    from app.main import app

    def _crear(**cambios) -> TestClient:
        config = settings_auth.model_copy(update=cambios)

        def _get_db():
            sesion = fabrica_sesiones()
            try:
                yield sesion
            finally:
                sesion.close()

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_settings] = lambda: config
        reiniciar_limitadores()
        return TestClient(app)

    yield _crear
    app.dependency_overrides.clear()
    reiniciar_limitadores()


@pytest.fixture
def cliente(crear_cliente) -> TestClient:
    return crear_cliente()


@pytest.fixture
def ana(cliente):
    from tests.utils import Usuario

    return Usuario(cliente, "ana@correo.cl")


@pytest.fixture
def beto(cliente):
    from tests.utils import Usuario

    return Usuario(cliente, "beto@correo.cl")
