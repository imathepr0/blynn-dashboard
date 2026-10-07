"""
Límite de intentos COMPARTIDO (defensa contra fuerza bruta), guardado en la base de datos.

Los contadores no viven en la memoria del proceso: un servidor con varias instancias
(Vercel, Cloud Run) cuenta todo junto, y un reinicio no los borra.

Cosas a saber:
* Cada llamada que escribe (`registrar`, `reiniciar`) hace `commit` de la sesión que recibe:
  un fallo de login debe quedar registrado aunque la petición termine en error (y deshaga
  su transacción). Por eso se llama ANTES de escribir datos de negocio.
* La clave (correo + IP) se guarda como huella SHA-256, no en claro.
* Revisar y registrar son dos pasos: dos peticiones simultáneas pueden pasar el mismo
  control a la vez, así que el tope puede excederse por unas pocas peticiones. Es
  aceptable para frenar adivinanzas de contraseñas.
* Un ataque distribuido serio se frena en el borde (firewall del hosting), no aquí.
"""
from __future__ import annotations

import hashlib
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import IntentoLimitado


class LimitadorDeIntentos:
    """Ventana deslizante: máximo `maximo` eventos cada `ventana_segundos`, por clave."""

    def __init__(
        self,
        nombre: str,
        maximo: int,
        ventana_segundos: float,
        *,
        reloj: Callable[[], float] = time.time,
    ) -> None:
        self.nombre = nombre  # distingue un límite de otro dentro de la misma tabla
        self.maximo = maximo
        self.ventana = ventana_segundos
        self._reloj = reloj

    def _huella(self, clave: str) -> str:
        return hashlib.sha256(f"{self.nombre}|{clave}".encode()).hexdigest()

    def segundos_de_espera(self, db: Session, clave: str) -> int:
        """0 si puede intentar; si no, segundos hasta poder reintentar."""
        ahora = self._reloj()
        cantidad, mas_antiguo = db.execute(
            select(func.count(), func.min(IntentoLimitado.ts)).where(
                IntentoLimitado.nombre == self.nombre,
                IntentoLimitado.clave == self._huella(clave),
                IntentoLimitado.ts > ahora - self.ventana,
            )
        ).one()
        if cantidad < self.maximo:
            return 0
        return max(1, int(self.ventana - (ahora - mas_antiguo)) + 1)

    def registrar(self, db: Session, clave: str) -> None:
        ahora = self._reloj()
        corte = ahora - self.ventana
        huella = self._huella(clave)
        db.add(IntentoLimitado(nombre=self.nombre, clave=huella, ts=ahora))
        # Limpieza: lo vencido de esta clave, y de vez en cuando lo vencido de todo el límite.
        db.execute(
            delete(IntentoLimitado).where(
                IntentoLimitado.nombre == self.nombre,
                IntentoLimitado.clave == huella,
                IntentoLimitado.ts <= corte,
            )
        )
        if random.random() < 0.02:
            db.execute(
                delete(IntentoLimitado).where(IntentoLimitado.nombre == self.nombre, IntentoLimitado.ts <= corte)
            )
        db.commit()

    def reiniciar(self, db: Session, clave: str) -> None:
        db.execute(
            delete(IntentoLimitado).where(
                IntentoLimitado.nombre == self.nombre, IntentoLimitado.clave == self._huella(clave)
            )
        )
        db.commit()


@dataclass
class LimitadoresAuth:
    fallos_por_cuenta: LimitadorDeIntentos  # clave: correo + IP
    fallos_por_ip: LimitadorDeIntentos
    registros_por_ip: LimitadorDeIntentos

    @classmethod
    def desde(cls, settings: Settings) -> LimitadoresAuth:
        ventana = settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
        return cls(
            fallos_por_cuenta=LimitadorDeIntentos("fallos_cuenta", settings.AUTH_MAX_FALLOS_POR_CUENTA, ventana),
            fallos_por_ip=LimitadorDeIntentos("fallos_ip", settings.AUTH_MAX_FALLOS_POR_IP, ventana),
            registros_por_ip=LimitadorDeIntentos("registros_ip", settings.AUTH_MAX_REGISTROS_POR_IP, ventana),
        )


_limitadores: LimitadoresAuth | None = None
_lock_global = threading.Lock()


def obtener_limitadores(settings: Settings) -> LimitadoresAuth:
    global _limitadores
    with _lock_global:
        if _limitadores is None:
            _limitadores = LimitadoresAuth.desde(settings)
        return _limitadores


def reiniciar_limitadores() -> None:
    """Solo para pruebas: borra todos los contadores."""
    global _limitadores
    with _lock_global:
        _limitadores = None


def ip_cliente(request: Request, settings: Settings | None = None) -> str:
    """IP del cliente.

    Por defecto es la que ve el servidor, que detrás de un proxy es la IP del PROXY (todos
    los usuarios compartirían el mismo contador por IP). Dos formas de arreglarlo:
    * uvicorn con `--proxy-headers --forwarded-allow-ips=...` (Cloud Run, Docker), o
    * `TRUSTED_CLIENT_IP_HEADER`: el nombre de una cabecera que el hosting SOBRESCRIBE con la
      IP real (en Vercel: ver README). Solo se debe configurar si el hosting garantiza eso;
      si no, cualquiera podría falsificarla. Una cabecera ausente cae a la IP del servidor.
    NUNCA se lee X-Forwarded-For "porque sí".
    """
    nombre = settings.TRUSTED_CLIENT_IP_HEADER if settings else None
    if nombre:
        valor = request.headers.get(nombre, "").split(",")[0].strip()
        if valor:
            return valor[:64]
    return request.client.host if request.client else "desconocida"


def exigir_disponible(db: Session, limitador: LimitadorDeIntentos, clave: str) -> None:
    """Lanza 429 si la clave ya agotó sus intentos."""
    espera = limitador.segundos_de_espera(db, clave)
    if espera:
        minutos = max(1, round(espera / 60))
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos. Intenta nuevamente en {minutos} min.",
            headers={"Retry-After": str(espera)},
        )
