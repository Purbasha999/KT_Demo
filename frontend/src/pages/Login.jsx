import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { getFirms, login, superAdminLogin } from "../api/client";

export default function Login() {
  const [firms, setFirms]             = useState([]);
  const [firmId, setFirmId]           = useState("");
  const [loginId, setLoginId]         = useState("");
  const [password, setPassword]       = useState("");
  const [error, setError]             = useState("");
  const [loading, setLoading]         = useState(false);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const { loginSuccess }              = useAuth();
  const navigate                      = useNavigate();

  useEffect(() => {
    getFirms().then(setFirms).catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      let data;
      if (isSuperAdmin) {
        data = await superAdminLogin(loginId, password);
      } else {
        data = await login(firmId, loginId, password);
      }
      loginSuccess(data);
      if (data.is_superadmin) navigate("/superadmin");
      else if (data.is_admin) navigate("/admin");
      else navigate("/chat");
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setIsSuperAdmin((v) => !v);
    setError("");
    setLoginId("");
    setPassword("");
    setFirmId("");
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 w-full max-w-md p-8">
        <h1 className="text-2xl font-semibold text-gray-800 mb-1">
          {isSuperAdmin ? "Super Admin" : "Sign in"}
        </h1>
        <p className="text-sm text-gray-500 mb-6">KT Demo Chatbot</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isSuperAdmin && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Company</label>
              <select
                required
                value={firmId}
                onChange={(e) => setFirmId(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select your company</option>
                {firms.map((f) => (
                  <option key={f.firm_id} value={f.firm_id}>{f.firm_name}</option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Login ID</label>
            <input
              required
              type="text"
              value={loginId}
              onChange={(e) => setLoginId(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder={isSuperAdmin ? "ADMIN" : "your.login"}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              required
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium rounded-lg py-2 text-sm transition-colors"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={switchMode}
            className="text-xs text-gray-400 hover:text-gray-600 underline transition-colors"
          >
            {isSuperAdmin ? "Back to regular login" : "Super Admin login"}
          </button>
        </div>
      </div>
    </div>
  );
}
