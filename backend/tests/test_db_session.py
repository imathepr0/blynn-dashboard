"""Pruebas de la conexión: normalización de la URL de Supabase y
parámetros seguros del motor. No necesitan una base de datos real."""
import pytest

from app.config import Settings
from app.db.session import BaseDeDatosNoConfiguradaError, crear_motor, normalizar_database_url


def test_postgresql_se_convierte_a_psycopg3():
    u = normalizar_database_url("postgresql://u:p@localhost:5432/db")
    assert u.drivername == "postgresql+psycopg"


def test_postgres_a_secas_tambien_se_acepta():
    """Algunos proveedores entregan 'postgres://'."""
    assert normalizar_database_url("postgres://u:p@localhost/db").drivername == "postgresql+psycopg"


def test_un_driver_explicito_se_respeta():
    assert normalizar_database_url("postgresql+psycopg://u:p@h/db").drivername == "postgresql+psycopg"


def test_supabase_fuerza_ssl():
    url = "postgresql://postgres.abcd:pw@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    assert normalizar_database_url(url).query["sslmode"] == "require"
    url2 = "postgresql://postgres:pw@db.abcd.supabase.co:5432/postgres"
    assert normalizar_database_url(url2).query["sslmode"] == "require"


def test_supabase_respeta_un_sslmode_ya_indicado():
    url = "postgresql://u:p@aws-0-x.pooler.supabase.com:5432/postgres?sslmode=verify-full"
    assert normalizar_database_url(url).query["sslmode"] == "verify-full"


def test_bases_locales_no_reciben_ssl_forzado():
    assert "sslmode" not in normalizar_database_url("postgresql://u:p@localhost/db").query


def test_el_usuario_con_punto_de_supabase_se_conserva():
    """El pooler de Supabase usa usuarios del tipo 'postgres.<ref-proyecto>'."""
    u = normalizar_database_url("postgresql://postgres.abcdefgh:pw@aws-0-sa-east-1.pooler.supabase.com:6543/postgres")
    assert u.username == "postgres.abcdefgh" and u.port == 6543


def test_contrasena_con_caracteres_especiales_codificados_se_conserva():
    u = normalizar_database_url("postgresql://u:p%40ss%23w%2Ford@h.supabase.com/db")
    assert u.password == "p@ss#w/ord"


def test_sqlite_no_se_modifica():
    assert normalizar_database_url("sqlite://").drivername == "sqlite"


def test_el_motor_oculta_los_parametros_de_las_consultas():
    """Evita que correos/hashes/huellas aparezcan en los logs de errores."""
    motor = crear_motor("postgresql://u:p@localhost/db", Settings())
    assert motor.hide_parameters is True
    assert crear_motor("sqlite://", Settings()).hide_parameters is True


def test_el_pool_toma_los_limites_de_la_configuracion():
    motor = crear_motor(
        "postgresql://u:p@localhost/db", Settings(DB_POOL_SIZE=2, DB_MAX_OVERFLOW=1)
    )
    assert motor.pool.size() == 2
    assert motor.pool._max_overflow == 1


def test_sin_database_url_falla_con_mensaje_claro(monkeypatch):
    from app.db import session

    monkeypatch.setattr(session, "get_settings", lambda: Settings(DATABASE_URL=None))
    session.obtener_motor.cache_clear()
    with pytest.raises(BaseDeDatosNoConfiguradaError, match="DATABASE_URL"):
        session.obtener_motor()
    session.obtener_motor.cache_clear()
