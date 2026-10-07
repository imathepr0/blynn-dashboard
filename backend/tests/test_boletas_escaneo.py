"""
Escaneo de boletas (Etapa 4): `POST /api/v1/boletas/scan`.

El escáner real (boletas-backend, en Render) NUNCA se llama desde las
pruebas: se reemplaza por un `httpx.MockTransport` que registra lo que
Blynn API le envía y responde lo que cada prueba necesite.

Qué se comprueba:
* sin sesión no se entra, y ni siquiera se LEE el cuerpo de la petición;
* la imagen se valida por sus bytes reales (no por lo que declare el cliente);
* tamaño, cupo por usuario y un solo escaneo a la vez por usuario;
* la conexión a la base de datos se suelta mientras se espera al escáner;
* cada fallo del escáner (caído, lento, despertando, respuesta rara) se
  traduce a un error claro sin filtrar detalles internos;
* la respuesta pasa por una lista blanca (campos desconocidos no salen, los
  valores sucios del OCR se sanean, un contrato roto es 502);
* la clave de servicio se envía, nunca se registra en logs, y las
  redirecciones no se siguen.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
import pytest
from fastapi import Depends
from pydantic import SecretStr

from app.api.boletas import RUTA_ESCANEO, crear_cliente_http
from app.config import Settings, validar_configuracion
from app.services import escaneo as servicio
from app.services.escaneo import RUTA_ESCANER, detectar_tipo_imagen
from tests.utils import API, Usuario

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
WEBP = b"RIFF" + b"\x10\x00\x00\x00" + b"WEBP" + b"\x00" * 200
CLAVE_SERVICIO = "clave-de-servicio-para-pruebas-123456"
NOMBRE_SECRETO = "mi foto secreta.jpg"

# Respuesta típica del escáner real (ejemplo de su README).
RESULTADO = {
    "estado": "SUCCESS",
    "mensaje": "Boleta procesada correctamente.",
    "confianza_general": 92.5,
    "confianza_por_campo": {
        "comercio": 95.0,
        "fecha": 90.0,
        "metodo_pago": 88.0,
        "productos": 91.0,
        "total": 97.0,
    },
    "advertencias": [],
    "datos": {
        "comercio": "Jumbo",
        "fecha": "2026-07-14",
        "metodo_pago": "Débito",
        "productos": [{"nombre": "Pan Hallulla", "cantidad": 1, "precio_unitario": 1200, "confianza": 93.0}],
        "total": 1200,
    },
}


class EscanerFalso:
    """Registra cada llamada y responde con `self.respuesta(request)`."""

    def __init__(self) -> None:
        self.llamadas: list[httpx.Request] = []
        self.respuesta = lambda peticion: httpx.Response(200, json=RESULTADO)

    async def handler(self, peticion: httpx.Request) -> httpx.Response:
        self.llamadas.append(peticion)
        resultado = self.respuesta(peticion)
        if asyncio.iscoroutine(resultado):
            resultado = await resultado
        return resultado


@pytest.fixture(autouse=True)
def sin_pausa(monkeypatch):
    """El reintento por arranque en frío espera 5 s de verdad; en pruebas, 0."""
    monkeypatch.setattr(servicio, "_PAUSA_REINTENTO", 0)


@pytest.fixture
def escaner() -> EscanerFalso:
    return EscanerFalso()


@pytest.fixture
def api(crear_cliente, escaner):
    """Fábrica de clientes con el escaneo configurado y el escáner falso."""
    from app.api.boletas import cliente_escaner
    from app.config import get_settings
    from app.main import app

    def _crear(**cambios):
        base = {
            "OCR_SERVICE_URL": "https://escaner.test",
            "OCR_SERVICE_KEY": SecretStr(CLAVE_SERVICIO),
            "OCR_SERVICE_TIMEOUT_SECONDS": 5.0,
        }
        base.update(cambios)
        cliente = crear_cliente(**base)

        async def _cliente_falso(settings: Settings = Depends(get_settings)):
            transporte = httpx.MockTransport(escaner.handler)
            async with crear_cliente_http(settings, transport=transporte) as c:
                yield c

        app.dependency_overrides[cliente_escaner] = _cliente_falso
        return cliente

    return _crear


@pytest.fixture
def cliente(api):
    return api()


@pytest.fixture
def ana(cliente):
    return Usuario(cliente, "ana@correo.cl")


@pytest.fixture
def beto(cliente):
    return Usuario(cliente, "beto@correo.cl")


def subir(cliente, usuario, contenido=JPEG, nombre=NOMBRE_SECRETO, tipo="image/jpeg", **campos):
    return cliente.post(
        f"{API}/boletas/scan",
        files={"file": (nombre, contenido, tipo)},
        data=campos or None,
        headers=usuario.headers,
    )


# ---------------------------------------------------------------------- #
# Sesión
# ---------------------------------------------------------------------- #
def test_la_ruta_coincide_con_la_que_recibe_el_limite_propio():
    from app.main import app

    assert "post" in app.openapi()["paths"][RUTA_ESCANEO]
    assert RUTA_ESCANEO == "/api/v1" + "/boletas/scan"


def test_sin_sesion_responde_401_y_no_llama_al_escaner(cliente, escaner):
    r = cliente.post(f"{API}/boletas/scan", files={"file": ("a.jpg", JPEG, "image/jpeg")})
    assert r.status_code == 401
    assert escaner.llamadas == []


def test_con_token_falso_responde_401(cliente, escaner):
    r = cliente.post(
        f"{API}/boletas/scan",
        files={"file": ("a.jpg", JPEG, "image/jpeg")},
        headers={"Authorization": "Bearer esto.no.es.un.jwt"},
    )
    assert r.status_code == 401
    assert escaner.llamadas == []


def test_sin_sesion_ni_siquiera_se_lee_el_cuerpo(api, escaner):
    """Si el archivo se declarara con `File()`, FastAPI leería hasta 10 MB
    ANTES de mirar el token. Aquí se cuentan los bloques de cuerpo que el
    servidor realmente consume: sin sesión deben ser 0; con sesión, más de 0
    (el control que demuestra que la prueba mide algo)."""
    from app.main import app

    cliente = api()
    ana = Usuario(cliente, "ana@correo.cl")
    grande = JPEG + b"\x00" * 300_000

    async def correr(headers):
        leidos = 0

        async def app_contada(scope, receive, send):
            async def receive_contado():
                nonlocal leidos
                mensaje = await receive()
                if mensaje["type"] == "http.request" and mensaje.get("body"):
                    leidos += 1
                return mensaje

            await app(scope, receive_contado, send)

        transporte = httpx.ASGITransport(app=app_contada)
        async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as c:
            r = await c.post(
                f"{API}/boletas/scan", files={"file": ("a.jpg", grande, "image/jpeg")}, headers=headers
            )
        return r.status_code, leidos

    estado, leidos = asyncio.run(correr({}))
    assert (estado, leidos) == (401, 0)

    estado, leidos = asyncio.run(correr(ana.headers))
    assert estado == 200
    assert leidos > 0


# ---------------------------------------------------------------------- #
# Camino feliz y lo que se reenvía
# ---------------------------------------------------------------------- #
def test_devuelve_el_resultado_del_escaner_sin_cache(cliente, ana, escaner):
    r = subir(cliente, ana)
    assert r.status_code == 200
    assert r.json() == RESULTADO
    assert r.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("contenido, mime, extension", [(JPEG, "image/jpeg", "jpg"), (PNG, "image/png", "png"), (WEBP, "image/webp", "webp")])
def test_acepta_jpg_png_y_webp(cliente, ana, escaner, contenido, mime, extension):
    r = subir(cliente, ana, contenido=contenido, tipo="application/octet-stream", nombre="x.bin")
    assert r.status_code == 200
    enviado = escaner.llamadas[0].content
    assert f'filename="boleta.{extension}"'.encode() in enviado
    assert f"Content-Type: {mime}".encode() in enviado
    assert contenido in enviado  # la imagen llega intacta


def test_reenvia_a_la_url_y_ruta_correctas_con_la_clave_de_servicio(cliente, ana, escaner):
    subir(cliente, ana)
    peticion = escaner.llamadas[0]
    assert peticion.method == "POST"
    assert str(peticion.url) == "https://escaner.test" + RUTA_ESCANER
    assert peticion.headers["x-service-key"] == CLAVE_SERVICIO
    assert peticion.headers["content-type"].startswith("multipart/form-data")


def test_la_url_base_puede_terminar_en_barra(api, escaner):
    cliente = api(OCR_SERVICE_URL="https://escaner.test/")
    ana = Usuario(cliente, "ana@correo.cl")
    assert subir(cliente, ana).status_code == 200
    assert str(escaner.llamadas[0].url) == "https://escaner.test" + RUTA_ESCANER


def test_sin_clave_configurada_no_se_envia_la_cabecera(api, escaner):
    cliente = api(OCR_SERVICE_KEY=None)
    ana = Usuario(cliente, "ana@correo.cl")
    assert subir(cliente, ana).status_code == 200
    assert "x-service-key" not in escaner.llamadas[0].headers


def test_nunca_se_reenvia_el_nombre_de_archivo_del_cliente(cliente, ana, escaner):
    subir(cliente, ana, nombre=NOMBRE_SECRETO)
    assert NOMBRE_SECRETO.encode() not in escaner.llamadas[0].content
    assert b'filename="boleta.jpg"' in escaner.llamadas[0].content


def test_source_por_defecto_es_file_y_se_reenvia_camera(cliente, ana, escaner):
    subir(cliente, ana)
    subir(cliente, ana, source="camera")
    assert b'name="source"\r\n\r\nfile' in escaner.llamadas[0].content
    assert b'name="source"\r\n\r\ncamera' in escaner.llamadas[1].content


def test_source_invalido_responde_422_sin_llamar_al_escaner(cliente, ana, escaner):
    r = subir(cliente, ana, source="drone")
    assert r.status_code == 422
    assert "source" in r.json()["detail"]
    assert escaner.llamadas == []


def test_falta_el_archivo_responde_422(cliente, ana, escaner):
    r = cliente.post(f"{API}/boletas/scan", data={"source": "file"}, files={"otro": ("a.jpg", JPEG)}, headers=ana.headers)
    assert r.status_code == 422
    assert escaner.llamadas == []


def test_cuerpo_json_en_vez_de_formulario_responde_422(cliente, ana, escaner):
    r = cliente.post(f"{API}/boletas/scan", json={"file": "hola"}, headers=ana.headers)
    assert r.status_code == 422
    assert escaner.llamadas == []


def test_documentacion_openapi_muestra_el_formulario(cliente):
    from app.main import app

    operacion = app.openapi()["paths"][RUTA_ESCANEO]["post"]
    esquema = operacion["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert esquema["properties"]["file"]["format"] == "binary"
    assert esquema["properties"]["source"]["enum"] == ["camera", "file"]


# ---------------------------------------------------------------------- #
# Validación de la imagen
# ---------------------------------------------------------------------- #
def test_archivo_vacio_responde_422(cliente, ana, escaner):
    r = subir(cliente, ana, contenido=b"")
    assert r.status_code == 422
    assert escaner.llamadas == []


@pytest.mark.parametrize(
    "contenido",
    [
        b"%PDF-1.7\n" + b"0" * 100,
        b"GIF89a" + b"0" * 100,
        b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
        b"MZ\x90\x00" + b"0" * 100,  # ejecutable de Windows
        b"RIFF\x10\x00\x00\x00WAVE" + b"0" * 100,  # RIFF, pero audio
        b"texto cualquiera que dice ser una foto",
    ],
)
def test_un_archivo_que_no_es_jpg_png_ni_webp_responde_415_aunque_diga_serlo(cliente, ana, escaner, contenido):
    """El tipo se decide por los bytes, no por el Content-Type ni el nombre."""
    r = subir(cliente, ana, contenido=contenido, nombre="foto.jpg", tipo="image/jpeg")
    assert r.status_code == 415
    assert escaner.llamadas == []


def test_imagen_sobre_el_maximo_responde_413(api, escaner):
    cliente = api(OCR_MAX_IMAGE_BYTES=1000)
    ana = Usuario(cliente, "ana@correo.cl")
    r = subir(cliente, ana, contenido=JPEG + b"\x00" * 900)
    assert r.status_code == 413
    assert escaner.llamadas == []
    # justo en el máximo, pasa
    assert subir(cliente, ana, contenido=JPEG[:1000].ljust(1000, b"\x00")).status_code == 200


def test_una_imagen_de_varios_mb_pasa_el_limite_de_cuerpo_de_la_ruta(cliente, ana, escaner):
    """El límite general de cuerpo es 1 MiB; esta ruta tiene uno propio."""
    r = subir(cliente, ana, contenido=JPEG + b"\x00" * 3_000_000)
    assert r.status_code == 200


def test_cuerpo_mas_grande_que_el_permitido_a_la_ruta_responde_413_sin_leerlo(cliente, ana, escaner):
    r = subir(cliente, ana, contenido=JPEG + b"\x00" * (10 * 1024 * 1024 + 200_000))
    assert r.status_code == 413
    # El mensaje del límite de CUERPO (no el de validar_imagen): se rechazó
    # sin cargar la imagen entera.
    assert r.json()["detail"] == "El cuerpo de la petición es demasiado grande."
    assert escaner.llamadas == []


def test_el_permiso_de_cuerpo_grande_es_solo_para_la_ruta_de_escaneo(cliente, ana):
    r = cliente.post(f"{API}/expenses", content=b"x" * 2_000_000, headers=ana.headers)
    assert r.status_code == 413


def test_detectar_tipo_imagen_no_se_deja_enganar_por_prefijos_cortos():
    assert detectar_tipo_imagen(b"") is None
    assert detectar_tipo_imagen(b"\xff\xd8") is None
    assert detectar_tipo_imagen(b"RIFF") is None
    assert detectar_tipo_imagen(JPEG) == ("image/jpeg", "jpg")


# ---------------------------------------------------------------------- #
# Configuración
# ---------------------------------------------------------------------- #
def test_sin_OCR_SERVICE_URL_el_escaneo_responde_503(api, escaner):
    cliente = api(OCR_SERVICE_URL=None)
    ana = Usuario(cliente, "ana@correo.cl")
    r = subir(cliente, ana)
    assert r.status_code == 503
    assert escaner.llamadas == []


def _config_produccion(**extra) -> Settings:
    return Settings(
        JWT_SECRET_KEY="k" * 64,
        ENVIRONMENT="production",
        DATABASE_URL="postgresql://u:p@host.test:5432/db",
        CORS_ORIGINS=["https://blynn.cl"],
        **extra,
    )


def test_en_produccion_la_url_del_escaner_debe_ser_https():
    with pytest.raises(Exception) as e:
        validar_configuracion(_config_produccion(OCR_SERVICE_URL="http://escaner.test"))
    assert "OCR_SERVICE_URL" in str(e.value)
    validar_configuracion(_config_produccion(OCR_SERVICE_URL="https://escaner.test"))


def test_en_produccion_una_clave_de_servicio_corta_se_rechaza():
    with pytest.raises(Exception) as e:
        validar_configuracion(_config_produccion(OCR_SERVICE_URL="https://e.test", OCR_SERVICE_KEY=SecretStr("corta")))
    assert "OCR_SERVICE_KEY" in str(e.value)
    validar_configuracion(
        _config_produccion(OCR_SERVICE_URL="https://e.test", OCR_SERVICE_KEY=SecretStr(CLAVE_SERVICIO))
    )


# ---------------------------------------------------------------------- #
# Cupo y concurrencia por usuario
# ---------------------------------------------------------------------- #
def test_limite_de_escaneos_por_usuario_responde_429_con_retry_after(api, escaner):
    cliente = api(OCR_MAX_ESCANEOS_POR_USUARIO=2)
    ana = Usuario(cliente, "ana@correo.cl")
    beto = Usuario(cliente, "beto@correo.cl")

    assert subir(cliente, ana).status_code == 200
    assert subir(cliente, ana).status_code == 200
    r = subir(cliente, ana)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
    assert len(escaner.llamadas) == 2  # el tercero no llegó al escáner

    # El cupo es por usuario: Beto no se ve afectado.
    assert subir(cliente, beto).status_code == 200


def test_un_solo_escaneo_a_la_vez_por_usuario(api, escaner):
    from app.main import app

    cliente = api()
    ana = Usuario(cliente, "ana@correo.cl")
    beto = Usuario(cliente, "beto@correo.cl")

    async def correr():
        liberar = asyncio.Event()
        dentro = asyncio.Event()

        async def lento(_peticion):
            dentro.set()
            await liberar.wait()
            return httpx.Response(200, json=RESULTADO)

        escaner.respuesta = lento
        archivos = {"file": ("a.jpg", JPEG, "image/jpeg")}
        transporte = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as c:
            primero = asyncio.create_task(c.post(f"{API}/boletas/scan", files=archivos, headers=ana.headers))
            await dentro.wait()
            segundo = await c.post(f"{API}/boletas/scan", files=archivos, headers=ana.headers)
            liberar.set()
            resultado_primero = await primero
            tercero = await c.post(f"{API}/boletas/scan", files=archivos, headers=ana.headers)
            otro_usuario = await c.post(f"{API}/boletas/scan", files=archivos, headers=beto.headers)
        return resultado_primero.status_code, segundo, tercero.status_code, otro_usuario.status_code

    primero, segundo, tercero, otro = asyncio.run(correr())
    assert primero == 200
    assert segundo.status_code == 429
    assert "en curso" in segundo.json()["detail"]
    assert tercero == 200  # al terminar el primero, el cupo "en curso" se liberó
    assert otro == 200


def test_si_el_escaner_falla_el_usuario_queda_libre_para_reintentar(api, escaner):
    cliente = api()
    ana = Usuario(cliente, "ana@correo.cl")
    escaner.respuesta = lambda _p: httpx.Response(500, json={"detail": "boom"})
    assert subir(cliente, ana).status_code == 502
    escaner.respuesta = lambda _p: httpx.Response(200, json=RESULTADO)
    assert subir(cliente, ana).status_code == 200


def test_una_imagen_invalida_tambien_libera_al_usuario(cliente, ana):
    assert subir(cliente, ana, contenido=b"no soy una imagen").status_code == 415
    assert subir(cliente, ana).status_code == 200


# ---------------------------------------------------------------------- #
# Base de datos
# ---------------------------------------------------------------------- #
def test_la_conexion_a_la_base_se_suelta_mientras_se_espera_al_escaner(api, escaner, fabrica_sesiones):
    """Un escaneo puede durar más de un minuto; si la sesión de la base de
    datos siguiera en transacción, tendría tomada una conexión del pool."""
    from app.db.session import get_db
    from app.main import app

    cliente = api()
    ana = Usuario(cliente, "ana@correo.cl")
    sesiones = []

    def _get_db_registrando():
        sesion = fabrica_sesiones()
        sesiones.append(sesion)
        try:
            yield sesion
        finally:
            sesion.close()

    app.dependency_overrides[get_db] = _get_db_registrando
    en_transaccion = []

    def respuesta(_peticion):
        en_transaccion.append(sesiones[-1].in_transaction())
        return httpx.Response(200, json=RESULTADO)

    escaner.respuesta = respuesta
    assert subir(cliente, ana).status_code == 200
    assert en_transaccion == [False]


# ---------------------------------------------------------------------- #
# Fallos del escáner
# ---------------------------------------------------------------------- #
def test_escaner_caido_responde_503_tras_un_reintento(cliente, ana, escaner):
    def caido(_peticion):
        raise httpx.ConnectError("no hay conexión")

    escaner.respuesta = caido
    r = subir(cliente, ana)
    assert r.status_code == 503
    assert len(escaner.llamadas) == 2


def test_escaner_lento_responde_504_sin_reintentar(cliente, ana, escaner):
    def lento(_peticion):
        raise httpx.ReadTimeout("tardó")

    escaner.respuesta = lento
    r = subir(cliente, ana)
    assert r.status_code == 504
    assert len(escaner.llamadas) == 1


def test_el_tiempo_total_esta_acotado(api, escaner):
    cliente = api(OCR_SERVICE_TIMEOUT_SECONDS=0.2)
    ana = Usuario(cliente, "ana@correo.cl")

    async def cuelga(_peticion):
        await asyncio.sleep(3)
        return httpx.Response(200, json=RESULTADO)

    escaner.respuesta = cuelga
    r = subir(cliente, ana)
    assert r.status_code == 504


def test_escaner_dormido_se_reintenta_una_vez_y_funciona(cliente, ana, escaner):
    """Render apaga el servicio por inactividad; al despertar, su proxy
    responde 503 con HTML (sin JSON)."""
    respuestas = iter(
        [
            httpx.Response(503, text="<html>Service waking up</html>", headers={"content-type": "text/html"}),
            httpx.Response(200, json=RESULTADO),
        ]
    )
    escaner.respuesta = lambda _p: next(respuestas)
    r = subir(cliente, ana)
    assert r.status_code == 200
    assert r.json() == RESULTADO
    assert len(escaner.llamadas) == 2


def test_un_503_con_json_del_propio_escaner_no_se_reintenta(cliente, ana, escaner):
    escaner.respuesta = lambda _p: httpx.Response(503, json={"detail": "Tesseract no disponible"})
    r = subir(cliente, ana)
    assert r.status_code == 503
    assert len(escaner.llamadas) == 1
    assert "Tesseract" not in r.text


def test_si_sigue_dormido_tras_el_reintento_responde_503(cliente, ana, escaner):
    escaner.respuesta = lambda _p: httpx.Response(502, text="bad gateway", headers={"content-type": "text/plain"})
    r = subir(cliente, ana)
    assert r.status_code == 503
    assert len(escaner.llamadas) == 2


@pytest.mark.parametrize("codigo", [400, 401, 403, 404, 413, 415, 422, 500])
def test_errores_del_escaner_se_traducen_a_502_sin_filtrar_su_cuerpo(cliente, ana, escaner, codigo):
    escaner.respuesta = lambda _p: httpx.Response(codigo, json={"detail": "SECRETO-INTERNO traceback /app/x.py"})
    r = subir(cliente, ana)
    assert r.status_code == 502
    assert "SECRETO-INTERNO" not in r.text
    assert len(escaner.llamadas) == 1


@pytest.mark.parametrize(
    "respuesta",
    [
        httpx.Response(200, text="esto no es json", headers={"content-type": "text/plain"}),
        httpx.Response(200, json=["una", "lista"]),
        httpx.Response(200, json="texto"),
    ],
)
def test_respuesta_200_que_no_es_un_objeto_json_responde_502(cliente, ana, escaner, respuesta):
    escaner.respuesta = lambda _p: respuesta
    assert subir(cliente, ana).status_code == 502


def test_las_redirecciones_no_se_siguen(cliente, ana, escaner):
    """Una redirección podría llevar la clave de servicio a otro servidor."""
    escaner.respuesta = lambda _p: httpx.Response(307, headers={"location": "https://atacante.test/robar"})
    r = subir(cliente, ana)
    assert r.status_code == 502
    assert [str(p.url) for p in escaner.llamadas] == ["https://escaner.test" + RUTA_ESCANER]


def test_el_cliente_real_no_sigue_redirecciones_y_acota_el_tiempo():
    cliente = crear_cliente_http(Settings(JWT_SECRET_KEY="k" * 64, OCR_SERVICE_TIMEOUT_SECONDS=77.0))
    assert cliente.follow_redirects is False
    assert cliente.timeout.read == 77.0
    asyncio.run(cliente.aclose())


# ---------------------------------------------------------------------- #
# Lista blanca de la respuesta
# ---------------------------------------------------------------------- #
def test_solo_pasan_los_campos_declarados_en_el_esquema(cliente, ana, escaner):
    """Un campo interno o de depuración que algún día agregue el escáner no
    debe llegar al navegador."""
    sucio = {
        **RESULTADO,
        "texto_completo": "TEXTO CRUDO DEL OCR",
        "debug": {"ruta": "/app/tmp/x"},
        "datos": {
            **RESULTADO["datos"],
            "rut_comercio": "76.123.456-7",
            "productos": [{**RESULTADO["datos"]["productos"][0], "interno": "no"}],
        },
    }
    escaner.respuesta = lambda _p: httpx.Response(200, json=sucio)
    r = subir(cliente, ana)
    assert r.status_code == 200
    assert r.json() == RESULTADO
    assert "OCR" not in r.text and "rut_comercio" not in r.text and "/app/tmp" not in r.text


def test_una_lectura_parcial_se_devuelve_con_los_vacios_en_null(cliente, ana, escaner):
    parcial = {"estado": "PARTIAL_SUCCESS", "mensaje": "Faltan datos.", "datos": {"total": 5000}}
    escaner.respuesta = lambda _p: httpx.Response(200, json=parcial)
    cuerpo = subir(cliente, ana).json()
    assert cuerpo["estado"] == "PARTIAL_SUCCESS"
    assert cuerpo["datos"]["total"] == 5000
    assert cuerpo["datos"]["comercio"] is None and cuerpo["datos"]["productos"] == []
    assert cuerpo["confianza_general"] is None and cuerpo["advertencias"] == []


@pytest.mark.parametrize("estado", ["IMAGE_UNREADABLE", "NO_RECEIPT_DETECTED", "UNSUPPORTED_FILE", "INCOMPLETE_RECEIPT", "LOW_CONFIDENCE"])
def test_los_demas_estados_del_escaner_se_entregan_tal_cual(cliente, ana, escaner, estado):
    escaner.respuesta = lambda _p: httpx.Response(200, json={"estado": estado, "mensaje": "Mensaje del escáner.", "datos": None})
    r = subir(cliente, ana)
    assert r.status_code == 200
    assert r.json()["estado"] == estado
    assert r.json()["datos"] is None


def test_los_valores_sucios_del_ocr_se_sanean_sin_perder_la_lectura(cliente, ana, escaner):
    """El OCR devuelve basura a veces: un campo raro no debe tumbar todo."""
    crudo = (
        b'{"estado": "SUCCESS", "mensaje": "ok\\u0000\\u0007!", "confianza_general": 250,'
        b' "advertencias": ["", "  aviso  ", "\\u0000"],'
        b' "datos": {"comercio": "  J\\u0000umbo\\n  ", "fecha": "2999-01-01", "metodo_pago": "   ",'
        b' "total": NaN, "productos": [{"nombre": "Pan", "cantidad": -1, "precio_unitario": true, "confianza": 101}]}}'
    )
    escaner.respuesta = lambda _p: httpx.Response(200, content=crudo, headers={"content-type": "application/json"})
    r = subir(cliente, ana)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["mensaje"] == "ok!"
    assert cuerpo["confianza_general"] is None  # fuera de 0-100
    assert cuerpo["advertencias"] == ["aviso"]
    datos = cuerpo["datos"]
    assert datos["comercio"] == "Jumbo"
    assert datos["fecha"] is None  # año absurdo
    assert datos["metodo_pago"] is None  # solo espacios
    assert datos["total"] is None  # NaN
    assert datos["productos"] == [{"nombre": "Pan", "cantidad": None, "precio_unitario": None, "confianza": None}]


def test_la_fecha_valida_se_conserva_y_la_que_no_es_fecha_se_descarta(cliente, ana, escaner):
    for entrada, esperado in [("2026-07-14", "2026-07-14"), ("14/07/2026", None), ("2026-02-30", None), ("", None)]:
        escaner.respuesta = lambda _p, f=entrada: httpx.Response(200, json={"estado": "SUCCESS", "mensaje": "ok", "datos": {"fecha": f}})
        assert subir(cliente, ana).json()["datos"]["fecha"] == esperado


def test_los_textos_largos_se_recortan(cliente, ana, escaner):
    escaner.respuesta = lambda _p: httpx.Response(200, json={"estado": "SUCCESS", "mensaje": "m" * 5000, "datos": {"comercio": "C" * 5000}})
    cuerpo = subir(cliente, ana).json()
    assert len(cuerpo["mensaje"]) == 1000
    assert len(cuerpo["datos"]["comercio"]) == 300


@pytest.mark.parametrize(
    "roto",
    [
        {"estado": "ESTADO_NUEVO", "mensaje": "x"},  # estado desconocido: el contrato cambió
        {"mensaje": "sin estado"},
        {"estado": "SUCCESS"},  # sin mensaje
        {"estado": "SUCCESS", "mensaje": "x", "datos": ["no", "es", "un", "objeto"]},
        {"estado": "SUCCESS", "mensaje": "x", "advertencias": "una sola cadena"},
        {"estado": "SUCCESS", "mensaje": "x", "datos": {"comercio": 12345}},
        {"estado": "SUCCESS", "mensaje": "x", "datos": {"productos": [{"nombre": "p"}] * 201}},
        {"estado": "SUCCESS", "mensaje": "x", "advertencias": ["a"] * 51},
    ],
)
def test_una_respuesta_que_rompe_el_contrato_responde_502(cliente, ana, escaner, roto):
    escaner.respuesta = lambda _p: httpx.Response(200, json=roto)
    r = subir(cliente, ana)
    assert r.status_code == 502


def test_si_el_contrato_se_rompe_el_log_dice_que_campos_pero_no_sus_valores(cliente, ana, escaner, caplog):
    """Los valores son datos de la boleta de una persona."""
    caplog.set_level(logging.DEBUG)
    escaner.respuesta = lambda _p: httpx.Response(
        200, json={"estado": "SUCCESS", "mensaje": "x", "datos": {"comercio": 99, "total": "DATO-PRIVADO-DE-LA-BOLETA"}}
    )
    assert subir(cliente, ana).status_code == 502
    assert "datos.comercio" in caplog.text
    assert "DATO-PRIVADO" not in caplog.text


def test_la_clave_con_espacios_o_salto_de_linea_se_envia_recortada(api, escaner):
    """Pegar un secreto desde el celular suele dejar un espacio o un salto de línea."""
    cliente = api(OCR_SERVICE_KEY=SecretStr(f"  {CLAVE_SERVICIO}\n"))
    ana = Usuario(cliente, "ana@correo.cl")
    assert subir(cliente, ana).status_code == 200
    assert escaner.llamadas[0].headers["x-service-key"] == CLAVE_SERVICIO


def test_una_clave_vacia_equivale_a_no_tener_clave_y_no_envia_la_cabecera(api, escaner):
    """`OCR_SERVICE_KEY=` (vacía) en el .env no debe mandar una cabecera vacía."""
    for vacia in ("", "   ", "\n"):
        cliente = api(OCR_SERVICE_KEY=SecretStr(vacia))
        ana = Usuario(cliente, f"ana{len(escaner.llamadas)}@correo.cl")
        assert subir(cliente, ana).status_code == 200
        assert "x-service-key" not in escaner.llamadas[-1].headers


def test_una_clave_corta_rellena_de_espacios_sigue_siendo_corta():
    with pytest.raises(Exception) as e:
        validar_configuracion(
            _config_produccion(OCR_SERVICE_URL="https://e.test", OCR_SERVICE_KEY=SecretStr("   " + "a" * 10 + "   " * 5))
        )
    assert "OCR_SERVICE_KEY" in str(e.value)


# ---------------------------------------------------------------------- #
# Privacidad
# ---------------------------------------------------------------------- #
def test_los_logs_no_contienen_la_clave_ni_el_nombre_del_archivo(cliente, ana, escaner, caplog):
    caplog.set_level(logging.DEBUG)
    escaner.respuesta = lambda _p: httpx.Response(500, json={"detail": "x"})
    subir(cliente, ana)
    escaner.respuesta = lambda _p: (_ for _ in ()).throw(httpx.ConnectError("x"))
    subir(cliente, ana)
    assert CLAVE_SERVICIO not in caplog.text
    assert NOMBRE_SECRETO not in caplog.text
    assert "SecretStr" not in caplog.text


def test_la_clave_de_servicio_no_aparece_al_imprimir_la_configuracion():
    config = Settings(JWT_SECRET_KEY="k" * 64, OCR_SERVICE_KEY=SecretStr(CLAVE_SERVICIO))
    assert CLAVE_SERVICIO not in repr(config)
    assert CLAVE_SERVICIO not in str(config)


def test_el_escaneo_no_crea_ningun_gasto(cliente, ana, escaner):
    assert subir(cliente, ana).status_code == 200
    assert ana.get("/expenses").json() == []


# ---------------------------------------------------------------------- #
# Turno y cupo en la base de datos (válidos entre instancias)
# ---------------------------------------------------------------------- #
def test_un_turno_abandonado_vence_solo(api, escaner, fabrica_sesiones):
    """Si un proceso muere en pleno escaneo, el usuario no queda bloqueado para siempre."""
    import time

    from app.db.models import EscaneoActivo, User

    cliente = api(OCR_SERVICE_TIMEOUT_SECONDS=5.0)
    ana = Usuario(cliente, "ana@correo.cl")
    with fabrica_sesiones() as db:
        usuario = db.query(User).filter_by(email="ana@correo.cl").one()
        db.add(EscaneoActivo(user_id=usuario.id, iniciado_ts=time.time()))  # turno recién tomado
        db.commit()
        user_id = usuario.id
    assert subir(cliente, ana).status_code == 429  # sigue "en curso"

    with fabrica_sesiones() as db:
        db.query(EscaneoActivo).filter_by(user_id=user_id).update({"iniciado_ts": time.time() - 3600})
        db.commit()
    assert subir(cliente, ana).status_code == 200  # el turno viejo venció


def test_al_terminar_no_queda_ningun_turno_en_la_base(cliente, ana, escaner, fabrica_sesiones):
    from app.db.models import EscaneoActivo

    assert subir(cliente, ana).status_code == 200
    escaner.respuesta = lambda _p: httpx.Response(500, json={"detail": "x"})
    assert subir(cliente, ana).status_code == 502
    with fabrica_sesiones() as db:
        assert db.query(EscaneoActivo).count() == 0


def test_el_cupo_de_escaneos_no_guarda_el_id_del_usuario_en_claro(api, escaner, fabrica_sesiones):
    from sqlalchemy import select

    from app.db.models import IntentoLimitado, User

    cliente = api()
    ana = Usuario(cliente, "ana@correo.cl")
    assert subir(cliente, ana).status_code == 200
    with fabrica_sesiones() as db:
        usuario = db.query(User).filter_by(email="ana@correo.cl").one()
        filas = db.scalars(select(IntentoLimitado).where(IntentoLimitado.nombre == "escaneos")).all()
        assert len(filas) == 1 and str(usuario.id) not in filas[0].clave
