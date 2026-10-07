# Blynn API — backend general de Blynn

Backend propio de Blynn (finanzas personales chilenas), que reemplaza a
la plataforma anterior: base de datos, cuentas de usuario, autenticación y, a partir de
la Etapa 3, los datos de cada usuario (gastos, ingresos, categorías, metas).

## Arquitectura: dos sistemas separados

```
                 ┌──────────────────────────┐
  Frontend  ───▶ │  Blynn API  (esta carpeta)│ ───▶  Postgres (Supabase)
  React/Vite     │  FastAPI · auth · datos   │
  (raíz del      └────────────┬─────────────┘
   proyecto)                  │  solo si el usuario está autenticado
                              ▼
                 ┌──────────────────────────┐
                 │  Servicio de escaneo      │
                 │  (boletas-backend)        │  OpenCV + Tesseract, 100% local,
                 │  proyecto APARTE          │  no guarda imágenes
                 └──────────────────────────┘
```

* **Esta carpeta (`backend/`)** es el backend general. Vive dentro del
  proyecto de Blynn, junto al frontend (que está en la raíz y no se toca).
* **`boletas-backend`** es el sistema de escaneo de boletas. Es un
  proyecto y un servicio **aparte**, con sus propias dependencias
  (OpenCV, Tesseract) y su propio despliegue. Nada de su código está aquí.
* Cuando un usuario quiera escanear una boleta, el frontend le enviará la
  imagen a **Blynn API**, y Blynn API (tras comprobar el login) llamará
  a la API del servicio de escaneo. Ver "Integración con el escaneo".

## Estado de las etapas

| # | Etapa | Estado |
|---|---|---|
| 1 | Base de datos y modelos (Postgres + SQLAlchemy) | ✅ |
| 2 | Autenticación propia (bcrypt + JWT + refresh tokens) | ✅ |
| 3 | CRUD de Gastos, Ingresos, Categorías, Metas, Aportes y perfil | ✅ |
| 4 | Escaneo: endpoint autenticado que llama al servicio de escaneo | ✅ (probado de punta a punta con el escáner real corriendo en local; falta probarlo contra el de Render) |
| 5 | Quitar el SDK de la plataforma anterior del frontend y usar esta API | ✅ |
| 6 | Pantallas de login/registro conectadas | ✅ (se hizo junto con la 5: sin el login no se puede quitar el SDK) |
| 7 | Despliegue (Cloud Run + Supabase + Vercel/Netlify) | pendiente |

Regla del plan: **no se le quita la plataforma anterior al frontend hasta que este
backend funcione de punta a punta.** (Cumplida: el frontend ya no depende de
la plataforma anterior. El escaneo de boletas queda desactivado hasta la Etapa 4.)

## Puesta en marcha (desarrollo)

Requiere Python 3.12. Desde esta carpeta (`backend/`):

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env              # Windows: copy .env.example .env
# Edita .env: JWT_SECRET_KEY (obligatoria) y DATABASE_URL. Para generar la clave:
python -c "import secrets; print(secrets.token_urlsafe(64))"

alembic upgrade head              # crea las tablas en la base de datos
uvicorn app.main:app --reload --port 8000
```

Documentación interactiva: http://localhost:8000/docs

Ejemplo de registro y de uso del token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"ana@correo.cl","password":"Tr3s-Tristes-Tigres","full_name":"Ana"}'

curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer <access_token>"
```

> El servidor **no arranca** sin `JWT_SECRET_KEY` de al menos 32
> caracteres, y explica por qué. Es a propósito.

## Base de datos y Supabase

Se usa **solo el Postgres** de Supabase: toda la lógica de auth y de
negocio es de este backend (no se usa Supabase Auth, ni su Data API, ni
sus claves `anon`/`service_role`). Si algún día se cambia de proveedor,
basta con cambiar `DATABASE_URL`.

**Qué cadena de conexión usar** (panel de Supabase → *Connect*):

| Para qué | Cadena | Por qué |
|---|---|---|
| Correr migraciones (`alembic upgrade head`) | *Session pooler* (puerto 5432 del host `…pooler.supabase.com`) | Soporta todo Postgres y funciona por IPv4 |
| La aplicación en producción | *Transaction pooler* (puerto 6543) | Pensado para servidores que abren muchas conexiones cortas |

La conexión *directa* de Supabase usa IPv6; si tu hosting es solo IPv4
(muchos lo son), usa los *poolers*. Se puede pegar la cadena tal cual
(`postgresql://` o `postgres://`): el código la convierte al formato de
SQLAlchemy, agrega `sslmode=require` y desactiva las *prepared
statements* (el modo transacción no las soporta). Si la contraseña tiene
caracteres especiales (`@ # / : ? %`) hay que codificarlos en la URL
(`@` → `%40`). El usuario del pooler tiene la forma
`postgres.<id-del-proyecto>`.

**Plan gratuito** (según la documentación y guías de precios consultadas
en septiembre 2026; verifica en supabase.com/pricing antes de decidir):
500 MB de base de datos, 2 proyectos activos, y **el proyecto se pausa
tras 1 semana sin actividad** (hay que reactivarlo a mano desde el
panel; mientras está pausado la app no responde). Sirve para desarrollo
y para una etapa temprana; con usuarios reales conviene planificar el
salto de plan o un ping periódico.

**Seguridad específica de Supabase — importante.** Supabase expone por
HTTP las tablas del esquema `public` a quien tenga la clave pública
`anon`, salvo que tengan *Row Level Security* (RLS). Como este backend se
conecta directo a Postgres y no usa ese acceso, las migraciones dejan
**todas las tablas con RLS activado y sin políticas**, y quitan los
permisos a los roles `anon` y `authenticated`. Un test
(`test_migrations.py`) verifica ambas cosas en Postgres real. Como
defensa extra, en la configuración del proyecto de Supabase (sección
*Data API*) se puede **desactivar el Data API por completo**, ya que no
se usa. Regla: toda tabla nueva debe salir de una migración que active
RLS igual que las actuales.

**Comprobar que los tests siguen vigilando las defensas.** Un test que
pasa no prueba que proteja: `python tools/verificar_defensas.py` rompe a
propósito, una por una, 43 defensas del código (filtros por dueño, bloqueos
de fila, validaciones, RLS…) y comprueba que la suite falla cada vez. Con
SQLite verifica las que no dependen de Postgres; con `TEST_DATABASE_URL`
apuntando a Postgres, todas. Si cambias esas líneas de código, la
herramienta avisa "NO SE PUDO APLICAR" y hay que actualizar su lista.

**Migraciones** (Alembic). Nunca se edita una migración ya aplicada: cada
cambio de esquema es un archivo nuevo en `migrations/versions/`. Flujo:

```bash
# 1. cambiar el modelo en app/db/models.py
# 2. generar el borrador y REVISARLO A MANO (autogenerate no es perfecto)
alembic revision --autogenerate -m "descripcion corta"
# 3. si crea una tabla, agregar RLS como en 0001/0002, y aplicar
alembic upgrade head
alembic check        # debe decir "No new upgrade operations detected"
```

Las migraciones no importan código de `app/` (un test lo verifica): así
siguen funcionando aunque el código cambie después.

**Plan B sin conexión directa.** Si tu red no alcanza la base de datos
(p. ej. la conexión directa de Supabase es solo IPv6), genera el SQL
completo y pégalo en el *SQL Editor* de Supabase:

```bash
alembic upgrade head --sql > esquema.sql
```

Está verificado: aplicado a una base vacía deja exactamente el mismo
esquema que los modelos (`alembic check` sin diferencias), con RLS en las
7 tablas y la versión `0002` registrada, así que las migraciones futuras
siguen funcionando con normalidad.

## Modelo de datos

Mismos nombres de campo que las entidades de la plataforma anterior (`created_date`,
`payment_method`, `target_amount`…), para que el cambio en el frontend
sea de origen de datos y no un rediseño. Puntos a saber:

* Ids **UUID** (no adivinables). Montos en pesos como **enteros**
  (`BigInteger`): el frontend solo produce enteros.
* Valores permitidos (métodos de pago, tipos de ingreso, etc.) con
  `CHECK` en la base de datos, no tipos ENUM.
* Categorías: nombre único por usuario **sin distinguir mayúsculas**
  (los gastos referencian la categoría por nombre).
* `Contribution` (aporte) tiene una clave foránea **compuesta**
  `(goal_id, user_id)`: la base de datos impide que un aporte cuelgue de
  la meta de otro usuario, aunque un endpoint futuro tuviera un
  descuido. Borrar una meta borra sus aportes; borrar un usuario borra
  todo lo suyo.
* No existe entidad "Presupuesto": vive en `Category.budget` y
  `User.monthly_budget`, igual que en la plataforma anterior.
* Fechas siempre con zona horaria (UTC).

## Autenticación

| Endpoint | Qué hace |
|---|---|
| `POST /api/v1/auth/register` | Crea la cuenta (correo + contraseña + nombre opcional) e inicia sesión. `201`, `409` si el correo existe, `422` si la contraseña no cumple la política |
| `POST /api/v1/auth/login` | Inicia sesión. `401` con mensaje genérico, `429` si hay demasiados intentos |
| `POST /api/v1/auth/refresh` | Cambia un refresh token por un par nuevo (rotación) |
| `POST /api/v1/auth/logout` | Cierra la sesión de ese refresh token (`204` siempre) |
| `POST /api/v1/auth/logout-all` | Cierra todas las sesiones del usuario (requiere access token) |
| `GET /api/v1/auth/me` | Datos del usuario autenticado |
| `GET /health`, `GET /health/ready` | Proceso vivo / base de datos respondiendo |

Respuesta de register/login: `access_token`, `refresh_token`,
`token_type: "bearer"`, `expires_in` (segundos) y `user`.

**Cómo funciona la sesión**

* **Access token**: JWT firmado (HS256), dura **15 minutos**. Se envía en
  cada petición: `Authorization: Bearer <token>`.
* **Refresh token**: texto aleatorio opaco (no JWT), dura 30 días. En la
  base de datos solo se guarda su **huella SHA-256**. Cada vez que se usa
  se cambia por uno nuevo (**rotación**). Si alguien presenta un refresh
  token que ya se usó o se revocó, se asume robo y se **revoca la sesión
  completa** (esa familia de tokens); otras sesiones del mismo usuario
  (otro dispositivo) no se tocan.
* Una cuenta borrada o desactivada deja de funcionar **de inmediato**: en
  cada petición se consulta el usuario, no solo se valida el token.

**Decisiones de seguridad** (todas tienen un test que falla si se rompen):

* Contraseñas con **bcrypt** (costo 12). Largo mínimo 8, máximo 72 bytes
  (límite real de bcrypt: se rechaza en vez de truncar en silencio),
  lista corta de contraseñas comunes, no igual al correo. Se normaliza
  Unicode (NFKC) antes de hashear, para que una contraseña con `ñ` o
  tilde funcione igual escrita desde cualquier teléfono o sistema.
* **Sin enumeración por login**: contraseña incorrecta, correo
  inexistente y cuenta desactivada dan la *misma* respuesta, y con un
  correo inexistente se hace igual un cálculo bcrypt "señuelo" para que
  tarde lo mismo.
* JWT: algoritmo fijado en el servidor (rechaza `alg: none` y otros
  algoritmos), exige `exp/iat/sub/iss/jti`, verifica emisor y que sea de
  tipo `access` (un refresh token no sirve como access token).
* Entradas con `extra="forbid"`: no se puede colar `role: "admin"` al
  registrarse. Las salidas son listas blancas: `password_hash` no puede
  filtrarse aunque se agreguen columnas.
* Límite de intentos: 5 fallos por cuenta+IP, 30 por IP, 10 registros
  por IP, en ventanas de 15 min → `429` con `Retry-After`.
* Las respuestas con tokens llevan `Cache-Control: no-store`.
* Los errores de base de datos **no incluyen los valores** de la consulta
  (`hide_parameters`), así que correos, hashes y huellas no llegan a los
  logs.
* Arranque seguro: sin `JWT_SECRET_KEY` de al menos 32 caracteres el
  servidor no levanta; en producción además exige `DATABASE_URL` y CORS
  sin `*`.

**Proteger un endpoint nuevo:**

```python
from app.auth.dependencies import usuario_actual
from app.services.acceso import obtener_propio

@router.get("/gastos")
def listar(usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    # REGLA: toda consulta filtra por el usuario del token. Olvidarlo
    # filtraría datos entre usuarios (la plataforma anterior hacía este filtro por ti).
    return db.scalars(select(Expense).where(Expense.user_id == usuario.id)).all()

@router.get("/gastos/{gasto_id}")
def obtener(gasto_id: uuid.UUID, usuario: User = Depends(usuario_actual), db: Session = Depends(get_db)):
    # Para un registro por id, SIEMPRE `obtener_propio` (exige id Y dueño;
    # si es de otro usuario responde 404, igual que si no existiera).
    return obtener_propio(db, Expense, gasto_id, usuario.id)
```

`tests/test_datos_seguridad.py` recorre todos los endpoints y falla si
alguno responde sin sesión, así que un endpoint nuevo sin protección no
pasa desapercibido.

## API de datos (Etapa 3)

Todos estos endpoints exigen `Authorization: Bearer <access_token>` y
**solo ven y tocan los datos del usuario del token**. Un recurso ajeno
responde `404` exactamente igual que uno que no existe (no se revela qué
ids existen).

| Recurso | Endpoints |
|---|---|
| Categorías | `GET/POST /categories` · `POST /categories/defaults` · `GET/PATCH/DELETE /categories/{id}` |
| Gastos | `GET/POST /expenses` · `POST /expenses/bulk` · `GET/PATCH/DELETE /expenses/{id}` |
| Ingresos | `GET/POST /incomes` · `GET/PATCH/DELETE /incomes/{id}` |
| Metas | `GET/POST /goals` · `GET/PATCH/DELETE /goals/{id}` · `POST /goals/{id}/contributions` |
| Aportes | `GET /contributions` · `DELETE /contributions/{id}` (deshacer) |
| Perfil | `GET/PATCH /me` · `POST /me/reset` |

(todos bajo `/api/v1`; documentación interactiva en `/docs`)

**Convenciones**

* **Listados**: `sort` (`date`, `-date`, `amount`…; solo campos permitidos),
  `limit` (por defecto 500, máximo 1000), `offset`. Gastos e ingresos
  filtran además por `date_from` / `date_to` (`YYYY-MM-DD`); gastos por
  `category`, `is_recurring` y `recurring_active`; ingresos por `type`;
  aportes por `goal_id`. Para un mes concreto conviene usar el rango de
  fechas en vez de traer todo.
* **PATCH parcial**: solo se cambia lo enviado. `null` borra un campo
  opcional (`description`, `color`, `deadline`…); en uno obligatorio es
  `422`.
* **Errores**: `422` de validación trae `detail` como lista
  (`[{loc, msg, type}]`); los errores de negocio (`404`, `409`, `422` de
  regla) traen `detail` como texto. El frontend debe manejar ambos.
* **Formatos**: ids UUID; fechas `YYYY-MM-DD` (entre 2000 y 2100);
  `created_date`/`updated_date` en ISO con zona horaria UTC.
* **Validación estricta** (`422`, nunca un 500): montos enteros mayores
  que 0 y hasta 10¹² (no acepta `"3190"`, `12.5` ni `true`); textos con el
  largo de la columna, sin caracteres de control ni bytes nulos; colores
  solo `#rrggbb`; **campos desconocidos se
  rechazan** (no se puede enviar `user_id`, `id`, `created_date`…).
* Cuerpo de petición máximo **1 MiB** (`413`).

**Decisiones de diseño**

* `POST /categories/defaults` es **idempotente**: crea solo las que falten
  (sin distinguir mayúsculas) y se puede llamar desde varias pestañas a la
  vez sin duplicar ni fallar. Reemplaza al `bulkCreate` del frontend.
* **Renombrar una categoría actualiza sus gastos** (los gastos la
  referencian por nombre). En la plataforma anterior quedaban huérfanos. Solo afecta a los
  gastos del mismo usuario.
* **Aportes atómicos**: `POST /goals/{id}/contributions` crea el aporte y
  suma el monto a la meta en una sola transacción, con la fila de la meta
  bloqueada (diez aportes simultáneos no pierden ninguno). `DELETE
  /contributions/{id}` lo deshace y devuelve la meta (nunca bajo cero;
  deshacer dos veces da `404` y no descuenta dos veces). El cliente envía
  `date` y, si corresponde, `next_contribution_date` (la calcula él según
  la frecuencia); `goal_title` y `auto_approved_count` los lleva el
  servidor (un aporte `aprobado` suma 1).
* `POST /me/reset` (Ajustes → reiniciar) **borra datos y recrea las
  categorías por defecto en una sola transacción**, exige `{"confirm":
  true}` exacto, y conserva cuenta, contraseña, nombre y preferencias.
* `PATCH /me` solo acepta `full_name`, `onboarded`,
  `monthly_budget` y `preferences` (hoy `{notifications: bool}`). `email`,
  `role`, `is_active` y la contraseña no se pueden cambiar por ahí.

**Guía para el frontend: de la plataforma anterior a esta API** (aplicada en la Etapa 5)

| Antes (plataforma anterior) | Nueva API |
|---|---|
| `Category.list()` | `GET /categories` |
| `Category.bulkCreate(DEFAULT_CATEGORIES)` | `POST /categories/defaults` |
| `Expense.list("-date", 300)` | `GET /expenses?sort=-date&limit=300` |
| `Expense.bulkCreate(toCreate)` (cobros recurrentes) | `POST /expenses/bulk` (máx. 50) |
| `Income.list("-date", 100)` | `GET /incomes?sort=-date&limit=100` |
| `Goal.list("-created_date")` / `Goal.get(id)` | `GET /goals?sort=-created_date` / `GET /goals/{id}` |
| `Contribution.create` + `Goal.update` (`goalEngine.js`) | `POST /goals/{id}/contributions` |
| `Contribution.delete` + `Goal.get` + `Goal.update` (deshacer) | `DELETE /contributions/{id}` |
| `Contribution.deleteMany` + `Goal.delete` (`Metas.jsx`) | `DELETE /goals/{id}` |
| `deleteMany` ×4 + `bulkCreate` + `updateMe` (`Ajustes.jsx`) | `POST /me/reset` |
| `auth.me()` / `auth.updateMe(...)` | `GET /me` / `PATCH /me` |

Cosas que cambian y el frontend debe considerar: los montos deben ser
**mayores que 0** (hoy un `0` pasaba); `auto_approved_count` ya no se
envía en `Goal` (lo lleva el servidor); los ids son UUID; y `GET` de
listas sin `limit` devuelve como máximo 500 (Estadísticas pide 500: usar
rango de fechas si un usuario tiene más).

## Integración con el escaneo (Etapa 4)

**Estado.** ✅ Backend (4a) y frontend (4b) implementados. Las pruebas
unitarias usan un escáner simulado, y además se probó de punta a punta con el
**escáner real** (Tesseract + español) corriendo en local: cliente del
frontend → este backend (Postgres real) → escáner con su clave de servicio →
gasto guardado. **No se ha probado contra el escáner desplegado en Render**
(ni el tiempo real de un despertar en frío), ni el frontend en un navegador o
celular real.

**Dos sistemas.** Este backend NO hace OCR: valida y reenvía. El OCR vive en
`boletas-backend` (aparte, en Render), que nunca guarda la imagen.

```
POST /api/v1/boletas/scan      (exige sesión)
  multipart: file    jpg / png / webp, máx. 10 MB
             source  "camera" | "file"   (opcional, por defecto "file"; el frontend web
                                          solo envía "file", "camera" queda para una app móvil)
  200  la lectura del escáner filtrada por una lista blanca
       (app/schemas/boletas.py; Cache-Control: no-store)
```

Lo que hace, en orden: (1) comprueba la sesión **antes de leer el cuerpo**;
(2) suelta la conexión a la base de datos; (3) comprueba que el escaneo esté
configurado y que el usuario tenga cupo y no tenga otro escaneo en curso;
(4) lee y valida la imagen por sus **bytes reales** (el tipo y el nombre que
declare el cliente no cuentan) y su tamaño; (5) la reenvía con un nombre
fijo (`boleta.jpg`/`.png`/`.webp`: nunca el del cliente) y la clave de
servicio; (6) traduce la respuesta.

| Situación | Respuesta de Blynn API |
|---|---|
| Sin sesión / token falso | `401` (y no se lee el cuerpo) |
| Falta `file`, está vacío o `source` inválido | `422` |
| No es JPG/PNG/WEBP (por sus bytes) | `415` |
| Imagen o cuerpo sobre el máximo | `413` |
| Cupo agotado, o ya hay un escaneo en curso | `429` + `Retry-After` |
| `OCR_SERVICE_URL` sin configurar, escáner caído o error propio del escáner (p. ej. Tesseract) | `503` |
| El escáner no respondió dentro de `OCR_SERVICE_TIMEOUT_SECONDS` | `504` |
| El escáner respondió algo inesperado (4xx/5xx, no es JSON, redirección) o rompió el contrato (estado desconocido, tipos equivocados, listas absurdas) | `502` — nunca se copia su cuerpo al usuario ni se registran los valores de la boleta |

**Render duerme el servicio** tras un rato sin uso y tarda en despertar. Si el
proxy de Render responde 502/503/504 **sin JSON**, o la conexión falla, se
reintenta **una vez** tras 5 s. Un 503 *con* JSON es el del propio escáner y
no se reintenta. Todo el intento (con reintento) está acotado por
`OCR_SERVICE_TIMEOUT_SECONDS` (180 s por defecto). El tiempo que tarda un
despertar real **no está medido**: si 180 s no alcanzan, se sube esa variable.
**Recomendado:** el escáner por defecto se da hasta 330 s (`MAX_PROCESSING_TIME_SECONDS`
300 + `TIMEOUT_MARGEN_SEGUNDOS` 30). Si este backend se rinde antes, el escáner
sigue gastando CPU en una lectura que nadie espera. En Render, fija en el
escáner `MAX_PROCESSING_TIME_SECONDS=90` (corte duro a los 120 s) para que se
rinda él primero y de forma limpia. El frontend espera hasta 200 s.

Variables (ver `.env.example`):

| Variable | Qué hace |
|---|---|
| `OCR_SERVICE_URL` | Dirección BASE del escáner, sin ruta (`https://escaner-de-boletas-cl.onrender.com`). Vacía = escaneo desactivado (503). En producción debe ser `https://`. |
| `OCR_SERVICE_KEY` | Clave compartida, enviada en la cabecera `X-Service-Key`. Opcional **mientras el escáner siga público**; en producción, mínimo 24 caracteres. |
| `OCR_SERVICE_TIMEOUT_SECONDS` | Tiempo máximo total de un escaneo. Por defecto 180 (ver arriba: debe ser mayor que el límite del escáner). |
| `OCR_MAX_IMAGE_BYTES` | Tamaño máximo de la imagen. Por defecto 10 MiB. |
| `OCR_MAX_ESCANEOS_POR_USUARIO` / `OCR_RATE_LIMIT_WINDOW_SECONDS` | Cupo por usuario: 10 escaneos cada 10 minutos. |

Decisiones de seguridad (todas con prueba y vigiladas por
`tools/verificar_defensas.py`):

* El formulario se lee **después** de comprobar la sesión. Con `File()`,
  FastAPI leería hasta 10 MB antes de mirar el token.
* Solo `POST /api/v1/boletas/scan` puede recibir más de 1 MiB (excepción
  exacta por método + ruta en `LimitarTamanoCuerpo`, que además sigue siendo
  un tope).
* La conexión a la base se suelta antes de esperar al escáner; si no, 10
  escaneos simultáneos agotan el pool del plan gratuito de Supabase.
* El cliente HTTP no sigue redirecciones (llevarían la clave a otro
  servidor); la clave nunca se imprime (`SecretStr`) ni se registra en logs,
  y tampoco el nombre del archivo.
* La respuesta pasa por una **lista blanca** (`app/schemas/boletas.py`): un
  campo nuevo o interno del escáner no llega al navegador; los valores sucios
  del OCR (caracteres de control, NaN, negativos, fechas absurdas) se sanean
  en vez de tumbar la lectura; un contrato roto es 502, y el log dice qué
  campos fallaron pero nunca sus valores.
* El resultado se devuelve con `Cache-Control: no-store`. La imagen no se
  guarda en ningún lado; en memoria mientras dura la petición, con una
  salvedad técnica: Starlette vuelca a un archivo temporal las subidas de más
  de 1 MiB y lo borra al cerrar el formulario (el router lo cierra siempre).

**Probar la conexión con el escáner de Render desde tu computador.**
`python tools/probar_render.py` (desde `backend/`, con las dependencias instaladas):
despierta el escáner de Render, levanta tu backend en local con una base SQLite
temporal (no usa tu `.env` ni tu base real; no necesita Postgres), sube una boleta
sintética (`tools/boleta_sintetica.jpg`) y dice si se conectaron o dónde falló.
Opciones: `--escaner URL`, `--clave X` (solo si el escáner ya exige `X-Service-Key`),
`--imagen ruta`, `--espera segundos`. Sale con código 0 si se conectaron.
Nota: las migraciones de Alembic son solo para Postgres (usan `now()`); en SQLite
las tablas se crean desde los modelos, como hacen las pruebas.

**Clave de servicio del escáner (pendiente de aplicar).** El escáner
(proyecto aparte) es **público** hoy: cualquiera que conozca su URL puede usarlo
sin pasar por Blynn (gasta CPU del plan gratuito, no expone datos de usuarios).
Para cerrarlo hay un parche para ese proyecto (`escaner-clave-de-servicio.zip`,
18 pruebas propias): le agrega `SERVICE_API_KEY`, que se comprueba antes de leer
el cuerpo. Orden seguro: (1) subir el parche al escáner y desplegar, (2) definir
la MISMA clave en `SERVICE_API_KEY` (escáner) y `OCR_SERVICE_KEY` (aquí).
Mientras el parche no esté aplicado, la clave que este backend envía se ignora.

**Frontend.** `src/lib/boletasScan.js` (`processBoletaFile`) reduce la foto a
2000 px antes de subirla, llama a `api.boletas.scan` y traduce la lectura al
borrador del formulario. **Siempre** se pide confirmación antes de guardar un
gasto: ni una lectura "confiable" se guarda sola. La categoría se sugiere con
una regla simple por nombre de comercio (el escáner no clasifica ni usa IA).

## Despliegue en Vercel + Supabase (Etapa 7)

Tres piezas: **Supabase** (base de datos), **Vercel** proyecto 1 (backend, carpeta `backend/`) y
**Vercel** proyecto 2 (frontend, raíz del repositorio). Todo gratis y sin tarjeta. Lo de abajo está
probado en local; **el despliegue real en Vercel no está probado**: el primer intento puede pedir
ajustes, y `tools/verificar_despliegue.py` está hecho para decir exactamente qué falla.

Límites de los planes gratuitos (verificados en octubre de 2026, pueden cambiar):
Vercel Hobby es solo para uso personal **no comercial** (si cobras o pones anuncios hay que pasar a
Pro) y sus funciones Python admiten hasta 300 s por petición. Supabase gratis **pausa el proyecto
tras 1 semana sin actividad** y hay que reactivarlo a mano.

### 1. Base de datos (Supabase)
1. Crea el proyecto y guarda la contraseña de la base de datos.
2. *Connect*: copia el **Session pooler** (puerto 5432) para las migraciones y el
   **Transaction pooler** (puerto 6543) para la app. Si la contraseña tiene `@ # / : ? %`,
   codifícalos (`@` → `%40`).
3. Crea las tablas **desde tu computador** (una vez, y de nuevo en cada migración nueva):
   `DATABASE_URL="<session pooler>" alembic upgrade head` (desde `backend/`).

### 2. Backend (Vercel, proyecto 1)
1. *Add New → Project*, elige el repositorio, **Root Directory = `backend`**. Framework: *Other*.
2. Variables de entorno: copia `backend/.env.vercel.example` (todas son obligatorias salvo las
   marcadas). `JWT_SECRET_KEY` se genera con `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
3. Deploy. `api/index.py` valida la configuración al cargar: si algo es inseguro, falla con el motivo
   en los *Runtime Logs* en vez de arrancar.

### 3. Frontend (Vercel, proyecto 2)
1. Mismo repositorio, **Root Directory = `.`** (raíz). Framework: *Vite*.
2. Variable `VITE_API_URL=https://TU-BACKEND.vercel.app/api/v1` (con https: si no, el build se niega).
3. `vercel.json` ya redirige todas las rutas a `index.html` (recargar `/gastos` no da 404).
4. Vuelve al proyecto 1 y pon en `CORS_ORIGINS` la dirección exacta del frontend; redespliega.

### 4. Verificar (obligatorio)
`python tools/verificar_despliegue.py --api https://TU-BACKEND.vercel.app --frontend https://TU-FRONTEND.vercel.app --con-escaneo`
Comprueba salud y base de datos, CORS, registro/sesión/datos, el escaneo y, sobre todo, que **la IP
del cliente no se puede falsificar**. Si esa comprobación falla, el límite de intentos de contraseña
se esquiva cambiando una cabecera: cambia `TRUSTED_CLIENT_IP_HEADER` (`x-vercel-forwarded-for`) o
déjala vacía y repite. Con la cabecera vacía, detrás del proxy todos los usuarios comparten un
contador por IP: más seguro que falsificable, pero un atacante podría bloquear a todos.

### Supabase y la pausa por inactividad
Una tarea programada que llame a `GET /health/ready` (hace un `SELECT 1`) cada pocos días podría
mantenerlo activo; **no está comprobado** que eso cuente como actividad para Supabase.

## Pruebas

```bash
pytest                      # SQLite en memoria: no hay que instalar nada
pytest -v                   # con detalle
```

Para probar contra Postgres real (lo que importa para Supabase: bloqueo
de filas, RLS, migraciones):

```bash
createdb blynn_test
TEST_DATABASE_URL="postgresql://usuario@localhost/blynn_test" pytest
```

El nombre de la base **debe terminar en `_test`**: el fixture borra todo
el esquema `public` y se niega a correr contra cualquier otra (así no se
puede apuntar por error a Supabase). Sin instalar Postgres, `pgserver`
(en `requirements-dev.txt`) levanta uno embebido.

| Archivo | Qué cubre |
|---|---|
| `test_db_models.py` | Valores por defecto, restricciones, aislamiento entre usuarios, cascadas |
| `test_db_session.py` | Normalización de la URL de Supabase, SSL, parámetros del motor |
| `test_migrations.py` | Solo Postgres: migraciones == modelos, RLS activado, permisos de `anon`, sin prepared statements |
| `test_auth_passwords.py`, `test_auth_tokens.py` | bcrypt, política de contraseñas, JWT y ataques clásicos (firma alterada, `alg: none`, tipo equivocado…) |
| `test_auth_api.py`, `test_rate_limit.py` | API de auth de punta a punta, rotación y reutilización de refresh tokens, límite de intentos, concurrencia (Postgres) |
| `test_datos_seguridad.py` | Barrido automático: todo endpoint exige login; un usuario no puede ver/cambiar/borrar datos de otro (IDOR); no se pueden inyectar `user_id`/`id`; límite de tamaño |
| `test_categorias.py`, `test_gastos_ingresos.py` | CRUD, validación estricta, filtros, orden, paginación, lote atómico, categorías por defecto idempotentes, renombrado |
| `test_metas.py` | Metas y aportes: semántica de cada modo, deshacer, atomicidad ante fallos, concurrencia (Postgres) |
| `test_perfil.py` | `PATCH /me` (campos protegidos, preferencias, sin foto de perfil) y reinicio de cuenta (confirmación exacta, atomicidad) |
| `test_boletas_escaneo.py` | Escaneo (Etapa 4) con un escáner simulado: sesión antes de leer el cuerpo, validación por bytes, tamaño, cupo y un escaneo a la vez, conexión a la BD liberada, escáner caído/lento/dormido/con respuestas raras, redirecciones, privacidad en logs |
| `test_bloqueos_postgres.py` | Solo Postgres: comprueba de forma determinista que refresh, aportes y deshacer esperan el bloqueo de fila |

Estado: **524 pruebas pasan en Postgres 16; en SQLite pasan 505 y 19 se
omiten a propósito** (las de migraciones, RLS, bloqueos, concurrencia y
tildes, que solo tienen sentido en Postgres). Además se verificó rompiendo
a propósito **73 defensas** (17 de las Etapas 1-2, 26 de la Etapa 3, 24 de la Etapa 4 y 6 de límites compartidos:
filtros por dueño, bloqueos de fila, atomicidad, validaciones, un endpoint
sin login, etc.) y comprobando que algún test falla en cada caso
(`tools/verificar_defensas.py`). Los bloqueos de fila se prueban de forma
**determinista** (una transacción ajena retiene el bloqueo y se comprueba
que la petición espera): una prueba con muchos hilos puede pasar "de
suerte" aunque falte el bloqueo, y una de ellas lo hizo durante la
verificación. También se probó
levantando el servidor real con `uvicorn` contra Postgres, imitando los
flujos del frontend, y con 20.000 gastos de un mismo usuario: los
listados responden en menos de 25 ms y el reinicio de la cuenta en 22 ms.

## Límites conocidos y pendientes (leer antes de desplegar)

1. **El servicio de escaneo hoy no tiene autenticación**: este backend ya
   envía `X-Service-Key`, pero el escáner todavía no la exige (ver
   "Integración con el escaneo"). Hasta entonces cualquiera con su URL puede
   usarlo sin pasar por Blynn.
2. **Correos sin verificar**, sin recuperación de contraseña por correo y
   sin "Continuar con Google": decisión consciente para esta etapa
   (necesitan un servicio de correo / OAuth). Además, quien registre el
   correo de otra persona ocupa esa cuenta; hay que verificar correos
   *antes* de agregar la recuperación de contraseña. Agregar todo esto
   después es aditivo (tablas y endpoints nuevos), no obliga a rehacer.
3. `POST /register` responde `409` si el correo existe, lo que permite
   comprobar si un correo está registrado. Sin verificación por correo no
   se puede evitar; se mitiga con el límite de registros por IP.
4. Los límites de intentos viven **en la base de datos** (tablas `intentos_limitados` y
   `escaneos_en_curso`), así que valen con varias instancias y sobreviven a reinicios. Revisar y
   registrar son dos pasos: peticiones simultáneas pueden exceder el tope por unas pocas. Detrás de
   un proxy la IP que ve el servidor es la del proxy: en Vercel se usa `TRUSTED_CLIENT_IP_HEADER`;
   con uvicorn (Cloud Run, Docker) hay que usar `--proxy-headers` con `--forwarded-allow-ips`
   restringido (uvicorn confía por defecto en `X-Forwarded-For` de conexiones locales). En ambos
   casos se comprueba con `tools/verificar_despliegue.py`.
5. Un access token no se puede anular antes de vencer (máx. 15 min);
   `logout-all` revoca los refresh tokens, no los access ya emitidos.
6. **El frontend debe renovar la sesión de a una petición a la vez.**
   Si dos pestañas usan el mismo refresh token a la vez, la detección de
   reutilización cierra la sesión (es el costo de la protección). Resuelto
   en el frontend (`src/api/http.js`): renovación única por pestaña más un
   bloqueo entre pestañas (Web Locks), con pruebas. Queda un caso residual
   inevitable: si el servidor procesa una renovación pero la respuesta se
   pierde por la red, el reintento reutiliza el token y la sesión se cierra
   (hay que iniciar sesión de nuevo).
7. Los tokens se guardan en `localStorage` (decidido en la Etapa 5): quedarían
   expuestos si la app tuviera una vulnerabilidad XSS. Una cookie `HttpOnly`
   es más segura pero exige que front y API estén bajo el mismo sitio (p. ej.
   `app.blynn.cl` y `api.blynn.cl`); es una mejora posible al desplegar
   (Etapa 7). Mitigación recomendada entonces: una política CSP estricta en
   el hosting del frontend.
8. Aún sin "cambiar contraseña" (debe revocar las demás sesiones al
   hacerlo). No hay foto de perfil a propósito (decisión de producto).
9. Las categorías por defecto no se crean al registrarse: el frontend
   (`Layout.jsx`) llama a `POST /categories/defaults` (idempotente) al
   detectar que no hay ninguna.
10. Este proyecto estuvo conectado a la plataforma anterior (todo cambio subido al repositorio
    se reflejaba en su Builder). Con la Etapa 5 el frontend ya no usa el SDK de
    la plataforma anterior, así que **no debe subirse a una rama conectada a la plataforma anterior**: rompería
    la app que corre allí hoy. Trabajar en otra rama o repositorio hasta el
    despliegue (Etapa 7). La carpeta `respaldo-original/` se conserva como respaldo y se
    puede borrar después.
11. No hay foto de perfil: se quitó por decisión de producto (todos usan el
    mismo avatar). La columna `photo_url` se eliminó con la migración `0003`.

11. **La suma de porcentajes de las metas (≤ 100 %) solo la valida el
    frontend**, y ni siquiera de forma estricta (permite 1 % aunque ya
    esté en 100 %). El servidor no la exige.
12. La unicidad de categorías "sin distinguir mayúsculas" con tildes y `ñ`
    depende de que la base de datos use una configuración regional UTF-8
    normal (verificado en Postgres 16); en SQLite solo pliega ASCII.
13. El límite de 1 MiB por petición aplica a toda la API, salvo
    `POST /boletas/scan` (10 MiB + margen), que tiene una excepción exacta.
14. No hay "eliminar cuenta" (el frontend actual tampoco lo tiene): hoy
    solo existe el reinicio de datos.

## Estructura

```
backend/
├── app/
│   ├── main.py             # Punto de entrada FastAPI
│   ├── config.py           # Configuración central (Settings) y validación de arranque
│   ├── db/                 # Modelos SQLAlchemy, sesión y conexión (Etapa 1)
│   ├── auth/               # Contraseñas, JWT, refresh tokens, límite de intentos (Etapa 2)
│   ├── schemas/            # Validación de entrada y salida de la API de datos (Etapa 3)
│   ├── services/           # Lógica de negocio: aportes atómicos, categorías, reinicio (Etapa 3), escaneo (Etapa 4)
│   ├── api/                # Endpoints (auth, categorías, gastos, ingresos, metas, perfil, boletas)
│   └── utils/              # Logging
├── migrations/             # Migraciones de la base de datos (Alembic)
├── tests/                  # Suite de pytest
├── alembic.ini
├── .env.example            # Plantilla de variables de entorno (copiar a .env)
├── requirements.txt        # Dependencias de producción
└── requirements-dev.txt    # Dependencias de pruebas
```
