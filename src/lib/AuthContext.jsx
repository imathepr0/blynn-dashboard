import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, ApiError, describirError, tokenStore } from "@/api";
import { queryClientInstance } from "@/lib/query-client";
import { toast } from "@/components/ui/use-toast";

// Estado de la sesión de la app.
//
//   loading        -> comprobando si hay una sesión guardada
//   authenticated  -> hay usuario
//   anonymous      -> no hay sesión
//   error          -> no se pudo comprobar (sin red / servidor caído / mala
//                     configuración). La sesión guardada NO se borra.
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [estado, setEstado] = useState("loading");
  const [authError, setAuthError] = useState(null);

  const estadoRef = useRef(estado);
  estadoRef.current = estado;
  const operando = useRef(false); // true mientras login/registro/cierre manual están en curso

  const terminarSesion = useCallback((avisar) => {
    // Los datos en caché son del usuario anterior: nunca deben verse en la sesión siguiente.
    queryClientInstance.clear();
    setUser(null);
    setAuthError(null);
    setEstado("anonymous");
    if (avisar) {
      toast({ title: "Tu sesión terminó", description: "Inicia sesión nuevamente para continuar." });
    }
  }, []);

  const cargarUsuario = useCallback(async () => {
    if (!tokenStore.leer().refresh) {
      setEstado("anonymous");
      return;
    }
    setEstado("loading");
    setAuthError(null);
    try {
      setUser(await api.me.get());
      setEstado("authenticated");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setUser(null);
        setEstado("anonymous"); // la sesión ya no es válida (el cliente borró los tokens)
      } else {
        // Sin red, servidor caído o mala configuración: se conserva la sesión guardada.
        setAuthError({ type: e?.code === "config" ? "config" : "network", message: describirError(e) });
        setEstado("error");
      }
    }
  }, []);

  useEffect(() => {
    cargarUsuario();
  }, [cargarUsuario]);

  // Cambios de tokens: sesión vencida/revocada, o login/logout hecho en OTRA pestaña.
  useEffect(
    () =>
      tokenStore.suscribir(({ access, refresh }) => {
        const haySesion = Boolean(access && refresh);
        if (!haySesion && estadoRef.current === "authenticated") {
          terminarSesion(!operando.current);
        } else if (haySesion && estadoRef.current === "anonymous" && !operando.current) {
          cargarUsuario();
        }
      }),
    [terminarSesion, cargarUsuario]
  );

  const iniciar = useCallback(async (accion) => {
    operando.current = true;
    try {
      const usuario = await accion();
      queryClientInstance.clear();
      setUser(usuario);
      setAuthError(null);
      setEstado("authenticated");
      return usuario;
    } finally {
      operando.current = false;
    }
  }, []);

  const login = useCallback((email, password) => iniciar(() => api.auth.login(email, password)), [iniciar]);
  const register = useCallback((datos) => iniciar(() => api.auth.register(datos)), [iniciar]);

  const logout = useCallback(async () => {
    operando.current = true;
    try {
      const aviso = api.auth.logout(); // borra los tokens locales de inmediato
      terminarSesion(false);
      await aviso;
    } finally {
      operando.current = false;
    }
  }, [terminarSesion]);

  /** Guarda cambios del perfil en el servidor y deja al usuario actualizado en la app. */
  const updateUser = useCallback(async (cambios) => {
    const actualizado = await api.me.update(cambios);
    setUser(actualizado);
    return actualizado;
  }, []);

  /** Para cuando otra operación (p. ej. reiniciar la cuenta) devuelve el usuario ya actualizado. */
  const replaceUser = useCallback((actualizado) => setUser(actualizado), []);

  const value = {
    user,
    isAuthenticated: estado === "authenticated",
    isLoadingAuth: estado === "loading",
    authChecked: estado !== "loading",
    authError: estado === "error" ? authError : null,
    login,
    register,
    logout,
    updateUser,
    replaceUser,
    reintentar: cargarUsuario,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
