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

export default api;
