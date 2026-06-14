import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import {
  getSchema, uploadSchema,
  getRoles, createRole,
  getUsers, createUser, assignRole,
} from "../api/client";

// ── Minimal tab component ──────────────────────────────────────────────────
function Tabs({ tabs, active, onChange }) {
  return (
    <div className="flex gap-1 border-b border-gray-200 mb-6">
      {tabs.map((t) => (
        <button
          key={t}
          onClick={() => onChange(t)}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            active === t
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          {t}
        </button>
      ))}
    </div>
  );
}

function Toast({ msg, type }) {
  if (!msg) return null;
  return (
    <div className={`fixed top-4 right-4 px-4 py-2 rounded-lg text-sm text-white shadow-lg ${
      type === "error" ? "bg-red-500" : "bg-green-500"
    }`}>
      {msg}
    </div>
  );
}

// ── Schema tab ─────────────────────────────────────────────────────────────
function SchemaTab({ notify }) {
  const [json, setJson]   = useState("");
  const [saved, setSaved] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getSchema()
      .then((s) => { setJson(JSON.stringify(s, null, 2)); setSaved(s); })
      .catch(() => {});
  }, []);

  const save = async () => {
    setLoading(true);
    try {
      const parsed = JSON.parse(json);
      await uploadSchema(parsed);
      notify("Schema saved successfully", "success");
    } catch (e) {
      notify(e.response?.data?.detail || "Invalid JSON or save failed", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <p className="text-sm text-gray-500 mb-3">
        Describe your database tables, fields, and relationships. The chatbot uses this to understand your data.
      </p>
      <textarea
        value={json}
        onChange={(e) => setJson(e.target.value)}
        rows={22}
        className="w-full font-mono text-xs border border-gray-300 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
        placeholder={JSON.stringify({
          tables: [{ name: "employees", description: "All employees", fields: [{ name: "id", type: "INT", description: "Primary key" }] }],
          relationships: [{ from: "sales.emp_id", to: "employees.id", type: "FK" }]
        }, null, 2)}
      />
      <button
        onClick={save}
        disabled={loading}
        className="mt-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
      >
        {loading ? "Saving…" : "Save schema"}
      </button>
    </div>
  );
}

// ── Roles tab ──────────────────────────────────────────────────────────────
function RolesTab({ notify, onRolesChange }) {
  const [roles, setRoles]       = useState([]);
  const [name, setName]         = useState("");
  const [tables, setTables]     = useState("");
  const [loading, setLoading]   = useState(false);

  const load = () => getRoles().then((r) => { setRoles(r); onRolesChange(r); }).catch(() => {});

  useEffect(() => { load(); }, []);

  const save = async () => {
    setLoading(true);
    try {
      const allowed = tables.trim() === "*" ? ["*"] : tables.split(",").map((t) => t.trim()).filter(Boolean);
      await createRole({ role_name: name, allowed_tables: allowed });
      notify(`Role "${name}" saved`, "success");
      setName(""); setTables("");
      load();
    } catch (e) {
      notify(e.response?.data?.detail || "Failed to save role", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Create / update role</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Role name</label>
            <input value={name} onChange={(e) => setName(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="e.g. CEO, HR Head" />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Allowed tables (comma-separated or *)</label>
            <input value={tables} onChange={(e) => setTables(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="employees, sales or *" />
          </div>
        </div>
        <button onClick={save} disabled={loading || !name || !tables}
          className="mt-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
          {loading ? "Saving…" : "Save role"}
        </button>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left pb-2 text-gray-500 font-medium">Role</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Allowed tables</th>
          </tr>
        </thead>
        <tbody>
          {roles.map((r) => (
            <tr key={r.role_id} className="border-b border-gray-100">
              <td className="py-2 font-medium text-gray-700">{r.role_name}</td>
              <td className="py-2 text-gray-500">
                {Array.isArray(r.allowed_tables) ? r.allowed_tables.join(", ") : r.allowed_tables}
              </td>
            </tr>
          ))}
          {roles.length === 0 && (
            <tr><td colSpan={2} className="py-4 text-gray-400 text-center">No roles yet</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ── Users tab ──────────────────────────────────────────────────────────────
function UsersTab({ roles, notify }) {
  const [users, setUsers]       = useState([]);
  const [loginId, setLoginId]   = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [roleId, setRoleId]     = useState("");
  const [loading, setLoading]   = useState(false);

  const load = () => getUsers().then(setUsers).catch(() => {});

  useEffect(() => { load(); }, []);

  const save = async () => {
    setLoading(true);
    try {
      await createUser({
        login_id: loginId,
        display_name: displayName,
        password,
        role_id: roleId ? Number(roleId) : undefined,
      });
      notify("User created", "success");
      setLoginId(""); setDisplayName(""); setPassword(""); setRoleId("");
      load();
    } catch (e) {
      notify(e.response?.data?.detail || "Failed to create user", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleAssign = async (userId, newRoleId) => {
    try {
      await assignRole(userId, Number(newRoleId));
      notify("Role updated", "success");
      load();
    } catch {
      notify("Failed to assign role", "error");
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Create user</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Login ID</label>
            <input value={loginId} onChange={(e) => setLoginId(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="john.doe" />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Display name</label>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="John Doe" />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Role</label>
            <select value={roleId} onChange={(e) => setRoleId(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="">Select role</option>
              {roles.map((r) => <option key={r.role_id} value={r.role_id}>{r.role_name}</option>)}
            </select>
          </div>
        </div>
        <button onClick={save} disabled={loading || !loginId || !password}
          className="mt-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
          {loading ? "Creating…" : "Create user"}
        </button>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left pb-2 text-gray-500 font-medium">User</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Login ID</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Role</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.user_id} className="border-b border-gray-100">
              <td className="py-2 text-gray-700">{u.display_name || "—"}</td>
              <td className="py-2 text-gray-500 font-mono text-xs">{u.login_id}</td>
              <td className="py-2">
                <select
                  defaultValue={u.role_id || ""}
                  onChange={(e) => e.target.value && handleAssign(u.user_id, e.target.value)}
                  className="border border-gray-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">No role</option>
                  {roles.map((r) => <option key={r.role_id} value={r.role_id}>{r.role_name}</option>)}
                </select>
              </td>
            </tr>
          ))}
          {users.length === 0 && (
            <tr><td colSpan={3} className="py-4 text-gray-400 text-center">No users yet</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ── Main Admin page ────────────────────────────────────────────────────────
export default function Admin() {
  const [tab, setTab]       = useState("Schema");
  const [roles, setRoles]   = useState([]);
  const [toast, setToast]   = useState({ msg: "", type: "" });
  const { user, logout }    = useAuth();
  const navigate            = useNavigate();

  const notify = (msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast({ msg: "", type: "" }), 3000);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Toast msg={toast.msg} type={toast.type} />

      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="font-semibold text-gray-800">Admin panel</h1>
          <p className="text-xs text-gray-500">{user?.firm_id}</p>
        </div>
        <button
          onClick={() => { logout(); navigate("/"); }}
          className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
        >
          Sign out
        </button>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        <Tabs
          tabs={["Schema", "Roles", "Users"]}
          active={tab}
          onChange={setTab}
        />
        {tab === "Schema" && <SchemaTab notify={notify} />}
        {tab === "Roles"  && <RolesTab  notify={notify} onRolesChange={setRoles} />}
        {tab === "Users"  && <UsersTab  roles={roles} notify={notify} />}
      </main>
    </div>
  );
}
