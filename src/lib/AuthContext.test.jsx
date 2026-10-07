import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter, Route, Routes, Link } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import { queryClientInstance } from "@/lib/query-client";
import { tokenStore } from "@/api";
import { servidor, sesion, tokensRespuesta, usuarioEjemplo } from "@/test/servidorFalso";

function Privada({ titulo }) {
  const { user, logout } = useAuth();
  return (
    <div>
      <h1>{titulo}</h1>
      <p>Hola {user.full_name || user.email}</p>
      <button onClick={logout}>Salir</button>
      <Link to="/gastos">Ir a gastos</Link>
    </div>
  );
}

function montar(ruta = "/") {
  window.history.pushState({}, "", ruta);
  return render(
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Privada titulo="Inicio" />} />
            <Route path="/gastos" element={<Privada titulo="Gastos" />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

const ruta = () => window.location.pathname + window.location.search;
// Servidor que reconoce al usuario cuando llega el access token vigente.
const servidorConSesion = (usuario = usuarioEjemplo(), extra = () => null) =>
  servidor((req) => extra(req) || (req.ruta === "/me" ? { status: 200, body: usuario } : { status: 404, body: {} }));

describe("arranque de la app", () => {
  it("sin sesión guardada lleva al login", async () => {
    servidorConSesion();
    montar("/");
    expect(await screen.findByText("Bienvenido de nuevo")).toBeInTheDocument();
    expect(ruta()).toBe("/login");
  });

  it("con sesión válida muestra la app y recuerda a qué página volver", async () => {
    tokenStore.guardar(sesion());
    servidorConSesion();
    montar("/gastos");
    expect(await screen.findByText("Gastos")).toBeInTheDocument();
    expect(screen.getByText("Hola Ana")).toBeInTheDocument();
  });

  it("sin sesión, una página interna lleva al login conservando el destino", async () => {
    servidorConSesion();
    montar("/gastos");
    await screen.findByText("Bienvenido de nuevo");
    expect(ruta()).toBe("/login?returnTo=%2Fgastos");
  });

  it("si la sesión guardada ya no es válida, vuelve al login y limpia los tokens", async () => {
    tokenStore.guardar(sesion());
    servidor(() => ({ status: 401, body: { detail: "No autorizado." } }));
    montar("/");
    await screen.findByText("Bienvenido de nuevo");
    expect(tokenStore.leer()).toEqual({ access: null, refresh: null });
  });

  it("si el servidor no responde, avisa SIN cerrar la sesión y permite reintentar", async () => {
    tokenStore.guardar(sesion());
    let caido = true;
    servidor(({ ruta: r }) => {
      if (caido) return new TypeError("Failed to fetch");
      return r === "/me" ? { status: 200, body: usuarioEjemplo() } : { status: 404, body: {} };
    });
    montar("/");
    expect(await screen.findByText("No pudimos conectar")).toBeInTheDocument();
    expect(tokenStore.leer()).toEqual(sesion()); // la sesión se conserva
    caido = false;
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Hola Ana")).toBeInTheDocument();
  });
});

describe("login", () => {
  it("inicia sesión, entra a la app y limpia la caché del usuario anterior", async () => {
    queryClientInstance.setQueryData(["dato-del-usuario-anterior"], { secreto: true });
    const s = servidor(({ ruta: r }) => (r === "/auth/login" ? { status: 200, body: { ...tokensRespuesta(1), user: usuarioEjemplo() } } : { status: 404, body: {} }));
    montar("/login");
    await userEvent.type(await screen.findByLabelText("Correo electrónico"), "  ana@correo.cl ");
    await userEvent.type(screen.getByLabelText("Contraseña"), "mi-clave-123");
    await userEvent.click(screen.getByRole("button", { name: "Iniciar sesión" }));
    expect(await screen.findByText("Hola Ana")).toBeInTheDocument();
    expect(s.llamadas[0].cuerpo).toEqual({ email: "ana@correo.cl", password: "mi-clave-123" }); // correo sin espacios
    expect(queryClientInstance.getQueryData(["dato-del-usuario-anterior"])).toBeUndefined();
    expect(tokenStore.leer()).toEqual(sesion(1));
  });

  it("vuelve a la página que se quería abrir", async () => {
    servidor(({ ruta: r }) => (r === "/auth/login" ? { status: 200, body: { ...tokensRespuesta(1), user: usuarioEjemplo() } } : { status: 404, body: {} }));
    montar("/gastos");
    await userEvent.type(await screen.findByLabelText("Correo electrónico"), "ana@correo.cl");
    await userEvent.type(screen.getByLabelText("Contraseña"), "mi-clave-123");
    await userEvent.click(screen.getByRole("button", { name: "Iniciar sesión" }));
    expect(await screen.findByText("Gastos")).toBeInTheDocument();
    expect(ruta()).toBe("/gastos");
  });

  it("con credenciales malas muestra el mensaje, no entra y deja volver a intentar", async () => {
    servidor(() => ({ status: 401, body: { detail: "Correo o contraseña incorrectos." } }));
    montar("/login");
    await userEvent.type(await screen.findByLabelText("Correo electrónico"), "ana@correo.cl");
    await userEvent.type(screen.getByLabelText("Contraseña"), "mala-clave-1");
    await userEvent.click(screen.getByRole("button", { name: "Iniciar sesión" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Correo o contraseña incorrectos.");
    expect(screen.getByRole("button", { name: "Iniciar sesión" })).toBeEnabled();
    expect(tokenStore.leer().access).toBeNull();
  });

  it("muestra el aviso de demasiados intentos y el de falta de conexión", async () => {
    servidor(() => ({ status: 429, body: { detail: "Demasiados intentos. Intenta nuevamente en 15 min." } }));
    montar("/login");
    await userEvent.type(await screen.findByLabelText("Correo electrónico"), "ana@correo.cl");
    await userEvent.type(screen.getByLabelText("Contraseña"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Iniciar sesión" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Demasiados intentos");
  });

  it("no ofrece las opciones que el backend aún no tiene (Google, recuperar contraseña)", async () => {
    servidorConSesion();
    montar("/login");
    await screen.findByText("Bienvenido de nuevo");
    expect(screen.queryByText(/google/i)).toBeNull();
    expect(screen.queryByText(/olvidaste/i)).toBeNull();
  });
});

describe("registro", () => {
  async function llenar(email, clave, confirmacion = clave) {
    await userEvent.type(await screen.findByLabelText("Correo electrónico"), email);
    await userEvent.type(screen.getByLabelText("Contraseña"), clave);
    await userEvent.type(screen.getByLabelText("Confirmar contraseña"), confirmacion);
    await userEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));
  }

  it("valida la contraseña en el navegador antes de llamar al servidor", async () => {
    const s = servidorConSesion();
    montar("/register");
    await llenar("ana@correo.cl", "corta1");
    expect(await screen.findByRole("alert")).toHaveTextContent("al menos 8 caracteres");
    expect(s.llamadas).toHaveLength(0);
  });

  it("avisa si las contraseñas no coinciden", async () => {
    const s = servidorConSesion();
    montar("/register");
    await llenar("ana@correo.cl", "clave-larga-1", "clave-larga-2");
    expect(await screen.findByRole("alert")).toHaveTextContent("no coinciden");
    expect(s.llamadas).toHaveLength(0);
  });

  it("crea la cuenta y entra directamente a la app (sin código de verificación)", async () => {
    const s = servidor(({ ruta: r }) => (r === "/auth/register" ? { status: 201, body: { ...tokensRespuesta(1), user: usuarioEjemplo({ full_name: null }) } } : { status: 404, body: {} }));
    montar("/register");
    await llenar("ana@correo.cl", "clave-larga-1");
    expect(await screen.findByText("Hola ana@correo.cl")).toBeInTheDocument();
    expect(s.llamadas[0].cuerpo).toEqual({ email: "ana@correo.cl", password: "clave-larga-1" });
  });

  it("muestra los errores del servidor (correo repetido, contraseña común)", async () => {
    servidor(() => ({ status: 409, body: { detail: "Ya existe una cuenta con ese correo." } }));
    montar("/register");
    await llenar("ana@correo.cl", "clave-larga-1");
    expect(await screen.findByRole("alert")).toHaveTextContent("Ya existe una cuenta con ese correo.");
  });

  it("traduce un correo inválido rechazado por el servidor", async () => {
    servidor(() => ({ status: 422, body: { detail: [{ loc: ["body", "email"], type: "value_error", msg: "x" }] } }));
    montar("/register");
    await userEvent.type(await screen.findByLabelText("Correo electrónico"), "ana@correo");
    await userEvent.type(screen.getByLabelText("Contraseña"), "clave-larga-1");
    await userEvent.type(screen.getByLabelText("Confirmar contraseña"), "clave-larga-1");
    await userEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Ingresa un correo electrónico válido.");
  });
});

describe("cierre de sesión y cambios de sesión", () => {
  it("cerrar sesión borra los tokens al instante, avisa al servidor y limpia la caché", async () => {
    tokenStore.guardar(sesion());
    queryClientInstance.setQueryData(["privado"], { x: 1 });
    const s = servidorConSesion(usuarioEjemplo(), ({ ruta: r }) => (r === "/auth/logout" ? { status: 204 } : null));
    montar("/");
    await userEvent.click(await screen.findByRole("button", { name: "Salir" }));
    await screen.findByText("Bienvenido de nuevo");
    expect(tokenStore.leer()).toEqual({ access: null, refresh: null });
    expect(queryClientInstance.getQueryData(["privado"])).toBeUndefined();
    await waitFor(() => expect(s.cuantas("/auth/logout")).toBe(1));
    expect(s.llamadas.find((l) => l.ruta === "/auth/logout").cuerpo).toEqual({ refresh_token: "refresco-1" });
  });

  it("cerrar sesión funciona aunque no haya conexión", async () => {
    tokenStore.guardar(sesion());
    let sinRed = false;
    servidor(({ ruta: r }) => (sinRed ? new TypeError("Failed to fetch") : r === "/me" ? { status: 200, body: usuarioEjemplo() } : { status: 404, body: {} }));
    montar("/");
    const boton = await screen.findByRole("button", { name: "Salir" });
    sinRed = true;
    await userEvent.click(boton);
    await screen.findByText("Bienvenido de nuevo");
    expect(tokenStore.leer().refresh).toBeNull();
  });

  it("si otra pestaña cierra la sesión, esta pestaña también sale", async () => {
    tokenStore.guardar(sesion());
    servidorConSesion();
    montar("/");
    await screen.findByText("Hola Ana");
    act(() => tokenStore.borrar()); // lo que ocurre cuando otra pestaña (o una sesión vencida) borra los tokens
    await screen.findByText("Bienvenido de nuevo");
    expect(ruta()).toBe("/login");
  });

  it("si otra pestaña inicia sesión, esta pestaña entra sola", async () => {
    servidorConSesion();
    montar("/login");
    await screen.findByText("Bienvenido de nuevo");
    act(() => tokenStore.guardar(sesion(2)));
    expect(await screen.findByText("Hola Ana")).toBeInTheDocument();
  });

  it("una sesión que vence a mitad de uso (renovación rechazada) lleva al login", async () => {
    tokenStore.guardar(sesion());
    let vencida = false;
    servidor(({ ruta: r }) => {
      if (vencida) return { status: 401, body: { detail: "Sesión inválida o expirada. Inicia sesión nuevamente." } };
      return r === "/me" ? { status: 200, body: usuarioEjemplo() } : { status: 404, body: {} };
    });
    montar("/");
    await screen.findByText("Hola Ana");
    vencida = true;
    const { api } = await import("@/api");
    await expect(api.expenses.list()).rejects.toMatchObject({ status: 401 });
    await screen.findByText("Bienvenido de nuevo");
  });
});
