"""
Pruebas de la API de autenticación (Etapa 2), de extremo a extremo con
la base de datos de pruebas: registro, login, /me, refresh con rotación,
detección de reutilización, logout, límites de intentos y los casos
negativos (tokens alterados, vencidos, de otro tipo, cuentas borradas...).
"""
import threading
import unicodedata
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.auth.tokens import crear_access_token, huella_refresh_token
from app.db.base import ahora_utc
from app.db.models import RefreshToken, User
from tests.conftest import USA_POSTGRES

CLAVE = "Tr3s-Tristes-Tigres"
API = "/api/v1/auth"


def registrar(cliente, email="ana@correo.cl", password=CLAVE, **extra):
    return cliente.post(f"{API}/register", json={"email": email, "password": password, **extra})


def login(cliente, email="ana@correo.cl", password=CLAVE):
    return cliente.post(f"{API}/login", json={"email": email, "password": password})


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===================================================================== #
# Registro
# ===================================================================== #
def test_registro_exitoso_devuelve_sesion_y_usuario(cliente, db):
    r = registrar(cliente, full_name="Ana Pérez")
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["expires_in"] == 15 * 60
    assert cuerpo["user"]["email"] == "ana@correo.cl"
    assert cuerpo["user"]["full_name"] == "Ana Pérez"
    assert cuerpo["user"]["role"] == "user"
    assert r.headers["cache-control"] == "no-store"


def test_registro_nunca_expone_la_contrasena_ni_su_hash(cliente):
    r = registrar(cliente)
    texto = r.text.lower()
    assert "password" not in texto and "$2b$" not in texto and CLAVE.lower() not in texto


def test_registro_guarda_hash_bcrypt_y_solo_la_huella_del_refresh_token(cliente, db):
    r = registrar(cliente).json()
    usuario = db.scalar(select(User))
    assert usuario.password_hash.startswith("$2b$") and CLAVE not in usuario.password_hash
    fila = db.scalar(select(RefreshToken))
    assert fila.token_hash == huella_refresh_token(r["refresh_token"])
    assert fila.token_hash != r["refresh_token"]


def test_registro_normaliza_el_correo(cliente, db):
    r = registrar(cliente, email="  Ana@Correo.CL ")
    assert r.status_code == 201
    assert r.json()["user"]["email"] == "ana@correo.cl"
    assert db.scalar(select(User)).email == "ana@correo.cl"


def test_registro_con_correo_repetido_da_409_sin_importar_mayusculas(cliente, db):
    assert registrar(cliente).status_code == 201
    r = registrar(cliente, email="ANA@correo.cl", password="Otra-Clave-Distinta9")
    assert r.status_code == 409
    assert len(db.scalars(select(User)).all()) == 1


@pytest.mark.parametrize(
    "clave, fragmento",
    [("corta1", "al menos 8"), ("password", "común"), ("ñá" * 19, "larga"), ("aaaaaaaaaa", "repetido")],
)
def test_registro_rechaza_contrasenas_debiles(cliente, db, clave, fragmento):
    r = registrar(cliente, password=clave)
    assert r.status_code == 422
    assert fragmento in r.json()["detail"]
    assert db.scalars(select(User)).all() == []  # no se creó nada


@pytest.mark.parametrize("correo", ["no-es-correo", "a@", "@b.cl", "", "ana@@correo.cl"])
def test_registro_rechaza_correos_invalidos(cliente, correo):
    assert registrar(cliente, email=correo).status_code == 422


@pytest.mark.parametrize(
    "campo",
    [{"role": "admin"}, {"is_active": False}, {"id": str(uuid.uuid4())}, {"password_hash": "x"},
     {"onboarded": True}, {"monthly_budget": 999}],
)
def test_registro_rechaza_campos_internos_mass_assignment(cliente, db, campo):
    r = registrar(cliente, **campo)
    assert r.status_code == 422
    assert db.scalars(select(User)).all() == []


def test_registro_sin_contrasena_es_422(cliente):
    assert cliente.post(f"{API}/register", json={"email": "a@b.cl"}).status_code == 422


def test_nombre_vacio_se_guarda_como_nulo(cliente):
    assert registrar(cliente, full_name="   ").json()["user"]["full_name"] is None


# ===================================================================== #
# Login
# ===================================================================== #
def test_login_correcto_y_registra_ultimo_acceso(cliente, db):
    registrar(cliente)
    r = login(cliente)
    assert r.status_code == 200 and r.json()["access_token"] and r.json()["refresh_token"]
    db.expire_all()
    assert db.scalar(select(User)).last_login_date is not None


def test_login_ignora_mayusculas_del_correo(cliente):
    registrar(cliente)
    assert login(cliente, email="ANA@CORREO.CL").status_code == 200


def test_login_con_contrasena_unicode_equivalente(cliente):
    nfc = unicodedata.normalize("NFC", "Contraseña-Ñandú9")
    nfd = unicodedata.normalize("NFD", "Contraseña-Ñandú9")
    registrar(cliente, password=nfc)
    assert login(cliente, password=nfd).status_code == 200


def test_login_fallos_son_indistinguibles(cliente, db):
    """Contraseña mala, correo inexistente y cuenta desactivada dan
    EXACTAMENTE la misma respuesta: no se puede averiguar qué correos
    existen."""
    registrar(cliente)
    registrar(cliente, email="inactivo@correo.cl")
    db.execute(update(User).where(User.email == "inactivo@correo.cl").values(is_active=False))
    db.commit()

    respuestas = [
        login(cliente, password="Clave-Equivocada-1"),
        login(cliente, email="nadie@correo.cl"),
        login(cliente, email="inactivo@correo.cl"),  # con la contraseña correcta
    ]
    assert {r.status_code for r in respuestas} == {401}
    assert len({r.text for r in respuestas}) == 1


def test_login_con_correo_inexistente_gasta_tiempo_de_bcrypt(cliente, monkeypatch):
    import app.auth.service as servicio

    llamadas = []
    original = servicio.gastar_tiempo_de_verificacion
    monkeypatch.setattr(
        servicio, "gastar_tiempo_de_verificacion", lambda *a, **k: llamadas.append(1) or original(*a, **k)
    )
    registrar(cliente)
    login(cliente, email="nadie@correo.cl")
    assert len(llamadas) == 1
    login(cliente, password="Clave-Equivocada-1")  # correo real: verifica el hash real
    assert len(llamadas) == 1


def test_login_con_intento_de_inyeccion_sql_es_solo_credenciales_invalidas(cliente):
    registrar(cliente)
    assert login(cliente, password="' OR '1'='1' --").status_code == 401
    assert login(cliente, email="ana@correo.cl'; DROP TABLE users;--").status_code == 422
    assert login(cliente).status_code == 200  # la tabla sigue ahí


# ===================================================================== #
# /me y protección con access token
# ===================================================================== #
def test_me_con_token_valido(cliente):
    token = registrar(cliente).json()["access_token"]
    r = cliente.get(f"{API}/me", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["email"] == "ana@correo.cl"
    assert "password_hash" not in r.text


def test_me_sin_token_es_401_con_cabecera_www_authenticate(cliente):
    r = cliente.get(f"{API}/me")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "cabecera",
    ["Bearer", "Bearer ", "Bearer no.es.un.jwt", "Basic abc", "abc", "Bearer " + "a" * 500],
)
def test_me_con_cabecera_mal_formada_es_401(cliente, cabecera):
    assert cliente.get(f"{API}/me", headers={"Authorization": cabecera}).status_code == 401


def test_me_con_token_vencido_es_401(cliente):
    from app.config import Settings

    token = registrar(cliente).json()["access_token"]
    usuario_id = cliente.get(f"{API}/me", headers=bearer(token)).json()["id"]
    viejo, _ = crear_access_token(
        uuid.UUID(usuario_id),
        Settings(JWT_SECRET_KEY="clave-solo-para-pruebas-" + "x" * 40),
        ahora=ahora_utc() - timedelta(hours=1),
    )
    assert cliente.get(f"{API}/me", headers=bearer(viejo)).status_code == 401


def test_me_con_token_alterado_es_401(cliente):
    token = registrar(cliente).json()["access_token"]
    cabecera, cuerpo, firma = token.split(".")
    alterado = f"{cabecera}.{cuerpo}.{'A' * len(firma)}"
    assert cliente.get(f"{API}/me", headers=bearer(alterado)).status_code == 401


def test_un_refresh_token_no_sirve_como_access_token(cliente):
    refresh = registrar(cliente).json()["refresh_token"]
    assert cliente.get(f"{API}/me", headers=bearer(refresh)).status_code == 401


def test_un_access_token_no_sirve_como_refresh_token(cliente):
    access = registrar(cliente).json()["access_token"]
    r = cliente.post(f"{API}/refresh", json={"refresh_token": access})
    assert r.status_code in (401, 422)


def test_token_de_usuario_borrado_deja_de_servir_de_inmediato(cliente, db):
    token = registrar(cliente).json()["access_token"]
    db.delete(db.scalar(select(User)))
    db.commit()
    assert cliente.get(f"{API}/me", headers=bearer(token)).status_code == 401


def test_token_de_usuario_desactivado_deja_de_servir_de_inmediato(cliente, db):
    token = registrar(cliente).json()["access_token"]
    db.execute(update(User).values(is_active=False))
    db.commit()
    assert cliente.get(f"{API}/me", headers=bearer(token)).status_code == 401


def test_cada_usuario_ve_solo_sus_propios_datos(cliente):
    a = registrar(cliente, email="ana@correo.cl").json()
    b = registrar(cliente, email="beto@correo.cl").json()
    assert cliente.get(f"{API}/me", headers=bearer(a["access_token"])).json()["email"] == "ana@correo.cl"
    assert cliente.get(f"{API}/me", headers=bearer(b["access_token"])).json()["email"] == "beto@correo.cl"


# ===================================================================== #
# Refresh: rotación y detección de reutilización
# ===================================================================== #
def test_refresh_entrega_tokens_nuevos_y_funcionales(cliente):
    s1 = registrar(cliente).json()
    r = cliente.post(f"{API}/refresh", json={"refresh_token": s1["refresh_token"]})
    assert r.status_code == 200
    s2 = r.json()
    assert s2["refresh_token"] != s1["refresh_token"]
    assert s2["access_token"] != s1["access_token"]
    assert r.headers["cache-control"] == "no-store"
    assert cliente.get(f"{API}/me", headers=bearer(s2["access_token"])).status_code == 200


def test_el_refresh_token_anterior_queda_inutilizable(cliente):
    s1 = registrar(cliente).json()
    cliente.post(f"{API}/refresh", json={"refresh_token": s1["refresh_token"]})
    assert cliente.post(f"{API}/refresh", json={"refresh_token": s1["refresh_token"]}).status_code == 401


def test_reutilizar_un_refresh_token_viejo_revoca_toda_la_sesion(cliente):
    """Si alguien roba un refresh token y lo usa después de que el dueño
    ya lo rotó (o al revés), se cierra la sesión completa."""
    s1 = registrar(cliente).json()
    s2 = cliente.post(f"{API}/refresh", json={"refresh_token": s1["refresh_token"]}).json()
    # El "ladrón" presenta el token viejo ya usado...
    assert cliente.post(f"{API}/refresh", json={"refresh_token": s1["refresh_token"]}).status_code == 401
    # ...y el token nuevo, que era legítimo, también queda revocado.
    assert cliente.post(f"{API}/refresh", json={"refresh_token": s2["refresh_token"]}).status_code == 401


def test_la_reutilizacion_no_afecta_a_otras_sesiones_del_mismo_usuario(cliente):
    dispositivo_a = registrar(cliente).json()
    dispositivo_b = login(cliente).json()  # segundo login = otra sesión (otra familia)
    nuevo_a = cliente.post(f"{API}/refresh", json={"refresh_token": dispositivo_a["refresh_token"]}).json()
    cliente.post(f"{API}/refresh", json={"refresh_token": dispositivo_a["refresh_token"]})  # reuso en A
    assert cliente.post(f"{API}/refresh", json={"refresh_token": nuevo_a["refresh_token"]}).status_code == 401
    assert cliente.post(f"{API}/refresh", json={"refresh_token": dispositivo_b["refresh_token"]}).status_code == 200


def test_refresh_token_desconocido_es_401(cliente):
    r = cliente.post(f"{API}/refresh", json={"refresh_token": "x" * 64})
    assert r.status_code == 401


def test_refresh_token_vencido_es_401(cliente, db):
    s = registrar(cliente).json()
    db.execute(update(RefreshToken).values(expires_at=ahora_utc() - timedelta(minutes=1)))
    db.commit()
    assert cliente.post(f"{API}/refresh", json={"refresh_token": s["refresh_token"]}).status_code == 401


def test_refresh_de_usuario_desactivado_revoca_y_falla(cliente, db):
    s = registrar(cliente).json()
    db.execute(update(User).values(is_active=False))
    db.commit()
    assert cliente.post(f"{API}/refresh", json={"refresh_token": s["refresh_token"]}).status_code == 401
    db.expire_all()
    assert all(f.revoked_at is not None for f in db.scalars(select(RefreshToken)))


def test_refresh_con_cuerpo_invalido_es_422(cliente):
    assert cliente.post(f"{API}/refresh", json={}).status_code == 422
    assert cliente.post(f"{API}/refresh", json={"refresh_token": "corto"}).status_code == 422
    assert cliente.post(f"{API}/refresh", json={"refresh_token": "x" * 64, "extra": 1}).status_code == 422


def test_el_login_limpia_refresh_tokens_vencidos_hace_tiempo(cliente, db):
    registrar(cliente)
    db.execute(update(RefreshToken).values(expires_at=ahora_utc() - timedelta(days=3)))
    db.commit()
    login(cliente)
    db.expire_all()
    assert len(db.scalars(select(RefreshToken)).all()) == 1  # solo queda el nuevo


# ===================================================================== #
# Logout
# ===================================================================== #
def test_logout_revoca_la_sesion(cliente):
    s = registrar(cliente).json()
    assert cliente.post(f"{API}/logout", json={"refresh_token": s["refresh_token"]}).status_code == 204
    assert cliente.post(f"{API}/refresh", json={"refresh_token": s["refresh_token"]}).status_code == 401


def test_logout_con_token_desconocido_responde_204_igual(cliente):
    """No revela si el token existía."""
    assert cliente.post(f"{API}/logout", json={"refresh_token": "z" * 64}).status_code == 204


def test_logout_solo_cierra_esa_sesion(cliente):
    a = registrar(cliente).json()
    b = login(cliente).json()
    cliente.post(f"{API}/logout", json={"refresh_token": a["refresh_token"]})
    assert cliente.post(f"{API}/refresh", json={"refresh_token": b["refresh_token"]}).status_code == 200


def test_logout_all_cierra_todas_las_sesiones_del_usuario_y_no_las_de_otros(cliente):
    a1 = registrar(cliente, email="ana@correo.cl").json()
    a2 = login(cliente, email="ana@correo.cl").json()
    b = registrar(cliente, email="beto@correo.cl").json()

    r = cliente.post(f"{API}/logout-all", headers=bearer(a1["access_token"]))
    assert r.status_code == 204
    for s in (a1, a2):
        assert cliente.post(f"{API}/refresh", json={"refresh_token": s["refresh_token"]}).status_code == 401
    assert cliente.post(f"{API}/refresh", json={"refresh_token": b["refresh_token"]}).status_code == 200


def test_logout_all_exige_autenticacion(cliente):
    assert cliente.post(f"{API}/logout-all").status_code == 401


# ===================================================================== #
# Límite de intentos
# ===================================================================== #
def test_bloqueo_tras_demasiados_fallos_de_una_cuenta(crear_cliente):
    c = crear_cliente(AUTH_RATE_LIMIT_ENABLED=True, AUTH_MAX_FALLOS_POR_CUENTA=3)
    registrar(c)
    for _ in range(3):
        assert login(c, password="Clave-Equivocada-1").status_code == 401
    r = login(c, password="Clave-Equivocada-1")
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
    # Bloqueado incluso con la contraseña CORRECTA (así funciona la protección).
    assert login(c).status_code == 429


def test_el_bloqueo_de_una_cuenta_no_afecta_a_otra(crear_cliente):
    c = crear_cliente(AUTH_RATE_LIMIT_ENABLED=True, AUTH_MAX_FALLOS_POR_CUENTA=2)
    registrar(c, email="ana@correo.cl")
    registrar(c, email="beto@correo.cl")
    for _ in range(2):
        login(c, email="ana@correo.cl", password="Clave-Equivocada-1")
    assert login(c, email="ana@correo.cl").status_code == 429
    assert login(c, email="beto@correo.cl").status_code == 200


def test_un_login_exitoso_reinicia_el_contador_de_la_cuenta(crear_cliente):
    c = crear_cliente(AUTH_RATE_LIMIT_ENABLED=True, AUTH_MAX_FALLOS_POR_CUENTA=3)
    registrar(c)
    for _ in range(2):
        login(c, password="Clave-Equivocada-1")
    assert login(c).status_code == 200
    for _ in range(2):
        assert login(c, password="Clave-Equivocada-1").status_code == 401
    assert login(c).status_code == 200


def test_bloqueo_por_ip_aunque_se_prueben_muchos_correos(crear_cliente):
    c = crear_cliente(AUTH_RATE_LIMIT_ENABLED=True, AUTH_MAX_FALLOS_POR_IP=3)
    for i in range(3):
        assert login(c, email=f"nadie{i}@correo.cl").status_code == 401
    assert login(c, email="otro@correo.cl").status_code == 429


def test_limite_de_registros_por_ip(crear_cliente):
    c = crear_cliente(AUTH_RATE_LIMIT_ENABLED=True, AUTH_MAX_REGISTROS_POR_IP=2)
    assert registrar(c, email="a1@correo.cl").status_code == 201
    assert registrar(c, email="a2@correo.cl").status_code == 201
    r = registrar(c, email="a3@correo.cl")
    assert r.status_code == 429 and "retry-after" in r.headers


def test_el_bloqueo_no_gasta_bcrypt(crear_cliente, monkeypatch):
    import app.auth.service as servicio

    c = crear_cliente(AUTH_RATE_LIMIT_ENABLED=True, AUTH_MAX_FALLOS_POR_CUENTA=1)
    registrar(c)
    login(c, password="Clave-Equivocada-1")
    llamadas = []
    monkeypatch.setattr(servicio, "autenticar", lambda *a, **k: llamadas.append(1))
    assert login(c).status_code == 429
    assert llamadas == []  # ni siquiera se intentó autenticar


# ===================================================================== #
# Arranque y salud
# ===================================================================== #
def test_el_servidor_no_arranca_con_configuracion_insegura(monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as principal
    from app.config import ConfiguracionInvalidaError, Settings

    monkeypatch.setattr(principal, "settings", Settings(JWT_SECRET_KEY=None))
    with pytest.raises(ConfiguracionInvalidaError):
        with TestClient(principal.app):
            pass


def test_el_servidor_arranca_con_configuracion_valida():
    from fastapi.testclient import TestClient

    import app.main as principal

    with TestClient(principal.app) as c:
        assert c.get("/health").status_code == 200


def test_health_ready_sin_base_de_datos_configurada_es_503(cliente, monkeypatch):
    from app.db import session

    def _sin_bd():
        raise session.BaseDeDatosNoConfiguradaError("no configurada")

    monkeypatch.setattr(session, "obtener_motor", _sin_bd)
    r = cliente.get("/health/ready")
    assert r.status_code == 503 and r.json() == {"status": "sin_base_de_datos"}


def test_health_ready_con_base_de_datos_ok(cliente, motor_bd, monkeypatch):
    from app.db import session

    monkeypatch.setattr(session, "obtener_motor", lambda: motor_bd)
    assert cliente.get("/health/ready").json() == {"status": "ok"}


def test_los_errores_internos_no_filtran_datos_en_la_respuesta(cliente, monkeypatch):
    import app.auth.service as servicio

    def _falla(*a, **k):
        raise RuntimeError("password=SECRETO hash=$2b$04$xxxx")

    monkeypatch.setattr(servicio, "autenticar", _falla)
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app, raise_server_exceptions=False)
    r = c.post(f"{API}/login", json={"email": "ana@correo.cl", "password": CLAVE})
    assert r.status_code == 500
    assert "SECRETO" not in r.text and "$2b$" not in r.text


# ===================================================================== #
# Concurrencia (solo Postgres: SQLite no tiene bloqueo de filas)
# ===================================================================== #
@pytest.mark.skipif(not USA_POSTGRES, reason="requiere Postgres real (bloqueo de filas)")
def test_usos_simultaneos_del_mismo_refresh_token_solo_uno_gana(cliente):
    s = registrar(cliente).json()
    resultados: list[int] = []
    barrera = threading.Barrier(6)

    def _usar():
        barrera.wait()
        resultados.append(
            cliente.post(f"{API}/refresh", json={"refresh_token": s["refresh_token"]}).status_code
        )

    hilos = [threading.Thread(target=_usar) for _ in range(6)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert resultados.count(200) == 1
    assert resultados.count(401) == 5


@pytest.mark.skipif(not USA_POSTGRES, reason="requiere Postgres real (restricción UNIQUE)")
def test_registros_simultaneos_con_el_mismo_correo_crean_una_sola_cuenta(cliente, db):
    resultados: list[int] = []
    barrera = threading.Barrier(6)

    def _registrar():
        barrera.wait()
        resultados.append(registrar(cliente).status_code)

    hilos = [threading.Thread(target=_registrar) for _ in range(6)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert resultados.count(201) == 1
    assert resultados.count(409) == 5
    assert len(db.scalars(select(User)).all()) == 1
