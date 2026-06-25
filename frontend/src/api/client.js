import axios from "axios";

const api = axios.create({ baseURL: "http://localhost:8000" });

// Attach JWT to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-logout on 401
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.clear();
      window.location.href = "/";
    }
    return Promise.reject(err);
  }
);

// ── Auth ──────────────────────────────────────────────────────────────────────
export const getFirms = () => api.get("/auth/firms").then((r) => r.data);

export const login = (firm_id, login_id, password) =>
  api.post("/auth/login", { firm_id, login_id, password }).then((r) => r.data);

export const superAdminLogin = (login_id, password) =>
  api.post("/auth/superadmin-login", { login_id, password }).then((r) => r.data);

// ── Chat ──────────────────────────────────────────────────────────────────────
export const sendQuestion = (question, history = []) =>
  api.post("/chat/query", { question, history }).then((r) => r.data);

// ── Admin ─────────────────────────────────────────────────────────────────────
export const getSchema = () => api.get("/admin/schema").then((r) => r.data);
export const uploadSchema = (schema) =>
  api.post("/admin/schema", schema).then((r) => r.data);

export const getRoles = () => api.get("/admin/roles").then((r) => r.data);
export const createRole = (data) =>
  api.post("/admin/role", data).then((r) => r.data);
export const updateRole = (roleId, data) =>
  api.put(`/admin/role/${roleId}`, data).then((r) => r.data);
export const deleteRole = (roleId) =>
  api.delete(`/admin/role/${roleId}`);

export const getUsers = () => api.get("/admin/users").then((r) => r.data);
export const createUser = (data) =>
  api.post("/admin/user", data).then((r) => r.data);
export const updateUser = (userId, data) =>
  api.put(`/admin/user/${userId}`, data).then((r) => r.data);
export const assignRole = (user_id, role_id) =>
  api.post("/admin/user/assign-role", { user_id, role_id }).then((r) => r.data);
export const deleteUser = (userId) =>
  api.delete(`/admin/user/${userId}`);

export const getDocuments = () => api.get("/admin/documents").then((r) => r.data);
export const uploadDocument = (file, replace = true, description = "") => {
  const form = new FormData();
  form.append("file", file);
  if (description) form.append("description", description);
  return api.post(`/admin/documents/upload?replace=${replace}`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  }).then((r) => r.data);
};
export const deleteDocument = (filename) =>
  api.delete(`/admin/documents/${encodeURIComponent(filename)}`).then((r) => r.data);

// ── Superadmin ────────────────────────────────────────────────────────────────
export const getSuperAdminStats    = () => api.get("/superadmin/stats").then((r) => r.data);

export const getSuperAdminFirms    = () => api.get("/superadmin/firms").then((r) => r.data);
export const getFirmsList          = () => api.get("/superadmin/firms-list").then((r) => r.data);
export const createFirm            = (data) => api.post("/superadmin/firm", data).then((r) => r.data);
export const updateFirm            = (firmId, data) => api.put(`/superadmin/firm/${firmId}`, data).then((r) => r.data);
export const deleteFirm            = (firmId) => api.delete(`/superadmin/firm/${firmId}`);

export const getSuperAdminAdmins   = () => api.get("/superadmin/admins").then((r) => r.data);
export const createSuperAdmin      = (data) => api.post("/superadmin/admin", data).then((r) => r.data);
export const updateSuperAdmin      = (userId, data) => api.put(`/superadmin/admin/${userId}`, data).then((r) => r.data);
export const deleteSuperAdmin      = (userId) => api.delete(`/superadmin/admin/${userId}`);

export const getSuperAdminUsers    = () => api.get("/superadmin/users").then((r) => r.data);
export const updateSuperAdminUser  = (userId, data) => api.put(`/superadmin/user/${userId}`, data).then((r) => r.data);
export const deleteSuperAdminUser  = (userId) => api.delete(`/superadmin/user/${userId}`);

export default api;
