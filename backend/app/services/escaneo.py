"""
Escaneo de boletas (Etapa 4): lógica de negocio, sin HTTP de entrada.

Este backend NO hace OCR. El OCR vive en `boletas-backend` (proyecto aparte,
100 % local, sin IA, que nunca guarda la imagen). Aquí solo se hace lo que el
escáner no puede hacer por sí mismo:

* comprobar que quien pide es un usuario con sesión (lo hace el router);
* validar la imagen ANTES de gastar CPU del escáner (tipo real y tamaño);
* limitar cuánto puede escanear cada usuario (cada foto cuesta hasta 30 s);
* reenviar la imagen y traducir los fallos del escáner a errores claros.

La imagen no se guarda en ningún lado: ni en la base de datos ni en los logs
(ni su contenido ni el nombre de archivo que mandó el cliente). Se mantiene en
memoria mientras dura la petición; solo hay una salvedad técnica: Starlette
vuelca a un archivo temporal las subidas de más de 1 MiB y lo borra al cerrar
el formulario (el router lo cierra siempre, en un `finally`).

El cupo por usuario y "un escaneo a la vez" viven en la base de datos (tablas
`intentos_limitados` y `escaneos_en_curso`), no en la memoria del proceso: valen aunque el
servidor corra en varias instancias (Vercel, Cloud Run).
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

import httpx
from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.rate_limit import LimitadorDeIntentos
from app.config import Settings
from app.db.models import EscaneoActivo
from app.schemas.boletas import EscaneoOut
from app.services.errores import ErrorDeNegocio

logger = logging.getLogger(__name__)

# Ruta del escáner (la misma que muestra su /docs). La dirección base viene
# de OCR_SERVICE_URL.
RUTA_ESCANER = "/api/v1/boletas/scan"
CABECERA_CLAVE = "X-Service-Key"
FUENTES = ("camera", "file")

# Pausa antes de reintentar cuando el escáner parece estar despertando.
# (Es una constante de módulo para que las pruebas la pongan en 0.)
_PAUSA_REINTENTO = 5.0


# --------------------------------------------------------------------- #
# Errores (los traduce a HTTP el manejador de `app/main.py`)
# --------------------------------------------------------------------- #
class ImagenInvalida(ErrorDeNegocio):
    status_code = 422
    mensaje = "No se pudo leer la imagen de la boleta."


class ImagenNoSoportada(ErrorDeNegocio):
    status_code = 415
    mensaje = "Formato de imagen no soportado. Usa una foto JPG, PNG o WEBP."


class ImagenMuyGrande(ErrorDeNegocio):
    status_code = 413
    mensaje = "La imagen es demasiado grande."


class DemasiadosEscaneos(ErrorDeNegocio):
    status_code = 429

    def __init__(self, espera_segundos: int) -> None:
        minutos = max(1, round(espera_segundos / 60))
        super().__init__(
            f"Escaneaste muchas boletas seguidas. Intenta nuevamente en {minutos} min "
            "o ingresa el gasto a mano."
        )
        self.headers = {"Retry-After": str(espera_segundos)}


class EscaneoEnCurso(ErrorDeNegocio):
    status_code = 429
    mensaje = "Ya hay un escaneo en curso. Espera a que termine."

    def __init__(self) -> None:
        super().__init__()
        self.headers = {"Retry-After": "10"}


class EscaneoNoDisponible(ErrorDeNegocio):
    status_code = 503
    mensaje = "El escaneo de boletas no está disponible por ahora. Ingresa el gasto a mano."


class EscaneoTardo(ErrorDeNegocio):
    status_code = 504
    mensaje = "El escaneo tardó demasiado. Intenta nuevamente."


class EscaneoFallido(ErrorDeNegocio):
    status_code = 502
    mensaje = "No se pudo leer la boleta por un problema del servicio de escaneo. Intenta nuevamente."


# --------------------------------------------------------------------- #
# Validación de la imagen
# --------------------------------------------------------------------- #
def detectar_tipo_imagen(datos: bytes) -> tuple[str, str] | None:
    """(tipo MIME, extensión) según los PRIMEROS BYTES, no según lo que
    declare el cliente: el nombre y el Content-Type los controla quien
    sube el archivo, los bytes iniciales no se pueden falsear sin dejar de
    ser esa imagen. None si no es JPEG, PNG ni WEBP."""
    if datos.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def validar_imagen(datos: bytes, *, maximo: int) -> tuple[str, str]:
    """Devuelve (tipo MIME, extensión) o lanza el error que corresponda."""
    if not datos:
        raise ImagenInvalida("La imagen está vacía.")
    if len(datos) > maximo:
        mb = maximo // (1024 * 1024)
        raise ImagenMuyGrande(f"La imagen supera el máximo de {mb} MB.")
    tipo = detectar_tipo_imagen(datos)
    if tipo is None:
        raise ImagenNoSoportada()
    return tipo


# --------------------------------------------------------------------- #
# Límites por usuario (en la base de datos, compartidos entre instancias)
# --------------------------------------------------------------------- #
# Un turno "en curso" que nadie liberó (el proceso murió) vence solo, pasado este margen
# sobre el tiempo máximo de un escaneo.
_MARGEN_TURNO_SEGUNDOS = 30


def _limitador(settings: Settings) -> LimitadorDeIntentos:
    return LimitadorDeIntentos(
        "escaneos", settings.OCR_MAX_ESCANEOS_POR_USUARIO, settings.OCR_RATE_LIMIT_WINDOW_SECONDS
    )


def exigir_escaneo_configurado(settings: Settings) -> None:
    if not (settings.OCR_SERVICE_URL or "").strip():
        raise EscaneoNoDisponible()


def reservar_escaneo(db: Session, settings: Settings, user_id: uuid.UUID) -> None:
    """Deja pasar al usuario o lanza 429. Si pasa, queda con el turno "en curso" y se cuenta
    contra su cupo (todo se confirma con un `commit`); hay que llamar a `liberar_escaneo`
    SIEMPRE al terminar (el router lo hace en un `finally`)."""
    ahora = time.time()
    # Un turno abandonado (proceso caído) no bloquea al usuario para siempre.
    db.execute(
        delete(EscaneoActivo).where(
            EscaneoActivo.user_id == user_id,
            EscaneoActivo.iniciado_ts < ahora - settings.OCR_SERVICE_TIMEOUT_SECONDS - _MARGEN_TURNO_SEGUNDOS,
        )
    )
    # Tomar el turno es un INSERT sobre la clave primaria (el usuario): si ya hay uno, falla,
    # y eso es atómico aunque las dos peticiones lleguen a instancias distintas.
    db.add(EscaneoActivo(user_id=user_id, iniciado_ts=ahora))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise EscaneoEnCurso() from None

    limitador = _limitador(settings)
    espera = limitador.segundos_de_espera(db, str(user_id))
    if espera:
        db.rollback()  # el turno nunca llegó a confirmarse
        raise DemasiadosEscaneos(espera)
    limitador.registrar(db, str(user_id))  # confirma el cupo y el turno


def liberar_escaneo(db: Session, user_id: uuid.UUID) -> None:
    try:
        db.execute(delete(EscaneoActivo).where(EscaneoActivo.user_id == user_id))
        db.commit()
    except Exception:  # no debe tapar el error original del escaneo
        db.rollback()
        logger.exception("No se pudo liberar el turno de escaneo (vencerá solo)")


# --------------------------------------------------------------------- #
# Reenvío al escáner
# --------------------------------------------------------------------- #
def _parece_arranque_en_frio(respuesta: httpx.Response) -> bool:
    """El plan gratuito de Render apaga el servicio por inactividad y, al
    despertarlo, su proxy puede responder 502/503/504 SIN cuerpo JSON. Un
    503 del propio escáner (Tesseract caído) sí trae JSON y no se reintenta."""
    if respuesta.status_code not in (502, 503, 504):
        return False
    return "json" not in respuesta.headers.get("content-type", "").lower()


async def reenviar_al_escaner(
    cliente: httpx.AsyncClient,
    settings: Settings,
    imagen: bytes,
    mime: str,
    extension: str,
    fuente: str,
) -> Any:
    """Envía la imagen al escáner y devuelve su JSON tal cual.

    Reintenta UNA vez (tras una pausa) si el escáner parece estar
    despertando. Todo el intento, con reintento incluido, está acotado por
    OCR_SERVICE_TIMEOUT_SECONDS.
    """
    url = settings.OCR_SERVICE_URL.strip().rstrip("/") + RUTA_ESCANER  # type: ignore[union-attr]
    cabeceras = {}
    # .strip(): al pegar un secreto desde el celular es fácil que se cuele un espacio o un
    # salto de línea, y entonces la clave "no coincide". Una clave vacía (p. ej. una línea
    # `OCR_SERVICE_KEY=` en el .env) equivale a no tener clave: no se envía la cabecera.
    clave = settings.OCR_SERVICE_KEY.get_secret_value().strip() if settings.OCR_SERVICE_KEY is not None else ""
    if clave:
        cabeceras[CABECERA_CLAVE] = clave
    # El nombre del archivo lo fijamos nosotros: nunca se reenvía el que
    # mandó el cliente.
    archivos = {"file": (f"boleta.{extension}", imagen, mime)}
    datos = {"source": fuente}

    try:
        async with asyncio.timeout(settings.OCR_SERVICE_TIMEOUT_SECONDS):
            respuesta = await _enviar_con_reintento(cliente, url, archivos, datos, cabeceras)
    except (TimeoutError, httpx.TimeoutException):
        logger.warning("El servicio de escaneo no respondió a tiempo")
        raise EscaneoTardo() from None
    except httpx.TransportError as exc:
        logger.warning("No se pudo conectar con el servicio de escaneo (%s)", type(exc).__name__)
        raise EscaneoNoDisponible() from None

    return _interpretar(respuesta)


async def _enviar_con_reintento(
    cliente: httpx.AsyncClient, url: str, archivos: dict, datos: dict, cabeceras: dict
) -> httpx.Response:
    for intento in (1, 2):
        try:
            respuesta = await cliente.post(url, files=archivos, data=datos, headers=cabeceras)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError):
            if intento == 2:
                raise
            logger.info("El servicio de escaneo no respondió; se reintenta una vez")
            await asyncio.sleep(_PAUSA_REINTENTO)
            continue
        if intento == 1 and _parece_arranque_en_frio(respuesta):
            logger.info("El servicio de escaneo parece estar despertando; se reintenta una vez")
            await asyncio.sleep(_PAUSA_REINTENTO)
            continue
        return respuesta
    raise AssertionError("inalcanzable")  # pragma: no cover


def _interpretar(respuesta: httpx.Response) -> Any:
    """Traduce la respuesta del escáner. NUNCA se copia al usuario el cuerpo
    de un error del escáner (podría traer detalles internos)."""
    codigo = respuesta.status_code
    if codigo == 200:
        try:
            cuerpo = respuesta.json()
        except ValueError:
            logger.error("El servicio de escaneo respondió 200 con un cuerpo que no es JSON")
            raise EscaneoFallido() from None
        if not isinstance(cuerpo, dict):
            logger.error("El servicio de escaneo respondió 200 con un JSON inesperado")
            raise EscaneoFallido()
        try:
            # Lista blanca: solo pasa lo declarado en EscaneoOut (ver el esquema).
            return EscaneoOut.model_validate(cuerpo).model_dump(mode="json")
        except ValidationError as exc:
            # Se registran los CAMPOS que no encajan, nunca sus valores (son
            # datos de la boleta de una persona).
            campos = sorted({".".join(str(parte) for parte in e["loc"]) for e in exc.errors()})
            logger.error("La respuesta del escáner no cumple el contrato (campos: %s)", campos)
            raise EscaneoFallido() from None
    if codigo in (429, 502, 503, 504):
        logger.warning("El servicio de escaneo respondió %s", codigo)
        raise EscaneoNoDisponible()
    # 3xx (no se siguen redirecciones), 4xx (la imagen ya fue validada aquí:
    # un 4xx indica que el contrato cambió) y 5xx: es un fallo del servicio.
    logger.error("El servicio de escaneo respondió %s", codigo)
    raise EscaneoFallido()
