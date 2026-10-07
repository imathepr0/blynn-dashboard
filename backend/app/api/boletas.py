"""
Escaneo de boletas (Etapa 4).

    POST /api/v1/boletas/scan     multipart: file (jpg/png/webp, máx. 10 MB)
                                  y source ("camera" | "file", opcional)

Responde con la lectura del escáner filtrada por una lista blanca
(`app/schemas/boletas.py`). El frontend SIEMPRE muestra el resultado al
usuario para que lo confirme antes de guardar un gasto: este endpoint no
crea ningún gasto.

Dos decisiones de seguridad que se ven en el código (y que tienen prueba):

1. El formulario se lee DESPUÉS de comprobar la sesión. Si el archivo se
   declarara con `File()`, FastAPI leería hasta 10 MB del cuerpo ANTES de
   mirar el token, y cualquiera sin cuenta podría hacernos cargar 10 MB por
   petición. Por eso se lee a mano, con `request.form()`, ya autenticado.
2. Se suelta la conexión a la base de datos antes de esperar al escáner. Un
   escaneo puede tardar más de un minuto; si la conexión quedara tomada, 10
   escaneos simultáneos agotarían el pool (el plan gratuito de Supabase da
   muy pocas conexiones) y el resto de la app dejaría de funcionar.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.auth.dependencies import usuario_actual
from app.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db
from app.schemas.boletas import EscaneoOut
from app.services.escaneo import (
    FUENTES,
    ImagenInvalida,
    exigir_escaneo_configurado,
    liberar_escaneo,
    reenviar_al_escaner,
    reservar_escaneo,
    validar_imagen,
)

router = APIRouter(prefix="/boletas", tags=["Boletas"])

# Ruta completa: la usa `app/main.py` para darle a ESTA ruta (y a ninguna otra)
# un límite de cuerpo mayor.
RUTA_ESCANEO = "/api/v1/boletas/scan"

_FORMULARIO_DOCUMENTADO = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {
                        "file": {
                            "type": "string",
                            "format": "binary",
                            "description": "Foto de la boleta (JPG, PNG o WEBP, máx. 10 MB).",
                        },
                        "source": {
                            "type": "string",
                            "enum": list(FUENTES),
                            "default": "file",
                            "description": "De dónde viene la imagen.",
                        },
                    },
                }
            }
        },
    }
}


def crear_cliente_http(settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
    """Cliente HTTP hacia el escáner. Nunca sigue redirecciones: una
    redirección podría llevar la clave de servicio a otro servidor.
    (`transport` solo lo usan las pruebas para simular al escáner.)"""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.OCR_SERVICE_TIMEOUT_SECONDS, connect=15.0),
        follow_redirects=False,
        transport=transport,
    )


async def cliente_escaner(settings: Settings = Depends(get_settings)):
    async with crear_cliente_http(settings) as cliente:
        yield cliente


@router.post(
    "/scan",
    summary="Escanear una boleta",
    openapi_extra=_FORMULARIO_DOCUMENTADO,
    responses={
        200: {"model": EscaneoOut, "description": "La lectura de la boleta (a confirmar por la persona)."},
        413: {"description": "La imagen supera el máximo."},
        415: {"description": "Formato no soportado."},
        429: {"description": "Demasiados escaneos, o ya hay uno en curso."},
        502: {"description": "El servicio de escaneo falló."},
        503: {"description": "Escaneo no disponible."},
        504: {"description": "El escaneo tardó demasiado."},
    },
)
async def escanear_boleta(
    request: Request,
    usuario: User = Depends(usuario_actual),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    cliente: httpx.AsyncClient = Depends(cliente_escaner),
) -> JSONResponse:
    """Comprueba la sesión, valida la imagen y la reenvía al escáner. La
    imagen no se guarda (ver `app/services/escaneo.py`)."""
    user_id = usuario.id
    exigir_escaneo_configurado(settings)
    reservar_escaneo(db, settings, user_id)  # confirma el turno y el cupo en la base de datos
    db.close()  # libera la conexión mientras se espera al escáner (ver arriba)

    try:
        imagen, fuente = await _leer_formulario(request, settings)
        mime, extension = validar_imagen(imagen, maximo=settings.OCR_MAX_IMAGE_BYTES)
        resultado = await reenviar_al_escaner(cliente, settings, imagen, mime, extension, fuente)
    finally:
        liberar_escaneo(db, user_id)  # abre una conexión corta, ya terminada la espera

    # Es información de la boleta de este usuario: que ningún caché la guarde.
    return JSONResponse(content=resultado, headers={"Cache-Control": "no-store"})


async def _leer_formulario(request: Request, settings: Settings) -> tuple[bytes, str]:
    """Lee `file` y `source` del formulario multipart ya autenticado."""
    try:
        formulario = await request.form(max_files=1, max_fields=4)
    except HTTPException as exc:
        if exc.status_code == 413:
            raise  # el límite de cuerpo: ya trae su mensaje
        raise ImagenInvalida("No se pudo leer el formulario enviado.") from None

    try:
        archivo = formulario.get("file")
        if not isinstance(archivo, UploadFile):
            raise ImagenInvalida("Falta la imagen de la boleta (campo 'file').")
        fuente = formulario.get("source", "file")
        if fuente not in FUENTES:
            raise ImagenInvalida("El campo 'source' debe ser 'camera' o 'file'.")
        # Un byte más que el máximo basta para saber que se pasó, sin cargar el resto.
        imagen = await archivo.read(settings.OCR_MAX_IMAGE_BYTES + 1)
    finally:
        await formulario.close()
    return imagen, fuente
