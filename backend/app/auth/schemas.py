"""
Esquemas de entrada y salida de la API de autenticación.

* Entradas con `extra="forbid"`: cualquier campo desconocido se rechaza
  (422). Así nadie puede colar `role: "admin"` u otro campo interno al
  registrarse ("mass assignment").
* Salidas como LISTA BLANCA explícita: `UsuarioOut` enumera los campos
  que salen; `password_hash` no está y por lo tanto no puede filtrarse
  aunque alguien agregue columnas al modelo más adelante.
* A la contraseña NO se le recortan espacios: podrían ser parte
  intencional de ella. Al correo y al nombre sí.
"""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("email", "full_name", mode="before", check_fields=False)
    @classmethod
    def _recortar_espacios(cls, v):
        return v.strip() if isinstance(v, str) else v


class RegistroIn(_Entrada):
    email: EmailStr
    # Largo máximo generoso solo para no procesar textos gigantes; la
    # política real (mínimo y máximo en bytes) se valida en el servicio.
    password: str = Field(min_length=1, max_length=200)
    full_name: str | None = Field(default=None, max_length=120)

    @field_validator("full_name")
    @classmethod
    def _nombre_vacio_es_nulo(cls, v: str | None) -> str | None:
        return v or None


class LoginIn(_Entrada):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RefreshIn(_Entrada):
    refresh_token: str = Field(min_length=20, max_length=200)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    onboarded: bool
    monthly_budget: int
    preferences: dict
    created_date: dt.datetime


class TokensOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos de vida del access token


class AuthOut(TokensOut):
    user: UsuarioOut
