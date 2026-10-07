"""
Respuesta del escaneo de boletas (Etapa 4).

Es una LISTA BLANCA: de lo que responde el escáner solo pasa lo que está
declarado aquí. Un campo nuevo (o interno, de depuración) que algún día
agregue el escáner no llega al navegador por accidente.

Criterio: el texto sale de un OCR y puede venir sucio. Por eso, en vez de
rechazar toda la lectura por un campo raro, cada valor se SANEA:

* textos: sin caracteres de control, sin espacios sobrantes y con largo
  máximo (si queda vacío, pasa a `None`);
* números: si no son un número finito dentro del rango (NaN, infinito,
  negativos, absurdos, booleanos), pasan a `None`;
* fecha: solo si es una fecha ISO real entre 2000 y 2100; si no, `None`.

Lo que sí se rechaza (el servicio responde 502 al usuario) es lo que indica
que el contrato con el escáner cambió: un `estado` desconocido, un campo con
el tipo equivocado o listas absurdamente largas.

Todo lo que se muestra es una LECTURA para que la persona la revise: nada de
esto se guarda como gasto sin su confirmación.
"""
from __future__ import annotations

import datetime as dt
import math
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from app.schemas.comunes import MAX_MONTO

EstadoEscaneo = Literal[
    "SUCCESS",
    "PARTIAL_SUCCESS",
    "LOW_CONFIDENCE",
    "IMAGE_UNREADABLE",
    "INCOMPLETE_RECEIPT",
    "UNSUPPORTED_FILE",
    "NO_RECEIPT_DETECTED",
]


def _texto(maximo: int):
    def limpiar(valor: Any) -> Any:
        if valor is None:
            return None
        if not isinstance(valor, str):
            raise ValueError("debe ser texto")
        limpio = "".join(c for c in valor if c == " " or c.isprintable()).strip()
        return limpio[:maximo] or None

    return Annotated[str | None, BeforeValidator(limpiar)]


def _numero(minimo: float, maximo: float):
    def limpiar(valor: Any) -> Any:
        if valor is None or isinstance(valor, bool):
            return None
        if not isinstance(valor, (int, float)):
            raise ValueError("debe ser un número")
        numero = float(valor)
        if not math.isfinite(numero) or numero < minimo or numero > maximo:
            return None
        return numero

    return Annotated[float | None, BeforeValidator(limpiar)]


def _fecha_iso(valor: Any) -> Any:
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise ValueError("debe ser texto")
    try:
        fecha = dt.date.fromisoformat(valor.strip())
    except ValueError:
        return None
    return fecha.isoformat() if 2000 <= fecha.year <= 2100 else None


Confianza = _numero(0, 100)
Monto = _numero(0, MAX_MONTO)
Cantidad = _numero(0, 1_000_000)
FechaIso = Annotated[str | None, BeforeValidator(_fecha_iso)]


class ProductoEscaneado(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nombre: _texto(300) = None
    cantidad: Cantidad = None
    precio_unitario: Monto = None
    confianza: Confianza = None


class DatosEscaneados(BaseModel):
    model_config = ConfigDict(extra="ignore")

    comercio: _texto(300) = None
    fecha: FechaIso = None
    metodo_pago: _texto(100) = None
    productos: list[ProductoEscaneado] = Field(default_factory=list, max_length=200)
    total: Monto = None


class ConfianzaPorCampo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    comercio: Confianza = None
    fecha: Confianza = None
    metodo_pago: Confianza = None
    productos: Confianza = None
    total: Confianza = None


class EscaneoOut(BaseModel):
    """Lo que `POST /boletas/scan` entrega al navegador."""

    model_config = ConfigDict(extra="ignore")

    estado: EstadoEscaneo
    mensaje: _texto(1000)
    confianza_general: Confianza = None
    confianza_por_campo: ConfianzaPorCampo | None = None
    advertencias: list[_texto(500)] = Field(default_factory=list, max_length=50)
    datos: DatosEscaneados | None = None

    @field_validator("advertencias")
    @classmethod
    def _sin_advertencias_vacias(cls, valor: list[str | None]) -> list[str]:
        return [a for a in valor if a]
