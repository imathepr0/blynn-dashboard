"""Pruebas de tokens JWT de acceso y de refresh tokens, incluyendo los
ataques clásicos (firma alterada, algoritmo 'none', tipo equivocado)."""
import base64
import json
import uuid
from datetime import timedelta

import jwt
import pytest

from app.auth.tokens import (
    TokenInvalidoError,
    crear_access_token,
    decodificar_access_token,
    generar_refresh_token,
    huella_refresh_token,
)
from app.config import ConfiguracionInvalidaError, Settings, validar_configuracion
from app.db.base import ahora_utc

CLAVE = "clave-solo-para-pruebas-" + "x" * 40


@pytest.fixture
def cfg() -> Settings:
    return Settings(JWT_SECRET_KEY=CLAVE)


def _b64(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


def _payload(**cambios) -> dict:
    ahora = int(ahora_utc().timestamp())
    base = {
        "sub": str(uuid.uuid4()),
        "iss": "blynn-api",
        "iat": ahora,
        "exp": ahora + 600,
        "jti": uuid.uuid4().hex,
        "typ": "access",
    }
    base.update(cambios)
    return {k: v for k, v in base.items() if v is not None}


def test_ida_y_vuelta(cfg):
    uid = uuid.uuid4()
    token, vida = crear_access_token(uid, cfg)
    assert vida == 15 * 60
    assert decodificar_access_token(token, cfg) == uid


def test_token_vencido_se_rechaza(cfg):
    token, _ = crear_access_token(uuid.uuid4(), cfg, ahora=ahora_utc() - timedelta(minutes=16))
    with pytest.raises(TokenInvalidoError):
        decodificar_access_token(token, cfg)


def test_token_con_firma_alterada_se_rechaza(cfg):
    token, _ = crear_access_token(uuid.uuid4(), cfg)
    cabecera, cuerpo, firma = token.split(".")
    alterado = f"{cabecera}.{cuerpo}.{firma[:-2]}AA"
    with pytest.raises(TokenInvalidoError):
        decodificar_access_token(alterado, cfg)


def test_token_con_cuerpo_alterado_se_rechaza(cfg):
    """Cambiar el 'sub' sin re-firmar (suplantar a otro usuario)."""
    token, _ = crear_access_token(uuid.uuid4(), cfg)
    cabecera, _cuerpo, firma = token.split(".")
    falso = _b64(_payload())
    with pytest.raises(TokenInvalidoError):
        decodificar_access_token(f"{cabecera}.{falso}.{firma}", cfg)


def test_token_firmado_con_otra_clave_se_rechaza(cfg):
    otro = jwt.encode(_payload(), "otra-clave-distinta-" + "y" * 40, algorithm="HS256")
    with pytest.raises(TokenInvalidoError):
        decodificar_access_token(otro, cfg)


def test_algoritmo_none_se_rechaza(cfg):
    sin_firma = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(_payload())}."
    with pytest.raises(TokenInvalidoError):
        decodificar_access_token(sin_firma, cfg)


def test_otro_algoritmo_aunque_la_firma_sea_valida_se_rechaza(cfg):
    """El servidor fija HS256; un token HS512 con la clave correcta no pasa."""
    token = jwt.encode(_payload(), CLAVE, algorithm="HS512")
    with pytest.raises(TokenInvalidoError):
        decodificar_access_token(token, cfg)


def test_emisor_incorrecto_se_rechaza(cfg):
    token = jwt.encode(_payload(iss="otro-servicio"), CLAVE, algorithm="HS256")
    with pytest.raises(TokenInvalidoError):
        decodificar_access_token(token, cfg)


def test_tipo_distinto_de_access_se_rechaza(cfg):
    token = jwt.encode(_payload(typ="refresh"), CLAVE, algorithm="HS256")
    with pytest.raises(TokenInvalidoError):
        decodificar_access_token(token, cfg)


@pytest.mark.parametrize("faltante", ["exp", "iat", "sub", "iss", "jti"])
def test_claims_obligatorias(cfg, faltante):
    token = jwt.encode(_payload(**{faltante: None}), CLAVE, algorithm="HS256")
    with pytest.raises(TokenInvalidoError):
        decodificar_access_token(token, cfg)


def test_sub_que_no_es_uuid_se_rechaza(cfg):
    token = jwt.encode(_payload(sub="no-soy-un-uuid"), CLAVE, algorithm="HS256")
    with pytest.raises(TokenInvalidoError):
        decodificar_access_token(token, cfg)


@pytest.mark.parametrize("basura", ["", "abc", "a.b.c", "....", "Bearer x.y.z"])
def test_texto_basura_se_rechaza(cfg, basura):
    with pytest.raises(TokenInvalidoError):
        decodificar_access_token(basura, cfg)


def test_cada_token_lleva_un_jti_distinto(cfg):
    uid = uuid.uuid4()
    a, _ = crear_access_token(uid, cfg)
    b, _ = crear_access_token(uid, cfg)
    assert jwt.decode(a, options={"verify_signature": False})["jti"] != jwt.decode(
        b, options={"verify_signature": False}
    )["jti"]


def test_refresh_tokens_son_aleatorios_y_largos():
    tokens = {generar_refresh_token() for _ in range(200)}
    assert len(tokens) == 200
    assert all(len(t) >= 60 for t in tokens)


def test_huella_es_sha256_deterministica_y_no_revela_el_token():
    t = generar_refresh_token()
    h = huella_refresh_token(t)
    assert h == huella_refresh_token(t)
    assert len(h) == 64 and t not in h
    assert h != huella_refresh_token(generar_refresh_token())


# --- Validación de configuración al arrancar ---------------------------
def test_arranque_falla_sin_clave_jwt():
    with pytest.raises(ConfiguracionInvalidaError, match="JWT_SECRET_KEY"):
        validar_configuracion(Settings(JWT_SECRET_KEY=None))


def test_arranque_falla_con_clave_corta():
    with pytest.raises(ConfiguracionInvalidaError, match="32"):
        validar_configuracion(Settings(JWT_SECRET_KEY="corta"))


def test_arranque_ok_con_clave_valida_en_desarrollo():
    validar_configuracion(Settings(JWT_SECRET_KEY=CLAVE))


def test_produccion_exige_base_de_datos_y_cors_sin_comodin():
    with pytest.raises(ConfiguracionInvalidaError) as e:
        validar_configuracion(
            Settings(JWT_SECRET_KEY=CLAVE, ENVIRONMENT="production", CORS_ORIGINS=["*"])
        )
    assert "DATABASE_URL" in str(e.value) and "CORS_ORIGINS" in str(e.value)


def test_produccion_ok_con_todo_bien():
    validar_configuracion(
        Settings(
            JWT_SECRET_KEY=CLAVE,
            ENVIRONMENT="production",
            DATABASE_URL="postgresql://u:p@host/db",
            CORS_ORIGINS=["https://blynn.cl"],
        )
    )
