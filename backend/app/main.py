"""
Punto de entrada de la aplicación FastAPI de Blynn.

Ensambla la configuración, el middleware y los routers de la API. La
lógica de negocio vive en sus propios módulos (`app/auth`, `app/db`, ...)
y nunca se implementa directamente aquí.

El escaneo de boletas (OCR) NO es parte de esta aplicación: es un
servicio aparte (`boletas-backend`). Este backend solo comprueba la sesión,
valida la imagen y se la reenvía (`app/api/boletas.py`, Etapa 4).
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.auth_routes import router as auth_router
from app.api.boletas import RUTA_ESCANEO
from app.api.boletas import router as boletas_router
from app.api.categorias import router as categorias_router
from app.api.gastos import router as gastos_router
from app.api.ingresos import router as ingresos_router
from app.api.limite_cuerpo import LimitarTamanoCuerpo
from app.api.metas import router as metas_router
from app.api.metas import router_aportes
from app.api.perfil import router as perfil_router
from app.config import get_settings, validar_configuracion
from app.services.errores import ErrorDeNegocio
from app.utils.logging_config import configure_logging

configure_logging()
settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    """Al arrancar el servidor (no en cada petición): si falta la clave
    JWT, es demasiado corta, o la configuración de producción es insegura,
    el servidor NO levanta y explica por qué."""
    validar_configuracion(settings)
    yield


app = FastAPI(
    lifespan=ciclo_de_vida,
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Backend general de Blynn: cuentas de usuario, autenticación y los "
        "datos financieros de cada usuario (gastos, ingresos, categorías y metas)."
    ),
)

# Se agrega ANTES que CORS para quedar por dentro: así hasta las respuestas
# 413 llevan las cabeceras CORS y el navegador muestra el error real.
app.add_middleware(
    LimitarTamanoCuerpo,
    max_bytes=settings.MAX_REQUEST_BODY_BYTES,
    # Solo la ruta de escaneo puede recibir una imagen (+ margen del formulario).
    limites_por_ruta={("POST", RUTA_ESCANEO): settings.OCR_MAX_IMAGE_BYTES + 64 * 1024},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(perfil_router, prefix="/api/v1")
app.include_router(categorias_router, prefix="/api/v1")
app.include_router(gastos_router, prefix="/api/v1")
app.include_router(ingresos_router, prefix="/api/v1")
app.include_router(metas_router, prefix="/api/v1")
app.include_router(router_aportes, prefix="/api/v1")
app.include_router(boletas_router, prefix="/api/v1")


@app.exception_handler(ErrorDeNegocio)
async def manejador_errores_de_negocio(_: Request, exc: ErrorDeNegocio) -> JSONResponse:
    """Traduce los errores de la capa de servicios (404, 409, 422) a HTTP."""
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.mensaje}, headers=exc.headers
    )


@app.exception_handler(Exception)
async def manejador_errores_inesperados(request: Request, exc: Exception) -> JSONResponse:
    """Red de seguridad final: cualquier excepción no capturada
    explícitamente en otro lugar se convierte en una respuesta controlada
    en vez de un error 500 sin manejar. `HTTPException` de FastAPI sigue
    manejándose por su cuenta (es más específico que `Exception`); este
    manejador solo atrapa lo verdaderamente inesperado. Nunca devuelve el
    detalle del error al cliente.
    """
    logger.exception("Error no controlado procesando %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Ocurrió un error inesperado. Por favor intenta nuevamente."},
    )


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Verifica que el servicio esté activo."""
    return {"status": "ok", "service": settings.APP_NAME}


@app.get("/health/ready", tags=["Health"])
def health_ready() -> JSONResponse:
    """Comprueba que la base de datos responde (para el despliegue).
    Distinto de /health, que solo dice que el proceso está vivo."""
    from app.db.session import BaseDeDatosNoConfiguradaError, obtener_motor

    try:
        with obtener_motor().connect() as conexion:
            conexion.execute(text("SELECT 1"))
    except BaseDeDatosNoConfiguradaError:
        return JSONResponse(status_code=503, content={"status": "sin_base_de_datos"})
    except Exception:
        logger.exception("La base de datos no responde")
        return JSONResponse(status_code=503, content={"status": "base_de_datos_caida"})
    return JSONResponse(content={"status": "ok"})
