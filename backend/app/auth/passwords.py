"""
Contraseñas: política, hash con bcrypt y verificación.

Reglas de seguridad que se aplican aquí (y por qué):

* Se guarda SOLO el hash bcrypt, nunca la contraseña.
* bcrypt solo lee los primeros 72 BYTES. En vez de truncar en silencio
  (lo que haría que dos contraseñas distintas fueran "iguales"), se
  rechazan las más largas con un mensaje claro.
* Se normaliza el texto Unicode (NFKC) antes de hashear. Sin esto, una
  contraseña con "ñ" o tilde escrita en un teléfono o en otro sistema
  operativo puede codificarse distinto y NO coincidir con la que se
  registró (usuarios chilenos afectados). La normalización lo evita.
* Al iniciar sesión con un correo que NO existe se hace igual un cálculo
  bcrypt "señuelo", para que la respuesta tarde lo mismo que con un
  correo que sí existe. Así nadie puede descubrir qué correos están
  registrados midiendo tiempos.
"""
from __future__ import annotations

import unicodedata
from functools import lru_cache

import bcrypt

MAX_BYTES_BCRYPT = 72

# Lista mínima de contraseñas trivialmente adivinables. No reemplaza una
# lista grande (p. ej. Have I Been Pwned): es una barrera básica.
CONTRASENAS_COMUNES = frozenset(
    {
        "12345678", "123456789", "1234567890", "password", "password1", "password123",
        "qwertyui", "qwerty123", "qwertyuiop", "abc12345", "abcd1234", "iloveyou",
        "11111111", "00000000", "12341234", "contrasena", "contraseña", "contrasena1",
        "contraseña1", "contraseña123", "admin123", "administrador", "bienvenido",
        "chile1234", "santiago", "blynn123", "blynn1234", "11223344", "87654321",
        "123123123", "letmein123", "welcome123", "asdfghjk", "asdf1234", "q1w2e3r4",
    }
)


class ContrasenaInvalidaError(ValueError):
    """La contraseña no cumple la política. El mensaje es apto para mostrar."""


def normalizar(password: str) -> str:
    return unicodedata.normalize("NFKC", password)


def validar_politica(password: str, *, largo_minimo: int, email: str | None = None) -> None:
    p = normalizar(password)
    if "\x00" in p:
        raise ContrasenaInvalidaError("La contraseña contiene caracteres no permitidos.")
    if len(p) < largo_minimo:
        raise ContrasenaInvalidaError(
            f"La contraseña debe tener al menos {largo_minimo} caracteres."
        )
    if len(p.encode("utf-8")) > MAX_BYTES_BCRYPT:
        raise ContrasenaInvalidaError(
            "La contraseña es demasiado larga (máximo 72 bytes; las letras con tilde "
            "o la ñ ocupan más de un byte)."
        )
    if len(set(p)) == 1:
        raise ContrasenaInvalidaError("La contraseña no puede ser un solo carácter repetido.")
    if p.lower() in CONTRASENAS_COMUNES:
        raise ContrasenaInvalidaError("Esa contraseña es demasiado común. Elige otra.")
    if email and p.lower() in {email.lower(), email.lower().split("@")[0]}:
        raise ContrasenaInvalidaError("La contraseña no puede ser igual a tu correo.")


def hash_password(password: str, *, rounds: int) -> str:
    datos = normalizar(password).encode("utf-8")
    if len(datos) > MAX_BYTES_BCRYPT:
        raise ContrasenaInvalidaError("La contraseña es demasiado larga.")
    return bcrypt.hashpw(datos, bcrypt.gensalt(rounds=rounds)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """True solo si la contraseña coincide. Nunca lanza excepción."""
    datos = normalizar(password).encode("utf-8")
    if len(datos) > MAX_BYTES_BCRYPT:
        return False  # jamás pudo haberse registrado una contraseña así
    try:
        return bcrypt.checkpw(datos, password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False  # hash corrupto o mal formado


@lru_cache
def _hash_senuelo(rounds: int) -> str:
    return hash_password("contrasena-senuelo-que-nadie-usa", rounds=rounds)


def gastar_tiempo_de_verificacion(password: str, *, rounds: int) -> None:
    """Cálculo bcrypt descartable, con el mismo costo que uno real."""
    verify_password(password, _hash_senuelo(rounds))
