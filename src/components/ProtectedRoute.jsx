import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import ErrorDeConexion from "@/components/ErrorDeConexion";

const DefaultFallback = () => (
  <div className="fixed inset-0 flex items-center justify-center">
    <div className="w-8 h-8 border-4 border-slate-200 border-t-slate-800 rounded-full animate-spin"></div>
  </div>
);

/** Lleva al login recordando a qué página volver (solo si no es la de inicio). */
export function destinoLogin({ pathname, search }) {
  const actual = `${pathname}${search}`;
  return actual === "/" ? "/login" : `/login?returnTo=${encodeURIComponent(actual)}`;
}

export default function ProtectedRoute({ fallback = <DefaultFallback /> }) {
  const { isAuthenticated, isLoadingAuth, authError, reintentar } = useAuth();
  const location = useLocation();

  if (isLoadingAuth) return fallback;

  if (authError) {
    return <ErrorDeConexion mensaje={authError.message} onReintentar={reintentar} />;
  }

  if (!isAuthenticated) {
    return <Navigate to={destinoLogin(location)} replace />;
  }

  return <Outlet />;
}
