// Verifica que las pruebas del frontend realmente VIGILAN las defensas de seguridad.
//
// Un test que pasa no demuestra que proteja algo. Este script rompe a propósito,
// una por una, cada defensa (quita la renovación única de sesión, la limpieza de
// caché al cerrar sesión, la validación de redirecciones...) y comprueba que las
// pruebas FALLAN. Si alguna rotura pasa desapercibida, esa defensa no está
// vigilada y hay que escribir su test.
//
// Uso:  npm run verificar-defensas        (o: node scripts/verificar-defensas.mjs [desde] [hasta])
// (Nota: recortar espacios del correo no se lista: el navegador ya lo hace solo
// en un <input type="email">, así que no es una defensa propia.)
// Cada rotura se aplica, se corren las pruebas (se detiene en el primer fallo) y
// el archivo se RESTAURA siempre. Sale con código 1 si alguna defensa no está
// vigilada o si una línea ya no se encuentra (hay que actualizar la lista).

import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// [descripción, archivo, texto original, texto roto]
const DEFENSAS = [
  ["renovación de sesión sin 'single-flight' (varias a la vez)", "src/api/http.js",
    "  if (!renovacionEnCurso) {", "  if (true) {"],
  ["no revisa si otra pestaña ya renovó los tokens", "src/api/http.js",
    "  if (access && access !== tokenUsado) return access;", "  if (false) return access;"],
  ["un fallo transitorio al renovar cierra la sesión", "src/api/http.js",
    "  // 429, 5xx...: fallo transitorio, NO se cierra la sesión.\n", "  tokenStore.borrar();\n"],
  ["envía cookies/credenciales del navegador", "src/api/http.js", 'credentials: "omit"', 'credentials: "include"'],
  ["renueva también los endpoints públicos (login) ante un 401", "src/api/http.js",
    "if (r.status === 401 && auth && tokenUsado) {", "if (r.status === 401) {"],
  ["reintenta sin límite tras renovar (bucle)", "src/api/http.js",
    "    if (r.status === 401) tokenStore.borrar(); // sigue sin servir: la sesión no es válida\n", ""],
  ["acepta http en producción (tokens sin cifrar)", "src/api/config.js",
    'if (esProduccion && !url.startsWith("https://") && !ES_LOCAL.test(url)) {', "if (false) {"],
  ["el servidor puede exponer detalles internos en errores 500", "src/api/errors.js",
    '  if (status >= 500) return "Ocurrió un error en el servidor. Intenta nuevamente en unos minutos.";\n', ""],
  ["no se enteran los cambios de otra pestaña", "src/api/tokenStore.js",
    "if (e.key === null || e.key === CLAVE_ACCESO || e.key === CLAVE_REFRESCO) notificar();", "void 0;"],
  ["cerrar sesión no borra los tokens al instante", "src/api/index.js",
    "      const { refresh } = tokenStore.leer();\n      tokenStore.borrar();\n      if (!refresh) return;", "      const { refresh } = tokenStore.leer();\n      if (!refresh) return;"],
  ["iniciar sesión no limpia la caché del usuario anterior", "src/lib/AuthContext.jsx",
    "      const usuario = await accion();\n      queryClientInstance.clear();", "      const usuario = await accion();"],
  ["cerrar sesión no limpia la caché del usuario", "src/lib/AuthContext.jsx",
    "    // Los datos en caché son del usuario anterior: nunca deben verse en la sesión siguiente.\n    queryClientInstance.clear();\n", ""],
  ["un fallo de red al iniciar cierra la sesión", "src/lib/AuthContext.jsx",
    "if (e instanceof ApiError && e.status === 401) {", "if (true) {"],
  ["ignora cuando otra pestaña cierra la sesión", "src/lib/AuthContext.jsx",
    '        if (!haySesion && estadoRef.current === "authenticated") {', "        if (false) {"],
  ["una ruta protegida deja pasar sin sesión", "src/components/ProtectedRoute.jsx",
    "  if (!isAuthenticated) {", "  if (false) {"],
  ["redirección abierta tras el login (//evil.com)", "src/lib/authReturnTo.js",
    '    if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\\\")) return "/";', "    if (!path.startsWith(\"/\")) return \"/\";"],
  ["aprobar un aporte de $0 se envía al servidor (error 422)", "src/lib/goalEngine.js",
    "  if (!(amount > 0)) return skipContribution(goal);\n", ""],
  ["el registro no valida el largo mínimo en el navegador", "src/pages/Register.jsx",
    "    if (password.length < LARGO_MINIMO) {", "    if (false) {"],
];

function main() {
  const ini = Number(process.argv[2] ?? 0);
  const fin = Number(process.argv[3] ?? DEFENSAS.length);
  const sinVigilar = [];
  const noAplicables = [];
  let vigiladas = 0;

  for (const [nombre, archivo, original, roto] of DEFENSAS.slice(ini, fin)) {
    const ruta = path.join(RAIZ, archivo);
    const texto = readFileSync(ruta, "utf8");
    const crlf = texto.includes("\r\n");
    const normal = texto.replace(/\r\n/g, "\n");
    if (!normal.includes(original)) {
      noAplicables.push(nombre);
      console.log(`✘ NO SE PUDO APLICAR          ${nombre}  (${archivo})`);
      continue;
    }
    const modificado = normal.replace(original, roto);
    writeFileSync(ruta, crlf ? modificado.replace(/\n/g, "\r\n") : modificado, "utf8");
    let resultado;
    try {
      resultado = spawnSync("npx", ["vitest", "run", "--bail", "1", "--exclude", "**/contrato.test.js"], {
        cwd: RAIZ, encoding: "utf8", timeout: 300_000, shell: process.platform === "win32",
      });
    } finally {
      writeFileSync(ruta, texto, "utf8"); // SIEMPRE se restaura
    }
    if (resultado.status !== 0) {
      vigiladas++;
      console.log(`✔ vigilada                    ${nombre}`);
    } else {
      sinVigilar.push(nombre);
      console.log(`✘ ¡¡ SIN VIGILAR !!           ${nombre}`);
    }
  }
  console.log(`\nvigiladas: ${vigiladas} · sin vigilar: ${sinVigilar.length} · no aplicables: ${noAplicables.length}`);
  process.exit(sinVigilar.length || noAplicables.length ? 1 : 0);
}

main();
