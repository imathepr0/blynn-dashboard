# Blynn

Aplicación web de finanzas personales para Chile (gastos, ingresos, categorías, metas de ahorro
y presupuesto en pesos chilenos).

## Cómo está organizado el proyecto

```
├── src/              Frontend (React + Vite + Tailwind)
├── backend/          Backend propio (FastAPI + Postgres/Supabase) — ver backend/README.md
├── respaldo-original/  ANTIGUO: definición original de la app (ya no se usa; ver más abajo)
└── ...
```

El frontend habla con el backend por HTTP (`src/api/`). **Ya no depende de la plataforma anterior**: ni su SDK, ni su
servidor, ni su inicio de sesión, ni sus imágenes.

## Puesta en marcha (desarrollo)

Requiere Node 20 o superior y el backend corriendo (instrucciones en `backend/README.md`).

```bash
# 1) Backend (en otra terminal, desde backend/)
uvicorn app.main:app --reload --port 8000

# 2) Frontend (desde la raíz del proyecto)
npm install
npm run dev            # http://localhost:5173
```

Sin configurar nada, el frontend usa `http://localhost:8000/api/v1`. Para otra dirección copia
`.env.example` como `.env.local` y cambia `VITE_API_URL`.

## Comandos

| Comando | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo |
| `npm run build` | Compila para producción (exige `VITE_API_URL` con `https://`) |
| `npm run lint` | Revisa el código con ESLint |
| `npm test` | Pruebas (capa de API, sesión, pantallas de acceso, aportes, escaneo) |
| `npm run verificar-defensas` | Rompe a propósito 18 defensas de seguridad del cliente y comprueba que las pruebas fallan |

**Prueba de contrato contra un backend real.** `src/api/contrato.test.js` ejecuta el código real del
frontend contra un backend real (cuentas, gastos, metas, aportes, renovación de sesión, CORS...). Solo
corre si se indica un servidor de DESARROLLO:

```bash
# backend arrancado con AUTH_MAX_REGISTROS_POR_IP=1000 (la prueba crea muchas cuentas)
BLYNN_CONTRACT_URL=http://127.0.0.1:8000/api/v1 VITE_API_URL=http://127.0.0.1:8000/api/v1 \
  npx vitest run src/api/contrato.test.js
```

## Cómo funciona la sesión en el frontend

* `src/api/` es la **única** puerta al backend: las pantallas nunca llaman a `fetch` directamente.
* Los tokens se guardan en `localStorage`. El token de acceso dura 15 minutos y se renueva solo.
* **La renovación está serializada** (también entre pestañas, con Web Locks): el backend usa tokens de
  renovación de un solo uso y cierra la sesión si uno se reutiliza, así que dos renovaciones simultáneas
  la romperían. Un fallo de red al renovar NO cierra la sesión.
* Al cerrar sesión (o si vence) se borra la caché de datos, para que el siguiente usuario del mismo
  navegador nunca vea datos del anterior.
* Las pantallas de acceso son `Login` y `Register` (correo + contraseña). El mensaje de error de cada
  fallo viene del servidor, ya en español.

## Qué cambió respecto a la versión anterior

* **Inicio de sesión y registro propios.** Ya no hay verificación por código ni "Continuar con Google" ni
  "Olvidé mi contraseña" (el backend aún no los tiene; se pueden agregar después).
* **Escaneo de boletas: activo.** Ya no usa la IA de la plataforma anterior: la foto va al backend de Blynn, que la lee con el
  servicio de escaneo propio (OpenCV + Tesseract, sin IA). Siempre se revisa y confirma antes de guardar. Si el
  servicio no está disponible, la pantalla lo explica y se puede ingresar a mano. Ver `src/lib/boletasScan.js`.
  **Sin cámara en la web (decisión de producto):** solo se sube una foto desde el dispositivo ("Subir foto de
  boleta"); no se pide permiso de cámara. En un celular, el selector de archivos del sistema suele ofrecer
  tomar la foto en el momento (no verificado en navegadores reales). La cámara integrada podría volver con una
  app móvil. Si el servicio de lectura estaba dormido, la primera lectura puede tardar más de un minuto
  (medido: 76 s) y la pantalla de espera lo explica.
* **Foto de perfil: se quitó.** Todos los usuarios usan el mismo avatar por defecto (decisión de producto).
  El backend ya no guarda ni devuelve ninguna foto.
* **Logo:** estaba alojado en los servidores de la plataforma anterior. Ahora es un SVG (`src/components/LogoMark.jsx`);
  para volver al logo original guarda la imagen en `public/` y cámbialo en ese único archivo.
* **Montos:** deben ser mayores que 0 (antes se aceptaba 0). Aprobar un aporte automático de $0 equivale a omitirlo.
* **Aportes a metas, reinicio de cuenta y categorías por defecto** son ahora operaciones únicas y atómicas
  del servidor (antes eran varias llamadas que podían quedar a medias).
* **Renombrar una categoría** actualiza también sus gastos.
* Se eliminó `Perfil.jsx` (no tenía ruta; duplicaba a Ajustes) y las pantallas de recuperar contraseña.
* Se corrigieron dos archivos con el nombre mal escrito que impedían compilar
  (`PageNotFouns.jsx` → `PageNotFound.jsx`, `ComparinsonCard.jsx` → `ComparisonCard.jsx`).

## IMPORTANTE: la carpeta `respaldo-original/` y el repositorio conectado

* `respaldo-original/` (definición de entidades y configuración) ya no la usa nada de este código. Se conserva solo
  como respaldo hasta que todo esté en producción; después se puede borrar.
* **Si este repositorio sigue conectado a la plataforma anterior** (sus cambios se reflejan en esa plataforma), NO subas esta
  versión a la rama conectada: la app que corre hoy en la plataforma anterior dejaría de funcionar. Trabaja en una rama
  o repositorio aparte hasta el despliegue final (Etapa 7).

## Pendiente de plan

Aplicar el parche de clave de servicio al escáner y probar el escaneo contra el de Render · Etapa 7 (despliegue). Detalle en
`backend/README.md`.
