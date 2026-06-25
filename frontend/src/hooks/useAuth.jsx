import { createContext, useContext, useState, useEffect } from "react";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    const meta  = localStorage.getItem("user_meta");
    if (token && meta) setUser(JSON.parse(meta));
  }, []);

  const loginSuccess = (tokenData) => {
    localStorage.setItem("token", tokenData.access_token);
    const meta = {
      display_name:  tokenData.display_name,
      firm_id:       tokenData.firm_id,
      is_admin:      tokenData.is_admin,
      is_superadmin: tokenData.is_superadmin || false,
    };
    localStorage.setItem("user_meta", JSON.stringify(meta));
    setUser(meta);
  };

  const logout = () => {
    localStorage.clear();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loginSuccess, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
