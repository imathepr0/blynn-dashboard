"""
Pruebas de migraciones y de compatibilidad con Supabase. Solo corren
contra Postgres real (TEST_DATABASE_URL); con SQLite se omiten.
"""
import pytest
from alembic import command as alembic_command
from alembic.autogenerate import compare_metadata
from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from sqlalchemy import text

from app.config import Settings
from app.db.base import Base
from app.db.session import crear_motor
from tests.conftest import URL_BD_PRUEBAS, USA_POSTGRES, migrar_a_head

pytestmark = pytest.mark.skipif(not USA_POSTGRES, reason="requiere Postgres real")

TABLAS = [
    "categories", "contributions", "escaneos_en_curso", "expenses", "goals", "incomes",
    "intentos_limitados", "refresh_tokens", "users",
]


def _reiniciar_esquema(conexion) -> None:
    conexion.execute(text("DROP SCHEMA public CASCADE"))
    conexion.execute(text("CREATE SCHEMA public"))


def test_las_migraciones_coinciden_exactamente_con_los_modelos(motor_bd):
    """Si alguien cambia un modelo y olvida crear la migración, esto falla."""
    with motor_bd.connect() as conexion:
        diferencias = compare_metadata(MigrationContext.configure(conexion), Base.metadata)
    assert diferencias == []


def test_todas_las_tablas_tienen_row_level_security_activado(motor_bd):
    """Sin esto, el Data API público de Supabase expondría las tablas."""
    with motor_bd.connect() as conexion:
        filas = conexion.execute(
            text(
                "SELECT c.relname, c.relrowsecurity FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname <> 'alembic_version' "
                "ORDER BY c.relname"
            )
        ).all()
    assert [f[0] for f in filas] == TABLAS
    sin_rls = [f[0] for f in filas if not f[1]]
    assert sin_rls == [], f"Tablas SIN Row Level Security: {sin_rls}"


def test_los_roles_publicos_de_supabase_quedan_sin_permisos():
    """Simula Supabase: los roles `anon` y `authenticated` reciben permisos
    por defecto sobre las tablas nuevas. La migración debe quitárselos."""
    motor = crear_motor(URL_BD_PRUEBAS, Settings())
    with motor.begin() as c:
        c.execute(text("""
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon NOLOGIN; END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
            END $$;"""))
        _reiniciar_esquema(c)
        c.execute(text("GRANT USAGE ON SCHEMA public TO anon, authenticated"))
        c.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated"))
    try:
        migrar_a_head(motor)
        with motor.connect() as c:
            for tabla in TABLAS:
                for rol in ("anon", "authenticated"):
                    for permiso in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                        tiene = c.execute(
                            text("SELECT has_table_privilege(:r, :t, :p)"),
                            {"r": rol, "t": f"public.{tabla}", "p": permiso},
                        ).scalar()
                        assert tiene is False, f"{rol} tiene {permiso} sobre {tabla}"
    finally:
        with motor.begin() as c:
            c.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated"))
        motor.dispose()


def test_subir_bajar_y_volver_a_subir_las_migraciones():
    motor = crear_motor(URL_BD_PRUEBAS, Settings())
    cfg = AlembicConfig("alembic.ini")
    try:
        with motor.begin() as c:
            cfg.attributes["connection"] = c
            alembic_command.downgrade(cfg, "base")
        with motor.connect() as c:
            quedan = c.execute(
                text("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'")
            ).scalar()
        assert quedan == 0
        migrar_a_head(motor)
    finally:
        motor.dispose()


def test_las_migraciones_no_dependen_del_codigo_de_la_aplicacion():
    """Una migración debe seguir funcionando aunque el código cambie."""
    import pathlib

    for archivo in pathlib.Path("migrations/versions").glob("*.py"):
        assert "from app" not in archivo.read_text(encoding="utf-8"), archivo.name
        assert "import app" not in archivo.read_text(encoding="utf-8"), archivo.name


def test_no_se_usan_prepared_statements_en_el_servidor():
    """El pooler de Supabase en modo transacción no las soporta."""
    motor = crear_motor(URL_BD_PRUEBAS, Settings())
    try:
        with motor.connect() as c:
            for _ in range(15):  # más que el umbral por defecto de psycopg (5)
                c.execute(text("SELECT 1"))
            preparadas = c.execute(text("SELECT count(*) FROM pg_prepared_statements")).scalar()
        assert preparadas == 0
    finally:
        motor.dispose()


def test_el_tipo_de_preferencias_es_jsonb_en_postgres(motor_bd):
    with motor_bd.connect() as c:
        tipo = c.execute(
            text("SELECT data_type FROM information_schema.columns WHERE table_name='users' AND column_name='preferences'")
        ).scalar()
    assert tipo == "jsonb"


def test_las_fechas_son_timestamptz(motor_bd):
    with motor_bd.connect() as c:
        tipo = c.execute(
            text("SELECT data_type FROM information_schema.columns WHERE table_name='refresh_tokens' AND column_name='expires_at'")
        ).scalar()
    assert tipo == "timestamp with time zone"
