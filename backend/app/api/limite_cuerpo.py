"""
Límite de tamaño del cuerpo de las peticiones.

Sin esto, alguien podría enviar un JSON de cientos de MB a cualquier
endpoint y el servidor lo cargaría entero en memoria. Se revisa de dos
formas: por la cabecera `Content-Length` (rechazo inmediato, sin leer
nada) y contando los bytes que realmente llegan (por si la cabecera
miente o el envío es "chunked").

El escaneo de boletas (Etapa 4) necesita un límite mayor para imágenes:
se da como excepción explícita y exacta (método + ruta) en `limites_por_ruta`.
Cualquier otra ruta conserva el límite general. La excepción sigue siendo un
tope: una ruta con permiso para 10 MiB no puede recibir 11.
"""
from __future__ import annotations

from fastapi import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MENSAJE = "El cuerpo de la petición es demasiado grande."


class LimitarTamanoCuerpo:
    def __init__(
        self,
        app: ASGIApp,
        max_bytes: int,
        limites_por_ruta: dict[tuple[str, str], int] | None = None,
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        # {("POST", "/api/v1/boletas/scan"): bytes}
        self.limites_por_ruta = limites_por_ruta or {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limite = self.limites_por_ruta.get((scope["method"], scope["path"]), self.max_bytes)

        for nombre, valor in scope["headers"]:
            if nombre == b"content-length":
                try:
                    declarado = int(valor)
                except ValueError:
                    declarado = 0
                if declarado > limite:
                    respuesta = JSONResponse(status_code=413, content={"detail": MENSAJE})
                    await respuesta(scope, receive, send)
                    return

        recibidos = 0

        async def receive_limitado() -> Message:
            nonlocal recibidos
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                recibidos += len(mensaje.get("body", b""))
                if recibidos > limite:
                    # HTTPException (no una excepción propia): FastAPI la
                    # deja pasar en vez de convertirla en un 400 genérico.
                    raise HTTPException(status_code=413, detail=MENSAJE)
            return mensaje

        await self.app(scope, receive_limitado, send)
