"""
Verifica que la suite de pruebas realmente VIGILA las defensas de seguridad.

Un test que pasa no demuestra que proteja algo. Este script rompe a
propósito, una por una, cada defensa (borra un filtro por dueño, quita un
bloqueo de fila, debilita una validación...) y comprueba que la suite de
pruebas FALLA. Si alguna rotura pasa desapercibida (la suite sigue en
verde), esa defensa no está vigilada y hay que escribir su test.

Uso (desde backend/):

    python tools/verificar_defensas.py                 # SQLite: las que no exigen Postgres
    TEST_DATABASE_URL=postgresql://.../blynn_test \\
        python tools/verificar_defensas.py             # todas (incluye bloqueos y RLS)
    python tools/verificar_defensas.py 0 10            # solo un tramo de la lista

Cada rotura se aplica al archivo, se corre la suite (se detiene en el
primer fallo) y el archivo se RESTAURA siempre, incluso si algo falla.
Sale con código distinto de 0 si alguna defensa no está vigilada o si una
línea ya no se encuentra (hay que actualizar la lista de abajo).
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
USA_POSTGRES = os.environ.get("TEST_DATABASE_URL", "").startswith(("postgres", "postgresql"))

# (descripción, archivo, texto original, texto roto, requiere Postgres)
DEFENSAS: list[tuple[str, str, str, str, bool]] = [
    # ----- Etapa 2: autenticación -----
    ("sin detección de reutilización de refresh token", "app/auth/service.py",
     "        _revocar_familia(db, fila.family_id, ahora)\n        db.commit()\n        raise RefreshTokenInvalidoError()\n\n    if fila.expires_at",
     "        raise RefreshTokenInvalidoError()\n\n    if fila.expires_at", False),
    ("sin verificar el emisor (iss) del JWT", "app/auth/tokens.py", "            issuer=settings.JWT_ISSUER,\n", "", False),
    ("acepta cualquier tipo de token (sin typ=access)", "app/auth/tokens.py", 'if payload.get("typ") != "access":', "if False:", False),
    ("sin cálculo señuelo (tiempo de correos inexistentes)", "app/auth/service.py",
     "        gastar_tiempo_de_verificacion(password, rounds=settings.BCRYPT_ROUNDS)\n", "        pass\n", False),
    ("esquemas de auth aceptan campos extra", "app/auth/schemas.py",
     'model_config = ConfigDict(extra="forbid")\n\n    @field_validator("email"', 'model_config = ConfigDict(extra="ignore")\n\n    @field_validator("email"', False),
    ("cuenta desactivada puede iniciar sesión", "app/auth/service.py",
     "    if not usuario.is_active:\n        raise CredencialesInvalidasError()\n    return usuario", "    return usuario", False),
    ("usuario desactivado sigue con token válido", "app/auth/dependencies.py", "if usuario is None or not usuario.is_active:", "if usuario is None:", False),
    ("sin normalización Unicode NFKC", "app/auth/passwords.py", 'return unicodedata.normalize("NFKC", password)', "return password", False),
    ("sin límite de 72 bytes (trunca en silencio)", "app/auth/passwords.py",
     "    if len(datos) > MAX_BYTES_BCRYPT:\n        return False", "    datos = datos[:72]\n    if False:\n        return False", False),
    ("sin bloqueo de fila en refresh (carrera)", "app/auth/service.py", "        .with_for_update()\n", "", True),
    ("el correo no se normaliza a minúsculas", "app/auth/service.py", "    return email.strip().lower()", "    return email.strip()", False),
    ("los parámetros SQL aparecen en los errores", "app/db/session.py", '"hide_parameters": True,\n        "pool_pre_ping"', '"pool_pre_ping"', False),
    ("migración sin Row Level Security", "migrations/versions/0001_modelos_iniciales.py",
     "    op.execute(f'ALTER TABLE \"{tabla}\" ENABLE ROW LEVEL SECURITY')\n", "", True),
    ("migración no quita permisos a anon", "migrations/versions/0001_modelos_iniciales.py", 'REVOKE ALL ON TABLE "{tabla}" FROM anon;', "SELECT 1;", True),
    ("respuestas de token cacheables", "app/api/auth_routes.py", 'response.headers["Cache-Control"] = "no-store"', "pass", False),
    ("el límite de intentos no bloquea", "app/api/auth_routes.py", "        exigir_disponible(db, limitadores.fallos_por_cuenta, clave_cuenta)\n", "", False),
    ("logout no revoca nada", "app/auth/service.py",
     "        _revocar_familia(db, fila.family_id, ahora_utc())\n        db.commit()\n\n\ndef cerrar_todas", "        pass\n\n\ndef cerrar_todas", False),
    # ----- Etapa 3: datos del usuario -----
    ("IDOR: obtener_propio sin filtro de dueño", "app/services/acceso.py", "modelo.id == recurso_id, modelo.user_id == usuario_id)", "modelo.id == recurso_id)", False),
    ("listado de gastos sin filtro de dueño", "app/api/gastos.py", "select(Expense).where(Expense.user_id == usuario.id)", "select(Expense)", False),
    ("listado de ingresos sin filtro de dueño", "app/api/ingresos.py", "select(Income).where(Income.user_id == usuario.id)", "select(Income)", False),
    ("listado de categorías sin filtro de dueño", "app/api/categorias.py", "select(Category).where(Category.user_id == usuario.id)", "select(Category)", False),
    ("listado de metas sin filtro de dueño", "app/api/metas.py", "select(Goal).where(Goal.user_id == usuario.id)", "select(Goal)", False),
    ("listado de aportes sin filtro de dueño", "app/api/metas.py", "select(Contribution).where(Contribution.user_id == usuario.id)", "select(Contribution)", False),
    ("las entradas aceptan campos extra (user_id, id...)", "app/schemas/comunes.py",
     'class EntradaEstricta(BaseModel):\n    """Base de todo lo que llega del cliente: rechaza campos desconocidos."""\n\n    model_config = ConfigDict(extra="forbid")',
     'class EntradaEstricta(BaseModel):\n    """x"""\n\n    model_config = ConfigDict(extra="ignore")', False),
    ("renombrar categoría toca gastos de otros usuarios", "app/services/categorias.py",
     ".where(Expense.user_id == usuario_id, Expense.category == nombre_anterior)", ".where(Expense.category == nombre_anterior)", False),
    ("aporte sin bloqueo de fila (pérdida de aportes)", "app/services/metas.py",
     "meta = obtener_propio(db, Goal, meta_id, usuario_id, bloquear=True)", "meta = obtener_propio(db, Goal, meta_id, usuario_id)", True),
    ("deshacer sin bloqueo de la meta", "app/services/metas.py",
     "meta = obtener_propio(db, Goal, aporte.goal_id, usuario_id, bloquear=True)", "meta = obtener_propio(db, Goal, aporte.goal_id, usuario_id)", True),
    ("deshacer sin releer el aporte (doble descuento)", "app/services/metas.py",
     "    aporte = obtener_propio(db, Contribution, aporte_id, usuario_id)\n\n    meta.current_amount = max", "    meta.current_amount = max", True),
    ("reinicio confirma a mitad (no atómico)", "app/services/datos_usuario.py",
     "        agregar_categorias_faltantes(db, uid)\n        usuario.onboarded", "        db.commit()\n        agregar_categorias_faltantes(db, uid)\n        usuario.onboarded", False),
    ("sin límite de tamaño de cuerpo", "app/main.py",
     "app.add_middleware(\n    LimitarTamanoCuerpo,\n    max_bytes=settings.MAX_REQUEST_BODY_BYTES,\n    # Solo la ruta de escaneo puede recibir una imagen (+ margen del formulario).\n    limites_por_ruta={(\"POST\", RUTA_ESCANEO): settings.OCR_MAX_IMAGE_BYTES + 64 * 1024},\n)", "pass", False),
    ("reinicio acepta cualquier confirm", "app/schemas/perfil.py", "        if v is not True:", "        if False:", False),
    ("color sin patrón #rrggbb", "app/schemas/comunes.py", 'StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$"),', "StringConstraints(),", False),
    ("montos no estrictos (acepta '3190', true)", "app/schemas/comunes.py", "Field(strict=True, ", "Field(", False),
    ("acepta caracteres de control / NUL", "app/schemas/comunes.py", "    if any((ord(c) < 32 and c not in", "    return v\n    if any((ord(c) < 32 and c not in", False),
    ("orden por cualquier campo", "app/api/comun.py", "    if campo not in permitidos:", "    if False:", False),
    ("categorías por defecto no idempotentes", "app/services/categorias.py",
     "existentes = {n.lower() for n in db.scalars(select(Category.name).where(Category.user_id == usuario_id))}", "existentes = set()", False),
    ("aporte sin tope de monto", "app/services/metas.py", "    if nuevo_total > MAX_MONTO:", "    if False:", False),
    ("deshacer puede dejar la meta bajo cero", "app/services/metas.py", "max(0, meta.current_amount - aporte.amount)", "meta.current_amount - aporte.amount", False),
    ("PATCH permite recurrente activo sin recurrente", "app/api/gastos.py", "    if gasto.recurring_active and not gasto.is_recurring:", "    if False:", False),
    ("PATCH de meta sin validar el modo", "app/api/metas.py",
     "        _validar_modo(meta.contribution_mode, meta.contribution_percent, meta.contribution_amount)", "        pass", False),
    ("un endpoint de datos sin autenticación", "app/api/gastos.py", '@router.get("/{gasto_id}", response_model=GastoOut)',
     '@router.get("/publico-por-error")\ndef _oops(db: Session = Depends(get_db)):\n    return []\n\n\n@router.get("/{gasto_id}", response_model=GastoOut)', False),
    ("preferencias se pisan en vez de combinarse", "app/api/perfil.py",
     "usuario.preferences = {**(usuario.preferences or {}), **preferencias}", "usuario.preferences = preferencias", False),
    ("PATCH acepta null en campos obligatorios", "app/schemas/comunes.py", "for campo in self.model_fields_set & self.NO_NULOS:", "for campo in ():", False),
    # ----- Etapa 4: escaneo de boletas -----
    ("el escaneo acepta cualquier archivo (no revisa los bytes)", "app/services/escaneo.py",
     "    tipo = detectar_tipo_imagen(datos)\n    if tipo is None:", '    tipo = detectar_tipo_imagen(datos) or ("image/jpeg", "jpg")\n    if tipo is None:', False),
    ("un RIFF que no es WEBP (audio) pasa por imagen", "app/services/escaneo.py",
     'if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":', 'if datos[:4] == b"RIFF":', False),
    ("el escaneo no limita el tamaño de la imagen", "app/services/escaneo.py", "    if len(datos) > maximo:", "    if False:", False),
    ("la ruta de escaneo no tiene tope de cuerpo", "app/api/limite_cuerpo.py",
     'limite = self.limites_por_ruta.get((scope["method"], scope["path"]), self.max_bytes)',
     'limite = 10**12 if (scope["method"], scope["path"]) in self.limites_por_ruta else self.max_bytes', False),
    ("sin cupo de escaneos por usuario", "app/services/escaneo.py", "    if espera:\n        db.rollback()  # el turno nunca llegó a confirmarse\n        raise DemasiadosEscaneos(espera)", "    if False:\n        db.rollback()  # el turno nunca llegó a confirmarse\n        raise DemasiadosEscaneos(espera)", False),
    ("varios escaneos a la vez del mismo usuario", "app/services/escaneo.py", "    except IntegrityError:\n        db.rollback()\n        raise EscaneoEnCurso() from None", "    except IntegrityError:\n        db.rollback()\n        pass", False),
    ("el escaneo en curso no se libera al fallar", "app/api/boletas.py", "    finally:\n        liberar_escaneo(db, user_id)  # abre una conexión corta, ya terminada la espera", "    finally:\n        pass", False),
    ("la conexión a la base queda tomada durante el escaneo", "app/api/boletas.py",
     "    db.close()  # libera la conexión mientras se espera al escáner (ver arriba)", "    db.query(User).first()", False),
    ("se lee el cuerpo (hasta 10 MB) antes de comprobar la sesión", "app/api/boletas.py",
     "async def escanear_boleta(\n    request: Request,\n    usuario: User = Depends(usuario_actual),",
     'async def escanear_boleta(\n    request: Request,\n    _cuerpo: bytes = __import__("fastapi").Body(default=None),\n    usuario: User = Depends(usuario_actual),', False),
    ("el cliente del escáner sigue redirecciones (y la clave viaja)", "app/api/boletas.py", "follow_redirects=False,", "follow_redirects=True,", False),
    ("no se envía la clave de servicio al escáner", "app/services/escaneo.py",
     "        cabeceras[CABECERA_CLAVE] = clave", "        pass", False),
    ("el cuerpo de un error del escáner llega al usuario", "app/services/escaneo.py",
     '    logger.error("El servicio de escaneo respondió %s", codigo)\n    raise EscaneoFallido()',
     '    logger.error("El servicio de escaneo respondió %s", codigo)\n    raise EscaneoFallido(respuesta.text)', False),
    ("el escaneo no tiene tiempo máximo total", "app/services/escaneo.py",
     "async with asyncio.timeout(settings.OCR_SERVICE_TIMEOUT_SECONDS):", "async with asyncio.timeout(None):", False),
    ("el resultado del escaneo puede quedar en caché", "app/api/boletas.py",
     'return JSONResponse(content=resultado, headers={"Cache-Control": "no-store"})', "return JSONResponse(content=resultado)", False),
    ("producción acepta http hacia el escáner", "app/config.py",
     '        if url_escaner and not url_escaner.lower().startswith("https://"):', "        if False:", False),
    ("producción acepta una clave de servicio corta", "app/config.py",
     "        if clave_escaner and len(clave_escaner) < 24:", "        if False:", False),
    ("la clave de servicio con espacios o salto de línea no coincide", "app/services/escaneo.py",
     '    clave = settings.OCR_SERVICE_KEY.get_secret_value().strip() if settings.OCR_SERVICE_KEY is not None else ""',
     '    clave = settings.OCR_SERVICE_KEY.get_secret_value() if settings.OCR_SERVICE_KEY is not None else ""', False),
    ("una clave de servicio vacía se envía como cabecera vacía", "app/services/escaneo.py",
     "    if clave:\n        cabeceras[CABECERA_CLAVE] = clave", "    if True:\n        cabeceras[CABECERA_CLAVE] = clave", False),
    ("la respuesta del escáner se reenvía sin filtrar (campos internos)", "app/services/escaneo.py",
     '            return EscaneoOut.model_validate(cuerpo).model_dump(mode="json")', "            return cuerpo", False),
    ("un contrato roto del escáner no se detecta", "app/services/escaneo.py",
     "        except ValidationError as exc:", "        except ZeroDivisionError as exc:", False),
    ("el log del contrato roto incluye los valores de la boleta", "app/services/escaneo.py",
     '            logger.error("La respuesta del escáner no cumple el contrato (campos: %s)", campos)',
     '            logger.error("La respuesta del escáner no cumple el contrato: %s", exc.errors())', False),
    ("los textos del OCR conservan caracteres de control", "app/schemas/boletas.py",
     '        limpio = "".join(c for c in valor if c == " " or c.isprintable()).strip()', "        limpio = valor.strip()", False),
    ("los números del OCR no se acotan (NaN, negativos, absurdos)", "app/schemas/boletas.py",
     "        if not math.isfinite(numero) or numero < minimo or numero > maximo:", "        if False:", False),
    ("fechas del OCR fuera de rango se aceptan", "app/schemas/boletas.py",
     "    return fecha.isoformat() if 2000 <= fecha.year <= 2100 else None", "    return fecha.isoformat()", False),
    ("lista de productos sin tope", "app/schemas/boletas.py",
     "    productos: list[ProductoEscaneado] = Field(default_factory=list, max_length=200)",
     "    productos: list[ProductoEscaneado] = Field(default_factory=list)", False),
    # ----- Etapa 7: límites compartidos entre instancias -----
    ("un fallo de login no queda registrado si la petición falla", "app/auth/rate_limit.py",
     "        db.commit()\n\n    def reiniciar(self, db: Session, clave: str) -> None:", "        db.flush()\n\n    def reiniciar(self, db: Session, clave: str) -> None:", False),
    ("el correo y la IP se guardan en claro en la base", "app/auth/rate_limit.py",
     '        return hashlib.sha256(f"{self.nombre}|{clave}".encode()).hexdigest()', "        return clave[:64]", False),
    ("se confía en una cabecera de IP sin que esté configurada", "app/auth/rate_limit.py",
     "    nombre = settings.TRUSTED_CLIENT_IP_HEADER if settings else None", '    nombre = "x-forwarded-for"', False),
    ("un turno de escaneo abandonado bloquea al usuario para siempre", "app/services/escaneo.py",
     "            EscaneoActivo.iniciado_ts < ahora - settings.OCR_SERVICE_TIMEOUT_SECONDS - _MARGEN_TURNO_SEGUNDOS,",
     "            EscaneoActivo.iniciado_ts < 0,", False),
    ("los intentos vencidos no se limpian de la tabla", "app/auth/rate_limit.py",
     "                IntentoLimitado.clave == huella,\n                IntentoLimitado.ts <= corte,", "                IntentoLimitado.clave == huella,\n                IntentoLimitado.ts <= -1,", False),
]


def main() -> int:
    ini = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(DEFENSAS)
    sin_vigilar, no_aplicables, omitidas, vigiladas = [], [], 0, 0
    for nombre, archivo, original, roto, solo_pg in DEFENSAS[ini:fin]:
        if solo_pg and not USA_POSTGRES:
            omitidas += 1
            print(f"  omitida (requiere Postgres)  {nombre}")
            continue
        ruta = RAIZ / archivo
        texto = ruta.read_text(encoding="utf-8")
        if original not in texto:
            no_aplicables.append(nombre)
            print(f"✘ NO SE PUDO APLICAR          {nombre}  ({archivo})")
            continue
        ruta.write_text(texto.replace(original, roto, 1), encoding="utf-8")
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"],
                cwd=RAIZ, capture_output=True, text=True, timeout=900,
            )
        finally:
            ruta.write_text(texto, encoding="utf-8")  # SIEMPRE se restaura
        if r.returncode != 0:
            vigiladas += 1
            print(f"✔ vigilada                    {nombre}")
        else:
            sin_vigilar.append(nombre)
            print(f"✘ ¡¡ SIN VIGILAR !!           {nombre}")
    print(f"\nvigiladas: {vigiladas} · sin vigilar: {len(sin_vigilar)} · no aplicables: {len(no_aplicables)} · omitidas: {omitidas}")
    return 1 if (sin_vigilar or no_aplicables) else 0


if __name__ == "__main__":
    raise SystemExit(main())
