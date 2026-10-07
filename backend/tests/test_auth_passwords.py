"""Pruebas de contraseñas: política, hash bcrypt y verificación."""
import unicodedata

import pytest

from app.auth.passwords import (
    ContrasenaInvalidaError,
    gastar_tiempo_de_verificacion,
    hash_password,
    validar_politica,
    verify_password,
)

R = 4  # costo mínimo de bcrypt: solo para que las pruebas sean rápidas


def test_hash_y_verificacion_correcta():
    h = hash_password("MiClaveSegura1", rounds=R)
    assert h.startswith("$2b$")
    assert h != "MiClaveSegura1"
    assert verify_password("MiClaveSegura1", h) is True


def test_contrasena_incorrecta_no_verifica():
    h = hash_password("MiClaveSegura1", rounds=R)
    assert verify_password("miclavesegura1", h) is False
    assert verify_password("", h) is False


def test_dos_hashes_de_la_misma_contrasena_son_distintos():
    """Cada hash lleva su propia sal aleatoria."""
    assert hash_password("MiClaveSegura1", rounds=R) != hash_password("MiClaveSegura1", rounds=R)


def test_espacios_al_borde_forman_parte_de_la_contrasena():
    h = hash_password(" clave con espacios ", rounds=R)
    assert verify_password(" clave con espacios ", h) is True
    assert verify_password("clave con espacios", h) is False


def test_unicode_compuesto_y_descompuesto_es_la_misma_contrasena():
    """'ñ' puede codificarse como 1 carácter (NFC) o como 'n' + tilde
    (NFD), según el teclado/sistema. Deben ser equivalentes."""
    nfc = unicodedata.normalize("NFC", "contraseñaÁrbol9")
    nfd = unicodedata.normalize("NFD", "contraseñaÁrbol9")
    assert nfc != nfd  # son secuencias distintas...
    h = hash_password(nfc, rounds=R)
    assert verify_password(nfd, h) is True  # ...pero equivalentes


def test_hash_corrupto_devuelve_false_sin_lanzar_excepcion():
    assert verify_password("cualquiera123", "esto-no-es-un-hash") is False
    assert verify_password("cualquiera123", "") is False


def test_contrasena_de_mas_de_72_bytes_se_rechaza_no_se_trunca():
    larga = "a1" * 37  # 74 bytes
    with pytest.raises(ContrasenaInvalidaError):
        validar_politica(larga, largo_minimo=8)
    with pytest.raises(ContrasenaInvalidaError):
        hash_password(larga, rounds=R)
    # Y nunca "coincide" con una contraseña que comparta los primeros 72 bytes.
    h = hash_password(larga[:72], rounds=R)
    assert verify_password(larga, h) is False


def test_el_limite_de_72_bytes_cuenta_bytes_no_caracteres():
    demasiado = "ñá" * 18 + "ñ"  # 37 caracteres pero 74 bytes en UTF-8
    with pytest.raises(ContrasenaInvalidaError):
        validar_politica(demasiado, largo_minimo=8)
    validar_politica("ñá" * 18, largo_minimo=8)  # 36 caracteres = 72 bytes: permitido


@pytest.mark.parametrize(
    "clave",
    ["corta1", "1234567", ""],
)
def test_rechaza_contrasenas_cortas(clave):
    with pytest.raises(ContrasenaInvalidaError, match="al menos 8"):
        validar_politica(clave, largo_minimo=8)


def test_el_largo_minimo_cuenta_caracteres():
    validar_politica("ñandú123", largo_minimo=8)  # 8 caracteres


@pytest.mark.parametrize("clave", ["password", "12345678", "Contraseña123", "QWERTYUI"])
def test_rechaza_contrasenas_comunes(clave):
    with pytest.raises(ContrasenaInvalidaError):
        validar_politica(clave, largo_minimo=8)


def test_rechaza_un_solo_caracter_repetido():
    with pytest.raises(ContrasenaInvalidaError):
        validar_politica("aaaaaaaaaa", largo_minimo=8)
    with pytest.raises(ContrasenaInvalidaError):
        validar_politica("          ", largo_minimo=8)


def test_rechaza_contrasena_igual_al_correo():
    with pytest.raises(ContrasenaInvalidaError, match="correo"):
        validar_politica("camilo@correo.cl", largo_minimo=8, email="camilo@correo.cl")
    with pytest.raises(ContrasenaInvalidaError, match="correo"):
        validar_politica("camilo2026", largo_minimo=8, email="camilo2026@correo.cl")


def test_rechaza_byte_nulo():
    with pytest.raises(ContrasenaInvalidaError):
        validar_politica("clave\x00segura99", largo_minimo=8)


def test_acepta_contrasena_razonable():
    validar_politica("Tr3s-Tristes-Tigres", largo_minimo=8, email="a@b.cl")


def test_el_calculo_senuelo_hace_una_verificacion_bcrypt_real(monkeypatch):
    llamadas = []
    import app.auth.passwords as modulo

    original = modulo.bcrypt.checkpw
    monkeypatch.setattr(
        modulo.bcrypt, "checkpw", lambda a, b: llamadas.append(1) or original(a, b)
    )
    gastar_tiempo_de_verificacion("lo-que-sea-123", rounds=R)
    assert len(llamadas) == 1
