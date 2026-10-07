"""
Errores de negocio. La capa de servicios los lanza sin saber de HTTP; un
manejador único en `app/main.py` los convierte en la respuesta correcta.
"""
from __future__ import annotations


class ErrorDeNegocio(Exception):
    status_code = 400
    mensaje = "Solicitud inválida."
    # Cabeceras que acompañan la respuesta de error (p. ej. Retry-After).
    headers: dict[str, str] | None = None

    def __init__(self, mensaje: str | None = None) -> None:
        super().__init__(mensaje or self.mensaje)
        self.mensaje = mensaje or self.mensaje


class NoEncontrado(ErrorDeNegocio):
    """El recurso no existe O pertenece a otro usuario. Se responde igual
    en ambos casos (404) para no revelar qué ids existen."""

    status_code = 404
    mensaje = "No encontrado."


class Conflicto(ErrorDeNegocio):
    status_code = 409


class DatoInvalido(ErrorDeNegocio):
    status_code = 422
