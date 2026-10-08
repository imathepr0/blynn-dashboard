"""Punto de entrada para Vercel (funciones Python): expone la aplicación FastAPI como `app`.

El proyecto de Vercel debe tener como "Root Directory" la carpeta `backend/`. Todas las
rutas se envían aquí (ver vercel.json) y FastAPI decide cuál atiende.
"""
from pydantic import ValidationError

from app.config import get_settings, validar_configuracion

# La validación de producción (clave JWT fuerte, CORS en https, etc.) normalmente corre al
# arrancar el servidor. No doy por hecho que Vercel ejecute ese paso: la hago aquí, al cargar,
# para que una configuración insegura impida el arranque en vez de pasar en silencio.
try:
    validar_configuracion(get_settings())
except Exception as exc:
    # Las validaciones personalizadas solo describen nombres de variables,
    # nunca sus valores. Pydantic se resume sin incluir `input` para evitar
    # que una credencial termine en los registros de producción.
    if isinstance(exc, ValidationError):
        errores = exc.errors(include_input=False)
        detalle = "; ".join(
            f"{'.'.join(str(parte) for parte in error['loc'])}: {error['msg']}"
            for error in errores
        )
    elif type(exc).__name__ == "ConfiguracionInvalidaError":
        detalle = str(exc)
    elif isinstance(exc, (ImportError, ModuleNotFoundError)):
        detalle = f"{type(exc).__name__}: {exc}"
    else:
        detalle = type(exc).__name__
    print(f"Blynn API startup validation failed: {detalle}", flush=True)
    raise

from app.main import app  # noqa: E402,F401  (Vercel busca la variable `app`)
