"""
Prueba de conexión: backend de Blynn EN LOCAL  →  escáner desplegado en Render.

Qué hace, en orden:
  1. Despierta el escáner de Render (el plan gratuito lo duerme) y mide cuánto tarda.
  2. Levanta TU backend en local con una base SQLite temporal (no necesitas Postgres; las
     tablas se crean desde los modelos, como en las pruebas. Las migraciones de Alembic son
     solo para Postgres y no se usan aquí).
  3. Crea un usuario de prueba y sube una boleta sintética a `POST /api/v1/boletas/scan`.
  4. Dice si se conectaron, y si no, en qué punto falló.

El resultado de la lectura da igual: lo que se comprueba es la CONEXIÓN. No toca tu base
de datos real (usa un archivo temporal que se borra al terminar) ni tu .env.

Uso (desde la carpeta backend, con las dependencias instaladas):

    python tools/probar_render.py
    python tools/probar_render.py --escaner https://otro-escaner.onrender.com
    python tools/probar_render.py --clave LA_CLAVE      # solo si el escáner ya exige X-Service-Key
    python tools/probar_render.py --imagen mi_boleta.jpg

Código de salida: 0 = se conectaron · 1 = no · 2 = no se pudo preparar la prueba.
"""
from __future__ import annotations

import argparse
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parent.parent
ESCANER_POR_DEFECTO = "https://escaner-de-boletas-cl.onrender.com"
PUERTO = 8765


def titulo(texto: str) -> None:
    print(f"\n=== {texto} ===", flush=True)


def despertar_escaner(base: str, espera_maxima: float) -> tuple[bool, float]:
    """Llama a /health hasta que responda 200 (Render tarda en despertar)."""
    inicio = time.time()
    intento = 0
    while time.time() - inicio < espera_maxima:
        intento += 1
        try:
            r = httpx.get(f"{base}/health", timeout=30, follow_redirects=False)
            if r.status_code == 200:
                return True, time.time() - inicio
            print(f"  intento {intento}: respondió {r.status_code}; sigo esperando...", flush=True)
        except httpx.HTTPError as exc:
            print(f"  intento {intento}: sin respuesta aún ({type(exc).__name__})...", flush=True)
        time.sleep(5)
    return False, time.time() - inicio


def main() -> int:
    ap = argparse.ArgumentParser(description="Prueba backend local → escáner en Render")
    ap.add_argument("--escaner", default=ESCANER_POR_DEFECTO, help="URL base del escáner")
    ap.add_argument("--imagen", default=str(Path(__file__).with_name("boleta_sintetica.jpg")))
    ap.add_argument("--clave", default="", help="X-Service-Key, solo si el escáner ya la exige")
    ap.add_argument("--espera", type=float, default=240, help="segundos máximos para despertar y escanear")
    args = ap.parse_args()

    base = args.escaner.strip().rstrip("/")
    imagen = Path(args.imagen)
    if not imagen.is_file():
        print(f"No encuentro la imagen: {imagen}")
        return 2

    titulo("1. Despertando el escáner")
    print(f"  {base}/health", flush=True)
    vivo, segundos = despertar_escaner(base, args.espera)
    if not vivo:
        print(f"\n❌ El escáner NO respondió tras {segundos:.0f} s.")
        print("   Esto es antes de involucrar a tu backend: revisa tu conexión a internet y que el")
        print("   servicio esté 'Live' en el panel de Render.")
        return 1
    print(f"  ✅ responde (tardó {segundos:.1f} s{'; estaba dormido' if segundos > 10 else ''})", flush=True)

    titulo("2. Levantando tu backend en local")
    carpeta = tempfile.mkdtemp(prefix="blynn_prueba_")
    entorno = dict(
        os.environ,
        DATABASE_URL=f"sqlite:///{Path(carpeta, 'prueba.db').as_posix()}",
        JWT_SECRET_KEY=secrets.token_urlsafe(64),
        ENVIRONMENT="development",
        AUTH_MAX_REGISTROS_POR_IP="1000",
        OCR_SERVICE_URL=base,
        # Vacía si no se pasó --clave: así NO se usa la que haya en tu .env (una clave vacía
        # equivale a no enviar la cabecera). Las variables del entorno pesan más que el .env.
        OCR_SERVICE_KEY=args.clave,
        OCR_SERVICE_TIMEOUT_SECONDS=str(args.espera),
    )
    tablas = subprocess.run(
        [sys.executable, "-c",
         "from app.config import get_settings; from app.db.base import Base; import app.db.models; "
         "from app.db.session import crear_motor; "
         "s = get_settings(); Base.metadata.create_all(crear_motor(s.DATABASE_URL.get_secret_value(), s))"],
        cwd=BACKEND, env=entorno, capture_output=True, text=True,
    )
    if tablas.returncode != 0:
        print("❌ No se pudieron crear las tablas de prueba:\n", tablas.stderr[-800:])
        shutil.rmtree(carpeta, ignore_errors=True)
        return 2

    registro = Path(carpeta, "backend.log")
    servidor = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PUERTO), "--log-level", "info"],
        cwd=BACKEND, env=entorno, stdout=open(registro, "w", encoding="utf-8"), stderr=subprocess.STDOUT,
    )
    api = f"http://127.0.0.1:{PUERTO}/api/v1"
    try:
        for _ in range(60):
            try:
                if httpx.get(f"http://127.0.0.1:{PUERTO}/health/ready", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        else:
            print("❌ Tu backend no arrancó. Últimas líneas del registro:\n", registro.read_text(encoding="utf-8")[-1200:])
            return 2
        print(f"  ✅ backend local en {api}", flush=True)

        titulo("3. Subiendo la boleta sintética por TU backend")
        with httpx.Client(timeout=args.espera + 30) as c:
            r = c.post(f"{api}/auth/register", json={"email": "prueba@correo.cl", "password": "una-clave-larga-123"})
            if r.status_code not in (200, 201):
                print("❌ No se pudo crear el usuario de prueba:", r.status_code, r.text[:300])
                return 2
            cabeceras = {"Authorization": f"Bearer {r.json()['access_token']}"}
            inicio = time.time()
            r = c.post(
                f"{api}/boletas/scan",
                files={"file": ("boleta.jpg", imagen.read_bytes(), "image/jpeg")},
                data={"source": "file"},
                headers=cabeceras,
            )
            duracion = time.time() - inicio

        titulo("4. Resultado")
        print(f"  Respuesta de tu backend: HTTP {r.status_code}  ({duracion:.1f} s)")
        veredicto = {
            200: "✅ CONECTADOS: tu backend en local habló con el escáner de Render y recibió su respuesta.",
            401: "❌ Tu propio backend rechazó la sesión de prueba (no debería pasar).",
            415: "❌ Tu backend rechazó la imagen (¿usaste --imagen con otro formato?).",
            429: "❌ Tu backend limitó los escaneos.",
            502: "⚠️ SE CONECTARON, pero el escáner respondió algo que el backend no entiende (¿cambió su formato?).",
            503: "❌ NO se conectaron: el backend no pudo comunicarse con el escáner (o este respondió que no está disponible).",
            504: "❌ El escáner tardó demasiado en responder (más de %.0f s)." % args.espera,
        }
        print(" ", veredicto.get(r.status_code, f"❓ Respuesta inesperada: {r.status_code}"))
        try:
            cuerpo = r.json()
        except ValueError:
            cuerpo = {}
        if r.status_code == 200:
            datos = cuerpo.get("datos") or {}
            print(f"  Lectura: estado={cuerpo.get('estado')} · comercio={datos.get('comercio')} · total={datos.get('total')}")
            print("  (el contenido da igual para esta prueba)")
        else:
            print("  Detalle:", cuerpo.get("detail", r.text[:300]))
        if r.status_code in (502, 503, 504):
            lineas = [l for l in registro.read_text(encoding="utf-8").splitlines() if "escaneo" in l.lower() or "escáner" in l.lower()]
            if lineas:
                print("\n  Lo que registró tu backend:")
                for linea in lineas[-6:]:
                    print("   ", linea)
        return 0 if r.status_code in (200, 502) else 1
    finally:
        servidor.terminate()
        try:
            servidor.wait(timeout=10)
        except subprocess.TimeoutExpired:
            servidor.kill()
        shutil.rmtree(carpeta, ignore_errors=True)  # la base y el registro temporales


if __name__ == "__main__":
    sys.exit(main())
