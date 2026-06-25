import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import {
  getSuperAdminStats,
  getSuperAdminFirms, getFirmsList, createFirm, updateFirm, deleteFirm,
  getSuperAdminAdmins, createSuperAdmin, updateSuperAdmin, deleteSuperAdmin,
  getSuperAdminUsers, updateSuperAdminUser, deleteSuperAdminUser,
} from "../api/client";

// ── Helpers ───────────────────────────────────────────────────────────────────
function Toast({ msg, type }) {
  if (!msg) return null;
  return (
    <div className={`fixed top-4 right-4 px-4 py-2 rounded-lg text-sm text-white shadow-lg z-50 ${
      type === "error" ? "bg-red-500" : "bg-green-500"
    }`}>
      {msg}
    </div>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-40 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-800">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

const inputCls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";
const labelCls = "block text-xs text-gray-500 mb-1";

// ── Dashboard ─────────────────────────────────────────────────────────────────
function DashboardSection() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    getSuperAdminStats().then(setStats).catch(() => {});
  }, []);

  const cards = [
    { label: "Firms",  value: stats?.firm_count  ?? "—" },
    { label: "Admins", value: stats?.admin_count ?? "—" },
    { label: "Users",  value: stats?.user_count  ?? "—" },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-800">Dashboard</h2>
      <div className="grid grid-cols-3 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-5 text-center">
            <p className="text-3xl font-bold text-blue-600">{c.value}</p>
            <p className="text-sm text-gray-500 mt-1">{c.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Firm Form (shared add/edit modal) ─────────────────────────────────────────
function FirmModal({ mode, firm, onClose, onSaved, notify }) {
  const [firmId,      setFirmId]      = useState(mode === "edit" ? firm.firm_id   : "");
  const [firmName,    setFirmName]    = useState(mode === "edit" ? firm.firm_name : "");
  const [description, setDescription] = useState(mode === "edit" ? (firm.description || "") : "");
  const [dbType,      setDbType]      = useState(mode === "edit" ? firm.db_type   : "none");
  const [dbHost,      setDbHost]      = useState(mode === "edit" ? (firm.db_host || "") : "");
  const [dbPort,      setDbPort]      = useState(mode === "edit" ? (firm.db_port || 3306) : 3306);
  const [dbName,      setDbName]      = useState(mode === "edit" ? (firm.db_name || "") : "");
  const [dbUser,      setDbUser]      = useState(mode === "edit" ? (firm.db_user || "") : "");
  const [dbPassword,  setDbPassword]  = useState("");
  const [mongoUri,    setMongoUri]    = useState("");
  const [loading,     setLoading]     = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const data = {
        firm_id:     firmId,
        firm_name:   firmName,
        description,
        db_type:     dbType,
        db_host:     dbType === "mysql"   ? dbHost   : null,
        db_port:     dbType === "mysql"   ? Number(dbPort) : null,
        db_name:     dbType !== "none"    ? dbName   : null,
        db_user:     dbType === "mysql"   ? dbUser   : null,
        db_password: dbType === "mysql"   && dbPassword ? dbPassword : undefined,
        mongo_uri:   dbType === "mongodb" && mongoUri   ? mongoUri   : undefined,
      };
      if (mode === "add") {
        await createFirm(data);
        notify("Firm created", "success");
      } else {
        await updateFirm(firm.firm_id, data);
        notify("Firm updated", "success");
      }
      onSaved();
      onClose();
    } catch (err) {
      notify(err.response?.data?.detail || "Failed to save firm", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal title={mode === "add" ? "Add Firm" : "Edit Firm"} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === "add" && (
          <div>
            <label className={labelCls}>Firm ID <span className="text-gray-400">(lowercase, no spaces)</span></label>
            <input
              required
              value={firmId}
              onChange={(e) => setFirmId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
              placeholder="acme_corp"
              className={inputCls}
            />
          </div>
        )}
        {mode === "edit" && (
          <div>
            <label className={labelCls}>Firm ID</label>
            <input value={firmId} disabled className={`${inputCls} bg-gray-50 text-gray-400`} />
          </div>
        )}

        <div>
          <label className={labelCls}>Firm Name</label>
          <input required value={firmName} onChange={(e) => setFirmName(e.target.value)}
            placeholder="ACME Corp" className={inputCls} />
        </div>

        <div>
          <label className={labelCls}>Description</label>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)}
            rows={2} placeholder="What this firm does…"
            className={`${inputCls} resize-none`} />
        </div>

        <div>
          <label className={labelCls}>Database type</label>
          <div className="flex gap-5 mt-1">
            {[["none","No database"],["mysql","MySQL"],["mongodb","MongoDB"]].map(([val, label]) => (
              <label key={val} className="flex items-center gap-1.5 cursor-pointer text-sm text-gray-700">
                <input type="radio" checked={dbType === val} onChange={() => setDbType(val)}
                  className="text-blue-600" />
                {label}
              </label>
            ))}
          </div>
        </div>

        {dbType === "mysql" && (
          <div className="space-y-3 bg-gray-50 rounded-lg p-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Host</label>
                <input value={dbHost} onChange={(e) => setDbHost(e.target.value)}
                  placeholder="localhost" className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Port</label>
                <input type="number" value={dbPort} onChange={(e) => setDbPort(e.target.value)}
                  placeholder="3306" className={inputCls} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Database name</label>
                <input value={dbName} onChange={(e) => setDbName(e.target.value)}
                  placeholder="acme_db" className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>DB user</label>
                <input value={dbUser} onChange={(e) => setDbUser(e.target.value)}
                  placeholder="chatbot_ro" className={inputCls} />
              </div>
            </div>
            <div>
              <label className={labelCls}>
                Password{mode === "edit" && <span className="text-gray-400"> (leave blank to keep existing)</span>}
              </label>
              <input type="password" value={dbPassword} onChange={(e) => setDbPassword(e.target.value)}
                placeholder="••••••••" className={inputCls} />
            </div>
          </div>
        )}

        {dbType === "mongodb" && (
          <div>
            <label className={labelCls}>
              MongoDB URI{mode === "edit" && <span className="text-gray-400"> (leave blank to keep existing)</span>}
            </label>
            <input value={mongoUri} onChange={(e) => setMongoUri(e.target.value)}
              placeholder="mongodb+srv://user:pass@cluster.mongodb.net/db"
              className={inputCls} />
          </div>
        )}

        <div className="flex gap-2 pt-1">
          <button type="submit" disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            {loading ? "Saving…" : mode === "add" ? "Create firm" : "Update firm"}
          </button>
          <button type="button" onClick={onClose}
            className="border border-gray-300 text-gray-600 hover:bg-gray-50 text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ── Firms section ─────────────────────────────────────────────────────────────
function FirmsSection({ notify }) {
  const [firms,       setFirms]       = useState([]);
  const [modal,       setModal]       = useState(null); // null | "add" | firm object (edit)

  const load = () => getSuperAdminFirms().then(setFirms).catch(() => {});
  useEffect(() => { load(); }, []);

  const handleDelete = async (firm) => {
    if (!confirm(`Delete firm "${firm.firm_name}" and ALL its data? This cannot be undone.`)) return;
    try {
      await deleteFirm(firm.firm_id);
      notify(`"${firm.firm_name}" deleted`, "success");
      load();
    } catch (err) {
      notify(err.response?.data?.detail || "Delete failed", "error");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">Firms</h2>
        <button onClick={() => setModal("add")}
          className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
          + Add firm
        </button>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left pb-2 text-gray-500 font-medium">Firm</th>
            <th className="text-left pb-2 text-gray-500 font-medium">ID</th>
            <th className="text-left pb-2 text-gray-500 font-medium">DB</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Admins</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Users</th>
            <th className="pb-2" />
          </tr>
        </thead>
        <tbody>
          {firms.map((f) => (
            <tr key={f.firm_id} className="border-b border-gray-100">
              <td className="py-2 font-medium text-gray-700">{f.firm_name}</td>
              <td className="py-2 text-gray-400 font-mono text-xs">{f.firm_id}</td>
              <td className="py-2 text-gray-500">{f.db_type}</td>
              <td className="py-2 text-gray-500">{f.admin_count}</td>
              <td className="py-2 text-gray-500">{f.user_count}</td>
              <td className="py-2 text-right whitespace-nowrap">
                <button onClick={() => setModal(f)}
                  className="text-xs text-blue-600 hover:text-blue-800 mr-3 transition-colors">
                  Edit
                </button>
                <button onClick={() => handleDelete(f)}
                  className="text-xs text-red-400 hover:text-red-600 transition-colors">
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {firms.length === 0 && (
            <tr><td colSpan={6} className="py-4 text-gray-400 text-center">No firms yet</td></tr>
          )}
        </tbody>
      </table>

      {modal === "add" && (
        <FirmModal mode="add" onClose={() => setModal(null)} onSaved={load} notify={notify} />
      )}
      {modal && modal !== "add" && (
        <FirmModal mode="edit" firm={modal} onClose={() => setModal(null)} onSaved={load} notify={notify} />
      )}
    </div>
  );
}

// ── Admin modal ───────────────────────────────────────────────────────────────
function AdminModal({ mode, admin, firmsList, onClose, onSaved, notify }) {
  const [firmId,      setFirmId]      = useState(mode === "edit" ? admin.firm_id      : "");
  const [loginId,     setLoginId]     = useState(mode === "edit" ? admin.login_id     : "");
  const [displayName, setDisplayName] = useState(mode === "edit" ? (admin.display_name || "") : "");
  const [password,    setPassword]    = useState("");
  const [loading,     setLoading]     = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === "add") {
        await createSuperAdmin({ firm_id: firmId, login_id: loginId, display_name: displayName, password });
        notify("Admin created", "success");
      } else {
        await updateSuperAdmin(admin.user_id, { login_id: loginId, display_name: displayName, password: password || undefined });
        notify("Admin updated", "success");
      }
      onSaved();
      onClose();
    } catch (err) {
      notify(err.response?.data?.detail || "Failed to save admin", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal title={mode === "add" ? "Add Admin" : "Edit Admin"} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className={labelCls}>Firm</label>
          {mode === "add" ? (
            <select required value={firmId} onChange={(e) => setFirmId(e.target.value)} className={inputCls}>
              <option value="">Select firm</option>
              {firmsList.map((f) => <option key={f.firm_id} value={f.firm_id}>{f.firm_name}</option>)}
            </select>
          ) : (
            <input value={admin.firm_name} disabled className={`${inputCls} bg-gray-50 text-gray-400`} />
          )}
        </div>
        <div>
          <label className={labelCls}>Display name</label>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Jane Doe" className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Login ID</label>
          <input required value={loginId} onChange={(e) => setLoginId(e.target.value)}
            placeholder="admin_acme" className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>
            Password{mode === "edit" && <span className="text-gray-400"> (leave blank to keep existing)</span>}
          </label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            required={mode === "add"} placeholder="••••••••" className={inputCls} />
        </div>
        <div className="flex gap-2 pt-1">
          <button type="submit" disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            {loading ? "Saving…" : mode === "add" ? "Create admin" : "Update admin"}
          </button>
          <button type="button" onClick={onClose}
            className="border border-gray-300 text-gray-600 hover:bg-gray-50 text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ── Admins section ────────────────────────────────────────────────────────────
function AdminsSection({ notify }) {
  const [admins,    setAdmins]    = useState([]);
  const [firmsList, setFirmsList] = useState([]);
  const [modal,     setModal]     = useState(null);

  const load = () => {
    getSuperAdminAdmins().then(setAdmins).catch(() => {});
    getFirmsList().then(setFirmsList).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const handleDelete = async (admin) => {
    if (!confirm(`Delete admin "${admin.display_name || admin.login_id}"?`)) return;
    try {
      await deleteSuperAdmin(admin.user_id);
      notify("Admin deleted", "success");
      load();
    } catch (err) {
      notify(err.response?.data?.detail || "Delete failed", "error");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">Admins</h2>
        <button onClick={() => setModal("add")}
          className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
          + Add admin
        </button>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left pb-2 text-gray-500 font-medium">Name</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Login ID</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Firm</th>
            <th className="pb-2" />
          </tr>
        </thead>
        <tbody>
          {admins.map((a) => (
            <tr key={a.user_id} className="border-b border-gray-100">
              <td className="py-2 font-medium text-gray-700">{a.display_name || "—"}</td>
              <td className="py-2 text-gray-500 font-mono text-xs">{a.login_id}</td>
              <td className="py-2 text-gray-500">{a.firm_name}</td>
              <td className="py-2 text-right whitespace-nowrap">
                <button onClick={() => setModal(a)}
                  className="text-xs text-blue-600 hover:text-blue-800 mr-3 transition-colors">
                  Edit
                </button>
                <button onClick={() => handleDelete(a)}
                  className="text-xs text-red-400 hover:text-red-600 transition-colors">
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {admins.length === 0 && (
            <tr><td colSpan={4} className="py-4 text-gray-400 text-center">No admins yet</td></tr>
          )}
        </tbody>
      </table>

      {modal === "add" && (
        <AdminModal mode="add" firmsList={firmsList} onClose={() => setModal(null)} onSaved={load} notify={notify} />
      )}
      {modal && modal !== "add" && (
        <AdminModal mode="edit" admin={modal} firmsList={firmsList} onClose={() => setModal(null)} onSaved={load} notify={notify} />
      )}
    </div>
  );
}

// ── User edit modal ───────────────────────────────────────────────────────────
function EditUserModal({ user, onClose, onSaved, notify }) {
  const [loginId,     setLoginId]     = useState(user.login_id);
  const [displayName, setDisplayName] = useState(user.display_name || "");
  const [password,    setPassword]    = useState("");
  const [loading,     setLoading]     = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await updateSuperAdminUser(user.user_id, {
        login_id:     loginId,
        display_name: displayName,
        password:     password || undefined,
      });
      notify("User updated", "success");
      onSaved();
      onClose();
    } catch (err) {
      notify(err.response?.data?.detail || "Failed to update user", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal title="Edit User" onClose={onClose}>
      <p className="text-xs text-gray-400 mb-4">Firm: {user.firm_name}</p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className={labelCls}>Display name</label>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Jane Doe" className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Login ID</label>
          <input required value={loginId} onChange={(e) => setLoginId(e.target.value)}
            className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Password <span className="text-gray-400">(leave blank to keep existing)</span></label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••" className={inputCls} />
        </div>
        <div className="flex gap-2 pt-1">
          <button type="submit" disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            {loading ? "Saving…" : "Update user"}
          </button>
          <button type="button" onClick={onClose}
            className="border border-gray-300 text-gray-600 hover:bg-gray-50 text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ── Users section ─────────────────────────────────────────────────────────────
function UsersSection({ notify }) {
  const [users,       setUsers]       = useState([]);
  const [editingUser, setEditingUser] = useState(null);

  const load = () => getSuperAdminUsers().then(setUsers).catch(() => {});
  useEffect(() => { load(); }, []);

  const handleDelete = async (user) => {
    if (!confirm(`Delete user "${user.display_name || user.login_id}"?`)) return;
    try {
      await deleteSuperAdminUser(user.user_id);
      notify("User deleted", "success");
      load();
    } catch (err) {
      notify(err.response?.data?.detail || "Delete failed", "error");
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-800">Users</h2>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left pb-2 text-gray-500 font-medium">Name</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Login ID</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Firm</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Role</th>
            <th className="pb-2" />
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.user_id} className="border-b border-gray-100">
              <td className="py-2 font-medium text-gray-700">{u.display_name || "—"}</td>
              <td className="py-2 text-gray-500 font-mono text-xs">{u.login_id}</td>
              <td className="py-2 text-gray-500">{u.firm_name}</td>
              <td className="py-2 text-gray-400 text-xs">{u.role_name || "—"}</td>
              <td className="py-2 text-right whitespace-nowrap">
                <button onClick={() => setEditingUser(u)}
                  className="text-xs text-blue-600 hover:text-blue-800 mr-3 transition-colors">
                  Edit
                </button>
                <button onClick={() => handleDelete(u)}
                  className="text-xs text-red-400 hover:text-red-600 transition-colors">
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {users.length === 0 && (
            <tr><td colSpan={5} className="py-4 text-gray-400 text-center">No users yet</td></tr>
          )}
        </tbody>
      </table>

      {editingUser && (
        <EditUserModal
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSaved={load}
          notify={notify}
        />
      )}
    </div>
  );
}

// ── Main SuperAdmin page ───────────────────────────────────────────────────────
export default function SuperAdmin() {
  const [section, setSection] = useState("dashboard");
  const [toast,   setToast]   = useState({ msg: "", type: "" });
  const { logout }            = useAuth();
  const navigate              = useNavigate();

  const notify = (msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast({ msg: "", type: "" }), 3000);
  };

  const navItems = [
    { id: "dashboard", label: "Dashboard" },
    { id: "firms",     label: "Firms" },
    { id: "admins",    label: "Admins" },
    { id: "users",     label: "Users" },
  ];

  return (
    <div className="flex h-screen bg-gray-50">
      <Toast msg={toast.msg} type={toast.type} />

      {/* Left sidebar */}
      <aside className="w-52 bg-white border-r border-gray-200 flex flex-col fixed h-full z-10">
        <div className="p-4 border-b border-gray-200">
          <h1 className="font-semibold text-gray-800">Super Admin</h1>
          <p className="text-xs text-gray-400 mt-0.5">KT Vox Demo</p>
        </div>
        <nav className="flex-1 p-3 space-y-0.5">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setSection(item.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                section === item.id
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-800"
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="p-3 border-t border-gray-200">
          <button
            onClick={() => { logout(); navigate("/"); }}
            className="w-full text-left px-3 py-2 text-sm text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="ml-52 flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-8">
          {section === "dashboard" && <DashboardSection />}
          {section === "firms"     && <FirmsSection     notify={notify} />}
          {section === "admins"    && <AdminsSection     notify={notify} />}
          {section === "users"     && <UsersSection      notify={notify} />}
        </div>
      </main>
    </div>
  );
}
