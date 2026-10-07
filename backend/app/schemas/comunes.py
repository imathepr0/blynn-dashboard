"""
Tipos y clases base compartidos por los esquemas de la API de datos.

Filosofía: la API es la ÚLTIMA barrera antes de la base de datos, así que
valida todo de forma estricta y devuelve `422` con un mensaje claro en
vez de dejar que la base de datos falle con un error 500:

* Montos: enteros estrictos (nada de `true`, `"12"` ni `12.5`), con tope.
* Textos: sin espacios sobrantes, con largo máximo (el mismo de la
  columna) y sin caracteres de control ni bytes nulos (Postgres rechaza
  `\\x00`).
* Colores: solo `#rrggbb`. El frontend los mete en estilos CSS, así que
  un valor libre sería una puerta de entrada a inyección de estilos.
* Fechas: entre 2000 y 2100 (descarta datos absurdos).
* Las entradas rechazan campos desconocidos (`extra="forbid"`): no se
  puede enviar `user_id`, `id` ni `created_date`.
"""
from __future__ import annotations

import datetime as dt
from typing import Annotated, Any, ClassVar

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    model_validator,
)

MAX_MONTO = 10**12  # un billón de pesos: muy por sobre cualquier uso real
FECHA_MIN = dt.date(2000, 1, 1)
FECHA_MAX = dt.date(2100, 12, 31)


def _sin_caracteres_de_control(v: str) -> str:
    # Se permiten salto de línea, retorno y tabulación (descripciones
    # con un ítem por línea); todo otro carácter de control se rechaza.
    if any((ord(c) < 32 and c not in "\n\r\t") or ord(c) == 127 for c in v):
        raise ValueError("Contiene caracteres de control no permitidos.")
    return v


def _fecha_razonable(v: dt.date) -> dt.date:
    if not (FECHA_MIN <= v <= FECHA_MAX):
        raise ValueError("La fecha debe estar entre 2000 y 2100.")
    return v


def _vacio_a_nulo(v: Any) -> Any:
    """El frontend envía "" cuando un campo opcional está vacío."""
    if isinstance(v, str) and not v.strip():
        return None
    return v


def _texto(maximo: int):
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=maximo),
        AfterValidator(_sin_caracteres_de_control),
    ]


Texto100 = _texto(100)
Texto120 = _texto(120)
Texto255 = _texto(255)
TextoLargoOpcional = Annotated[
    _texto(5000) | None, BeforeValidator(_vacio_a_nulo)
]
Texto255Opcional = Annotated[_texto(255) | None, BeforeValidator(_vacio_a_nulo)]

Monto = Annotated[int, Field(strict=True, ge=0, le=MAX_MONTO)]
MontoPositivo = Annotated[int, Field(strict=True, gt=0, le=MAX_MONTO)]

Color = Annotated[
    str,
    StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$"),
    AfterValidator(str.lower),
]
ColorOpcional = Annotated[Color | None, BeforeValidator(_vacio_a_nulo)]
# Nombre de un icono de lucide-react ("ShoppingBag", "Car"...).
Icono = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9]{1,50}$")]

Fecha = Annotated[dt.date, AfterValidator(_fecha_razonable)]

# Booleano estricto: solo `true`/`false` (no acepta 1, "yes", "on"...).
Booleano = StrictBool


class EntradaEstricta(BaseModel):
    """Base de todo lo que llega del cliente: rechaza campos desconocidos."""

    model_config = ConfigDict(extra="forbid")


class EntradaParcial(EntradaEstricta):
    """Base de los PATCH: solo se aplican los campos enviados.

    `NO_NULOS` lista los campos cuya columna NO acepta nulo: enviarlos
    como `null` es un error 422 (no un 500 de la base de datos). Los
    demás sí pueden ponerse en `null` para borrarlos.
    """

    NO_NULOS: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _no_permitir_nulos_donde_no_corresponde(self):
        for campo in self.model_fields_set & self.NO_NULOS:
            if getattr(self, campo) is None:
                raise ValueError(f"'{campo}' no puede ser nulo.")
        return self


class Salida(BaseModel):
    """Base de las respuestas: solo salen los campos declarados."""

    model_config = ConfigDict(from_attributes=True)
