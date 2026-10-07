# CONTEXTO PARA CONTINUAR ESTE PROYECTO

Documento pensado para pegarse como prompt inicial en una sesión nueva
y retomar el backend de Blynn exactamente donde quedó.

## 1. Qué es esto y qué NO es

Blynn es una app de finanzas personales para Chile (CLP, boletas
locales). Hoy el frontend (React/Vite, raíz del proyecto) estuvo
construido sobre una plataforma de terceros. Camilo quiso **eliminar toda dependencia de ella** (auth,
entidades, hosting). Esta carpeta, `backend/`, es el backend propio que
lo reemplaza: **FastAPI + Postgres (Supabase, plan gratuito) + auth
propio**.

Hay **dos sistemas separados** y no deben mezclarse:

* **`backend/` (este)**: cuentas, auth y datos de cada usuario. Vive
  dentro del proyecto `blynn`, junto al frontend.
* **`boletas-backend`**: el sistema de escaneo de boletas (OpenCV +
  Tesseract, 100% local, sin IA, no guarda imágenes). Proyecto aparte, con
  su propio despliegue. **No se toca desde aquí.** Cuando un usuario
  escanee una boleta, Blynn API (tras comprobar el login) llamará a la
  API del escáner (Etapa 4, diseño en el README).

(Error ya cometido y corregido: se había puesto la base de datos y el
auth dentro de `boletas-backend`. No repetirlo.)

## 2. Plan de 7 etapas y estado

1 base de datos y modelos ✅ · 2 auth propio ✅ · 3 CRUD de entidades ✅ ·
4 endpoint de escaneo autenticado que llama al servicio de escaneo (HECHA:
backend + frontend, probada de punta a punta con el escáner real en local; falta
probar contra el de Render; Camilo decidió NO aplicar el parche de clave de servicio al escáner)

Etapa 7 (despliegue): decidido Vercel (frontend y backend, 2 proyectos) + Supabase (base de datos). Hecho y
probado en local: límites de intentos/escaneos en la base de datos (válidos con varias instancias),
`api/index.py` + `vercel.json`, `.env.vercel.example`, `tools/verificar_despliegue.py`. NO probado: el
despliegue real en Vercel. Guía en `backend/README.md` ("Despliegue en Vercel + Supabase"). · 5 quitar el SDK de la plataforma anterior del frontend ✅ · 6
pantallas login/registro ✅ (hecha junto con la 5) · 7 despliegue (Cloud
Run + Supabase + Vercel/Netlify). Detalle,
decisiones y límites conocidos: `README.md` (incluye la tabla "de la plataforma anterior a esta API" para la Etapa 5).

Decisiones ya tomadas por Camilo: registro solo con correo + contraseña
(sin verificación por código); sin recuperación de contraseña por correo
por ahora (la quiere después si no es complicado); "Continuar con
Google" diferido; refresh token en el cuerpo de la respuesta (no
cookie); el escaneo SIEMPRE pasa por confirmación del usuario antes de
guardar un gasto; los usuarios y datos que hay hoy en la plataforma anterior son ficticios
(de prueba), así que NO se migran datos existentes. Camilo pidió ser **muy cauteloso con auth** y que todo
sea **compatible con el plan gratuito de Supabase**.

## 3. Reglas para seguir (aprendidas en las etapas 1-2)

* Toda consulta de negocio filtra por `usuario.id` del token
  (`Depends(usuario_actual)`). Es el reemplazo del filtro por dueño que
  hacía la plataforma anterior.
* Toda tabla nueva sale de una migración Alembic escrita/revisada a mano
  que **active RLS y quite permisos a `anon`/`authenticated`** (ver
  `0001`). Nunca editar una migración ya aplicada. Las migraciones no
  importan código de `app/`.
* Nombres de campo = los del frontend original (`created_date`, etc.).
  Montos enteros (`BigInteger`). CHECK en vez de ENUM.
* Esquemas de entrada con `extra="forbid"`; esquemas de salida como lista
  blanca. Errores de auth genéricos.
* Nunca loguear contraseñas, tokens ni valores de consultas SQL
  (`hide_parameters=True` en el motor).
* Mensajes, comentarios y docstrings en español.
* Pruebas: SQLite por defecto, Postgres real con `TEST_DATABASE_URL`
  (la base debe terminar en `_test`). Toda defensa de seguridad nueva
  lleva un test que falle si se rompe, y se agrega a
  `tools/verificar_defensas.py` (rompe la defensa a propósito y comprueba
  que la suite falla; hay que volver a ejecutarlo tras tocar esas líneas).
* Nunca buscar un registro solo por id: `obtener_propio(db, Modelo, id,
  usuario.id)`. Toda lista filtra por `Modelo.user_id == usuario.id`. Un
  recurso ajeno responde 404 (igual que uno inexistente).
* Entradas con tipos estrictos de `app/schemas/comunes.py` (`Monto`,
  `Texto255`, `Color`, `Fecha`, `Booleano`...), nunca `int`/`str`/`bool`
  sueltos; PATCH con `EntradaParcial` y `NO_NULOS`. Un texto o número mal
  validado termina en un 500 de la base de datos: debe ser un 422.
* Operaciones de varios pasos = UNA transacción, con `bloquear=True` en la
  fila que se modifica. Los bloqueos se prueban con
  `tests/test_bloqueos_postgres.py` (determinista); las pruebas con muchos
  hilos pueden pasar de suerte y no bastan solas.
* Todo endpoint nuevo queda cubierto solo por el barrido de
  `test_datos_seguridad.py` (falla si responde sin sesión).

## 4. Trampas ya encontradas

* SQLAlchemy 2 no reconoce `postgres://` (el código lo convierte).
* SQLite no aplica claves foráneas salvo `PRAGMA foreign_keys=ON`.
* El modo transacción del pooler de Supabase no soporta prepared
  statements (`prepare_threshold=None`); la conexión directa de Supabase
  es solo IPv6.
* El autogenerate de Alembic referenció un tipo propio sin importarlo
  (por eso las migraciones se escriben a mano).
* passlib no se usa (`bcrypt` directo). bcrypt solo lee 72 bytes.
* El `.gitignore` de la raíz ignora `.env.*` (incluye `.env.example`); por
  eso `backend/` tiene su propio `.gitignore` con `!.env.example`.
* Un Postgres embebido (`pgserver`) se apaga entre comandos en algunos
  entornos: mantenerlo vivo durante toda la corrida de pytest.
* `bool`, `int` y `float` de Pydantic aceptan `"yes"`, `1`, `"10"` en modo
  normal: usar los tipos estrictos. `Literal[True]` acepta el número `1`
  (en Python `1 == True`): para confirmaciones destructivas exigir el
  `true` exacto.
* FastAPI convierte cualquier excepción al leer el cuerpo en un 400
  genérico salvo que sea `HTTPException` (por eso el límite de tamaño
  lanza `HTTPException(413)`).
* SQLite no pliega mayúsculas fuera de ASCII (`lower('Ó')`); Postgres sí.
  Los tests de unicidad de nombres usan ASCII, y hay uno solo-Postgres
  para tildes y ñ.

## 5. Contexto del frontend (raíz del proyecto; migrado en la Etapa 5)

El frontend (React + Vite) ya NO usa la plataforma anterior. Cómo está armado y por qué:

* `src/api/` es la única puerta al backend (`http.js`, `index.js`,
  `tokenStore.js`, `errors.js`, `events.js`, `config.js`). Las pantallas
  nunca llaman a `fetch`. Sigue la tabla "de la plataforma anterior a esta API" del README.
* **Renovación de sesión**: el backend cierra la sesión si un refresh token
  se usa dos veces, así que el cliente la serializa (una por pestaña +
  Web Locks entre pestañas) y un fallo de red al renovar NO cierra la sesión.
  No tocar `http.js` sin correr las pruebas y `npm run verificar-defensas`.
* `src/lib/AuthContext.jsx`: estado de sesión (loading / authenticated /
  anonymous / error). Al iniciar/cerrar sesión limpia la caché de React
  Query (datos de otro usuario nunca deben verse). `ProtectedRoute` muestra
  "No pudimos conectar" si el servidor no responde, sin cerrar la sesión.
* El "tiempo real" de la plataforma anterior (`Expense.subscribe`) se reemplazó por
  `alCambiar("expenses", ...)`: la capa de API avisa al modificar datos.
* Desactivado por ahora: escaneo de boletas (`ESCANEO_DISPONIBLE=false` en
  `boletasScan.js`; Etapa 4), verificación por código,
  recuperación de contraseña y "Continuar con Google".
* Archivos eliminados: `Perfil.jsx` (sin ruta, duplicaba Ajustes), pantallas
  de recuperar contraseña, `OAuthConsent`, `defaultCategories.js` (la lista
  vive solo en el servidor), `app-params.js` y el cliente del SDK anterior. Se
  corrigieron dos nombres de archivo mal escritos que impedían compilar.
* El logo se dibuja en SVG (`LogoMark.jsx`) porque el original estaba en los
  servidores de la plataforma anterior; para volver al original, ver ese archivo.
* El build de producción falla si falta `VITE_API_URL` o no es https.
* La carpeta `respaldo-original/` es solo respaldo; **no subir esta versión a una rama
  conectada a la plataforma anterior** (rompería la app que corre allí). Se puede borrar tras
  el despliegue.
* Pruebas: `npm test` (176 en total; 175 pasan contra el sistema completo y 1 se omite a propósito),
  `src/api/contrato.test.js` y `src/api/contratoEscaneo.test.js` (contra un backend real, ver README raíz)
  y `npm run verificar-defensas` (18 defensas).
* Los zips que Camilo subió al inicio no incluían el código de la Etapa 1;
  se reconstruyó desde `respaldo-original/entities/*.jsonc`.

## 6. Cómo quedó la Etapa 3 y notas para las siguientes

Implementado: categorías (con `POST /categories/defaults` idempotente y
renombrado que actualiza los gastos), gastos (con `POST /expenses/bulk`),
ingresos, metas, aportes atómicos (`POST /goals/{id}/contributions`,
`DELETE /contributions/{id}`), `GET/PATCH /me` y `POST /me/reset`.
Diseño, decisiones y la tabla de traducción plataforma anterior → API: `README.md`.

**Etapa 4a (hecha)**: `POST /api/v1/boletas/scan` (`app/api/boletas.py`,
`app/services/escaneo.py`). Detalle, variables `OCR_*` y decisiones en el
README ("Integración con el escaneo"). Lo esencial: el formulario se lee
DESPUÉS de comprobar la sesión (no usar `File()`), la conexión a la BD se
suelta antes de esperar al escáner, la imagen se valida por sus bytes, y hay
cupo + un escaneo a la vez por usuario. El escáner real (Render, plan
gratuito que duerme) NO se ha probado desde aquí; sigue siendo público hasta
que se le agregue la validación de `X-Service-Key`.

La **Etapa 5** (frontend) ya aplicó todo lo anterior: los dos formatos de
error se traducen en `describirError`, los montos son > 0, las listas piden
máximo 500, la sesión se renueva de a una vez y las categorías por defecto
se piden con `POST /categories/defaults`.

Abierto: la suma de porcentajes de las metas (≤ 100 %) solo la valida el
frontend; no hay "eliminar cuenta" ni "cambiar contraseña". La foto de perfil
se QUITÓ por decisión de Camilo (todos usan el mismo avatar; migración 0003
borró la columna): no volver a agregarla sin que él lo pida.
