import { Link, useLocation } from "react-router-dom";

export default function PageNotFound() {
  const location = useLocation();
  const pageName = location.pathname.substring(1);

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-slate-50">
      <div className="max-w-md w-full text-center space-y-6">
        <div className="space-y-2">
          <h1 className="text-7xl font-light font-heading text-slate-300">404</h1>
          <div className="h-0.5 w-16 bg-slate-200 mx-auto"></div>
        </div>
        <div className="space-y-3">
          <h2 className="text-2xl font-medium font-heading text-slate-800">Página no encontrada</h2>
          <p className="text-slate-600 leading-relaxed">
            No existe la página <span className="font-medium text-slate-700">«{pageName}»</span> en esta aplicación.
          </p>
        </div>
        <div className="pt-4">
          <Link
            to="/"
            className="inline-flex items-center px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 hover:border-slate-300 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-500"
          >
            Ir al inicio
          </Link>
        </div>
      </div>
    </div>
  );
}
