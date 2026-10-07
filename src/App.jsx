import { Toaster } from "@/components/ui/toaster"
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClientInstance } from '@/lib/query-client'
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import PageNotFound from './lib/PageNotFound';
import { AuthProvider, useAuth } from '@/lib/AuthContext';
import ScrollToTop from './components/ScrollToTop';
import ProtectedRoute from '@/components/ProtectedRoute';
import Layout from '@/components/layout/Layout';
import Login from '@/pages/Login';
import Register from '@/pages/Register';
import Resumen from '@/pages/Resumen';
import Estadisticas from '@/pages/Estadisticas';
import Gastos from '@/pages/Gastos';
import Categorias from '@/pages/Categorias';
import Boletas from '@/pages/Boletas';
import Metas from '@/pages/Metas';
import Ajustes from '@/pages/Ajustes';
import ExportarDatos from '@/pages/ExportarDatos';
import Ingresos from '@/pages/Ingresos';
import ErrorDeConexion from '@/components/ErrorDeConexion';
// Add page imports here

const AuthenticatedApp = () => {
  const { isLoadingAuth, authError, reintentar } = useAuth();

  // Mientras se comprueba si hay una sesión guardada
  if (isLoadingAuth) {
    return (
      <div className="fixed inset-0 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-slate-200 border-t-slate-800 rounded-full animate-spin"></div>
      </div>
    );
  }

  // No se pudo comprobar la sesión (sin conexión, servidor caído o mala configuración)
  if (authError) {
    return <ErrorDeConexion mensaje={authError.message} onReintentar={reintentar} />;
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Resumen />} />
          <Route path="/estadisticas" element={<Estadisticas />} />
          <Route path="/gastos" element={<Gastos />} />
          <Route path="/categorias" element={<Categorias />} />
          <Route path="/boletas" element={<Boletas />} />
          <Route path="/metas" element={<Metas />} />
          <Route path="/ajustes" element={<Ajustes />} />
          <Route path="/exportar-datos" element={<ExportarDatos />} />
          <Route path="/ingresos" element={<Ingresos />} />
        </Route>
      </Route>
      <Route path="*" element={<PageNotFound />} />
    </Routes>
  );
};


function App() {

  return (
    <AuthProvider>
      <QueryClientProvider client={queryClientInstance}>
        <Router>
          <ScrollToTop />
          <AuthenticatedApp />
        </Router>
        <Toaster />
      </QueryClientProvider>
    </AuthProvider>
  )
}

export default App
