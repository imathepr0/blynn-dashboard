"""Punto de entrada para Vercel (funciones Python): expone la aplicación FastAPI como `app`.

El proyecto de Vercel debe tener como "Root Directory" la carpeta `backend/`. Todas las
rutas se envían aquí (ver vercel.json) y FastAPI decide cuál atiende.
"""
from app.config import get_settings, validar_configuracion

# La validación de producción (clave JWT fuerte, CORS en https, etc.) normalmente corre al
# arrancar el servidor. No doy por hecho que Vercel ejecute ese paso: la hago aquí, al cargar,
# para que una configuración insegura impida el arranque en vez de pasar en silencio.
validar_configuracion(get_settings())

from app.main import app  # noqa: E402,F401  (Vercel busca la variable `app`)
