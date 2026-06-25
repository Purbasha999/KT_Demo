import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import Login      from "./pages/Login";
import Chat       from "./pages/Chat";
import Admin      from "./pages/Admin";
import SuperAdmin from "./pages/SuperAdmin";

function PrivateRoute({ children, adminOnly = false, superAdminOnly = false }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/" replace />;
  if (superAdminOnly && !user.is_superadmin) return <Navigate to="/" replace />;
  if (adminOnly && !user.is_admin) return <Navigate to="/chat" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Login />} />
          <Route path="/chat" element={
            <PrivateRoute><Chat /></PrivateRoute>
          } />
          <Route path="/admin" element={
            <PrivateRoute adminOnly><Admin /></PrivateRoute>
          } />
          <Route path="/superadmin" element={
            <PrivateRoute superAdminOnly><SuperAdmin /></PrivateRoute>
          } />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
