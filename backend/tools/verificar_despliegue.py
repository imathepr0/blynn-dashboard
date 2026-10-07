"""
Verifica un despliegue REAL (backend + frontend ya publicados). Crea un usuario de prueba.

    python tools/verificar_despliegue.py --api https://TU-BACKEND.vercel.app --frontend https://TU-FRONTEND.vercel.app
    ... --con-escaneo      (además sube una boleta sintética; la primera vez puede tardar más de un minuto)

Qué comprueba: que el backend responde y llega a la base de datos; que solo tu frontend puede
llamarlo desde un navegador (CORS); que se puede registrar, iniciar sesión y leer datos; y,
lo más importante en hosting con proxy, que la IP del cliente NO se puede falsificar: si se
pudiera, cualquiera esquivaría el límite de intentos de contraseña cambiando una cabecera.
Código de salida: 0 = todo bien · 1 = algo falló.
"""
from __future__ import annotations

import argparse
import secrets
import sys
import time
from pathlib import Path

import httpx

fallos: list[str] = []


def ok(cond: bool, texto: str, ayuda: str = "") -> bool:
    print(("  ✅ " if cond else "  ❌ ") + texto)
    if not cond:
        fallos.append(texto)
        if ayuda:
            print("     →", ayuda)
    return cond


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True, help="URL base del backend, sin /api/v1")
    ap.add_argument("--frontend", required=True, help="URL del frontend (la que va en CORS_ORIGINS)")
    ap.add_argument("--con-escaneo", action="store_true")
    a = ap.parse_args()
    api, front = a.api.rstrip("/"), a.frontend.rstrip("/")
    v1 = f"{api}/api/v1"
    c = httpx.Client(timeout=60)

    print("\n1. Backend y base de datos")
    try:
        r = c.get(f"{api}/health/ready")
    except httpx.HTTPError as exc:
        ok(False, f"el backend responde ({type(exc).__name__})", "revisa la URL y que el despliegue haya terminado")
        return 1
    ok(r.status_code == 200, f"/health/ready responde 200 (respondió {r.status_code})",
       "si es 503: revisa DATABASE_URL (pooler de transacción, puerto 6543) y que el proyecto de Supabase no esté pausado")
    ok(api.startswith("https://"), "el backend se sirve por https")

    print("\n2. CORS (quién puede llamar al backend desde un navegador)")
    pre = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type,authorization"}
    r = c.options(f"{v1}/auth/login", headers={"Origin": front, **pre})
    ok(r.headers.get("access-control-allow-origin") == front, "tu frontend está permitido",
       f"CORS_ORIGINS debe contener exactamente {front}")
    r = c.options(f"{v1}/auth/login", headers={"Origin": "https://sitio-malicioso.example", **pre})
    ok("access-control-allow-origin" not in r.headers, "otro sitio NO está permitido")

    print("\n3. Registro, sesión y datos")
    email = f"verificacion.{secrets.token_hex(4)}@correo.cl"
    clave = "Verif-" + secrets.token_urlsafe(12)
    r = c.post(f"{v1}/auth/register", json={"email": email, "password": clave})
    if not ok(r.status_code in (200, 201), f"registro (HTTP {r.status_code})", r.text[:200]):
        return 1
    cab = {"Authorization": f"Bearer {r.json()['access_token']}"}
    ok(c.post(f"{v1}/auth/login", json={"email": email, "password": clave}).status_code == 200, "inicio de sesión")
    ok(c.get(f"{v1}/expenses", headers=cab).status_code == 200, "lectura de datos con sesión")
    ok(c.get(f"{v1}/expenses").status_code == 401, "sin sesión no se leen datos (401)")

    print("\n4. La IP del cliente no se puede falsificar (límite de intentos de contraseña)")
    victima = f"victima.{secrets.token_hex(4)}@correo.cl"
    bloqueado = False
    for i in range(1, 11):
        falsa = f"198.51.100.{i}"
        r = c.post(f"{v1}/auth/login", json={"email": victima, "password": "incorrecta-123"},
                   headers={"X-Real-IP": falsa, "X-Forwarded-For": falsa, "X-Vercel-Forwarded-For": falsa})
        if r.status_code == 429:
            bloqueado = True
            break
    ok(bloqueado, "tras varios intentos fallidos se bloquea aunque cambie la IP declarada",
       "las cabeceras de IP son falsificables: cambia TRUSTED_CLIENT_IP_HEADER a otra (x-vercel-forwarded-for) "
       "o déjala vacía y vuelve a probar")

    if a.con_escaneo:
        print("\n5. Escaneo de una boleta (puede tardar si el escáner estaba dormido)")
        img = Path(__file__).with_name("boleta_sintetica.jpg")
        t0 = time.time()
        r = c.post(f"{v1}/boletas/scan", headers=cab, timeout=240,
                   files={"file": ("boleta.jpg", img.read_bytes(), "image/jpeg")}, data={"source": "file"})
        ok(r.status_code == 200, f"escaneo HTTP {r.status_code} en {time.time() - t0:.0f} s", r.text[:200])

    print("\n" + ("✅ TODO BIEN" if not fallos else f"❌ {len(fallos)} COMPROBACIÓN(ES) FALLARON"))
    return 0 if not fallos else 1


if __name__ == "__main__":
    sys.exit(main())
