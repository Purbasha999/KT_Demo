import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import {
  getSchema, uploadSchema,
  getRoles, createRole, updateRole, deleteRole,
  getUsers, createUser, assignRole, deleteUser,
  getDocuments, uploadDocument, deleteDocument,
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
function CheckboxGroup({ label, allLabel, items, allChecked, selected, onToggleAll, onToggle, emptyMsg }) {
  return (
    <div>
      <label className="text-xs text-gray-500 mb-2 block">{label}</label>
      <label className="flex items-center gap-2 text-sm text-gray-700 mb-2 cursor-pointer select-none">
        <input type="checkbox" checked={allChecked}
          onChange={(e) => onToggleAll(e.target.checked)}
          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
        {allLabel}
      </label>
      {!allChecked && items.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pl-1">
          {items.map((item) => (
            <label key={item} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none">
              <input type="checkbox" checked={selected.includes(item)}
                onChange={() => onToggle(item)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
              {item}
            </label>
          ))}
        </div>
      )}
      {!allChecked && items.length === 0 && (
        <p className="text-xs text-gray-400 pl-1">{emptyMsg}</p>
      )}
    </div>
  );
}

const emptyValueRow  = () => ({ id: Date.now() + Math.random(), operator: "eq", value: "" });
const emptyAttribute = () => ({ id: Date.now() + Math.random(), column: "", values: [emptyValueRow()] });
const emptyTableRow  = () => ({ id: Date.now() + Math.random(), table: "", conditional: false, attributes: [emptyAttribute()] });

function Toggle({ on, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors focus:outline-none ${on ? "bg-blue-600" : "bg-gray-300"}`}
    >
      <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${on ? "translate-x-[18px]" : "translate-x-0.5"}`} />
    </button>
  );
}

function RolesTab({ notify, onRolesChange }) {
  const [roles, setRoles]               = useState([]);
  const [editingId, setEditingId]       = useState(null); // null = create mode, number = edit mode
  const [name, setName]                 = useState("");
  const [allTables, setAllTables]   = useState(false);
  const [tablePerms, setTablePerms] = useState([emptyTableRow()]);
  const [allDocs, setAllDocs]       = useState(true);
  const [selDocs, setSelDocs]       = useState([]);
  const [schemaData, setSchemaData] = useState([]); // full table objects with fields
  const [docList, setDocList]       = useState([]);
  const [loading, setLoading]       = useState(false);

  const load = () => getRoles().then((r) => { setRoles(r); onRolesChange(r); }).catch(() => {});

  useEffect(() => {
    load();
    getSchema().then((s) => setSchemaData(s.tables || [])).catch(() => {});
    getDocuments().then((d) => setDocList(d.map((doc) => doc.filename))).catch(() => {});
  }, []);

  // ── table-level helpers ──────────────────────────────────────────────────
  const addTableRow    = () => setTablePerms((p) => [...p, emptyTableRow()]);
  const removeTableRow = (id) => setTablePerms((p) => p.filter((r) => r.id !== id));
  const updateRow      = (id, field, val) =>
    setTablePerms((p) => p.map((r) => r.id === id ? { ...r, [field]: val } : r));
  // When the table changes, reset attributes so field dropdowns repopulate correctly
  const updateRowTable = (id, val) =>
    setTablePerms((p) => p.map((r) => r.id === id ? { ...r, table: val, attributes: [emptyAttribute()] } : r));

  // ── attribute helpers (one attribute = one column with ≥1 value rows) ──
  const addAttribute    = (tableId) =>
    setTablePerms((p) => p.map((r) => r.id === tableId
      ? { ...r, attributes: [...(r.attributes || []), emptyAttribute()] }
      : r));
  const removeAttribute = (tableId, attrId) =>
    setTablePerms((p) => p.map((r) => r.id === tableId
      ? { ...r, attributes: (r.attributes || []).filter((a) => a.id !== attrId) }
      : r));
  const updateAttribute = (tableId, attrId, field, val) =>
    setTablePerms((p) => p.map((r) => r.id === tableId
      ? { ...r, attributes: (r.attributes || []).map((a) => a.id === attrId ? { ...a, [field]: val } : a) }
      : r));

  // ── value helpers (one value row = one operator + value for an attribute) ──
  const addValue    = (tableId, attrId) =>
    setTablePerms((p) => p.map((r) => r.id === tableId
      ? { ...r, attributes: (r.attributes || []).map((a) => a.id === attrId
          ? { ...a, values: [...(a.values || []), emptyValueRow()] }
          : a) }
      : r));
  const removeValue = (tableId, attrId, valId) =>
    setTablePerms((p) => p.map((r) => r.id === tableId
      ? { ...r, attributes: (r.attributes || []).map((a) => a.id === attrId
          ? { ...a, values: (a.values || []).filter((v) => v.id !== valId) }
          : a) }
      : r));
  const updateValue = (tableId, attrId, valId, field, val) =>
    setTablePerms((p) => p.map((r) => r.id === tableId
      ? { ...r, attributes: (r.attributes || []).map((a) => a.id === attrId
          ? { ...a, values: (a.values || []).map((v) => v.id === valId ? { ...v, [field]: val } : v) }
          : a) }
      : r));

  const buildPayload = () => {
    if (allTables) return { allowed_tables: ["*"], row_filters: {} };
    const allowed_tables = [...new Set(tablePerms.map((r) => r.table).filter(Boolean))];
    const row_filters = {};
    const OP_MAP = { gt: "$gt", gte: "$gte", lt: "$lt", lte: "$lte", ne: "$ne" };

    tablePerms.forEach((row) => {
      if (!row.table || !row.conditional) return;
      if (!row_filters[row.table]) row_filters[row.table] = {};

      (row.attributes || []).forEach((attr) => {
        if (!attr.column) return;
        const validVals = (attr.values || []).filter((v) => v.value.trim());
        if (!validVals.length) return;
        const col = attr.column;

        // Equality values → stored as list (IN filter)
        const eqVals = validVals.filter((v) => v.operator === "eq").map((v) => v.value.trim());
        if (eqVals.length) {
          row_filters[row.table][col] = eqVals;
          return; // equality takes precedence for this attribute
        }

        // Operator values → stored as operator dict
        const opDict = {};
        validVals.forEach((v) => {
          const op = OP_MAP[v.operator];
          if (op) opDict[op] = v.value.trim();
        });
        if (Object.keys(opDict).length) {
          row_filters[row.table][col] = opDict;
        }
      });
    });
    return { allowed_tables, row_filters };
  };

  const toggleDoc = (d) => setSelDocs((p) => p.includes(d) ? p.filter((x) => x !== d) : [...p, d]);

  const resetForm = () => {
    setEditingId(null);
    setName(""); setTablePerms([emptyTableRow()]); setAllTables(false);
    setSelDocs([]); setAllDocs(true);
  };

  const loadRoleForEdit = (role) => {
    setEditingId(role.role_id);
    setName(role.role_name);
    const isAll = role.allowed_tables[0] === "*";
    setAllTables(isAll);
    if (!isAll) {
      const OP_REV = { "$gt": "gt", "$gte": "gte", "$lt": "lt", "$lte": "lte", "$ne": "ne" };
      const perms = role.allowed_tables.map((tableName) => {
        const filters = role.row_filters?.[tableName];
        if (!filters || Object.keys(filters).length === 0) {
          return { id: Date.now() + Math.random(), table: tableName, conditional: false, attributes: [emptyAttribute()] };
        }
        // Rebuild attributes: each column in the filter → one attribute group
        const attributes = Object.entries(filters).map(([col, rule]) => {
          let values;
          if (Array.isArray(rule)) {
            values = rule.map((val) => ({ id: Date.now() + Math.random(), operator: "eq", value: String(val) }));
          } else if (rule && typeof rule === "object") {
            values = Object.entries(rule).map(([op, val]) => ({
              id: Date.now() + Math.random(), operator: OP_REV[op] || "eq", value: String(val),
            }));
          } else if (rule != null) {
            values = [{ id: Date.now() + Math.random(), operator: "eq", value: String(rule) }];
          } else {
            values = [emptyValueRow()];
          }
          return { id: Date.now() + Math.random(), column: col, values };
        });
        return {
          id: Date.now() + Math.random(), table: tableName, conditional: true,
          attributes: attributes.length > 0 ? attributes : [emptyAttribute()],
        };
      });
      setTablePerms(perms.length > 0 ? perms : [emptyTableRow()]);
    } else {
      setTablePerms([emptyTableRow()]);
    }
    const isAllDocs = role.allowed_documents[0] === "*";
    setAllDocs(isAllDocs);
    setSelDocs(isAllDocs ? [] : role.allowed_documents);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDeleteRole = async (role) => {
    if (!confirm(`Delete role "${role.role_name}"? This cannot be undone.`)) return;
    try {
      await deleteRole(role.role_id);
      notify(`Role "${role.role_name}" deleted`, "success");
      if (editingId === role.role_id) resetForm();
      load();
    } catch (e) {
      notify(e.response?.data?.detail || "Failed to delete role", "error");
    }
  };

  const save = async () => {
    setLoading(true);
    try {
      const { allowed_tables, row_filters } = buildPayload();
      const payload = {
        role_name:         name,
        allowed_tables,
        allowed_documents: allDocs ? ["*"] : selDocs,
        row_filters,
      };
      if (editingId !== null) {
        await updateRole(editingId, payload);
        notify(`Role "${name}" updated`, "success");
      } else {
        await createRole(payload);
        notify(`Role "${name}" saved`, "success");
      }
      resetForm();
      load();
    } catch (e) {
      notify(e.response?.data?.detail || "Failed to save role", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-50 rounded-xl p-4 border border-gray-200 space-y-4">
        <h3 className="text-sm font-medium text-gray-700">
          {editingId !== null ? "Edit role" : "Create role"}
        </h3>

        {/* Role name */}
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Role name</label>
          <input value={name} onChange={(e) => setName(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="e.g. CEO, HR Head" />
        </div>

        {/* Table permissions */}
        <div>
          <label className="text-xs text-gray-500 mb-2 block">Table permissions</label>

          <label className="flex items-center gap-2 text-sm text-gray-700 mb-3 cursor-pointer select-none">
            <input type="checkbox" checked={allTables}
              onChange={(e) => setAllTables(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
            All tables (*)
          </label>

          {!allTables && (
            <div className="space-y-2">
              {tablePerms.map((row) => (
                <div key={row.id} className="border border-gray-200 rounded-lg p-3 bg-white space-y-2">

                  {/* Table dropdown + toggle + remove */}
                  <div className="flex items-center gap-2">
                    <select
                      value={row.table}
                      onChange={(e) => updateRowTable(row.id, e.target.value)}
                      className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Select table</option>
                      {schemaData.map((t) => <option key={t.name} value={t.name}>{t.name}</option>)}
                    </select>

                    <span className="text-xs text-gray-400 whitespace-nowrap">Conditional</span>
                    <Toggle
                      on={row.conditional}
                      onToggle={() => updateRow(row.id, "conditional", !row.conditional)}
                    />

                    {tablePerms.length > 1 && (
                      <button type="button" onClick={() => removeTableRow(row.id)}
                        className="text-gray-300 hover:text-red-400 text-xl leading-none transition-colors">
                        ×
                      </button>
                    )}
                  </div>

                  {/* Conditional filters — grouped by attribute */}
                  {row.conditional && (() => {
                    const fields = schemaData.find((t) => t.name === row.table)?.fields || [];
                    return (
                      <div className="pt-2 space-y-3 border-t border-gray-100">
                        {(row.attributes || []).map((attr) => (
                          <div key={attr.id} className="space-y-1">
                            {/* Attribute selector row */}
                            <div className="flex items-center gap-1.5">
                              {fields.length > 0 ? (
                                <select
                                  value={attr.column}
                                  onChange={(e) => updateAttribute(row.id, attr.id, "column", e.target.value)}
                                  className="flex-1 min-w-0 border border-gray-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                                >
                                  <option value="">Select attribute</option>
                                  {fields.map((f) => <option key={f.name} value={f.name}>{f.name}</option>)}
                                </select>
                              ) : (
                                <input
                                  value={attr.column}
                                  onChange={(e) => updateAttribute(row.id, attr.id, "column", e.target.value)}
                                  placeholder="attribute"
                                  className="flex-1 min-w-0 border border-gray-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                              )}
                              {(row.attributes || []).length > 1 && (
                                <button type="button" onClick={() => removeAttribute(row.id, attr.id)}
                                  className="text-gray-300 hover:text-red-400 text-xl leading-none transition-colors flex-shrink-0">
                                  ×
                                </button>
                              )}
                            </div>

                            {/* Value rows for this attribute */}
                            <div className="pl-4 space-y-1">
                              {(attr.values || []).map((val) => (
                                <div key={val.id} className="flex items-center gap-1.5">
                                  <select
                                    value={val.operator}
                                    onChange={(e) => updateValue(row.id, attr.id, val.id, "operator", e.target.value)}
                                    className="border border-gray-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 flex-shrink-0"
                                  >
                                    <option value="eq">equals</option>
                                    <option value="gt">greater than</option>
                                    <option value="gte">≥ gte</option>
                                    <option value="lt">less than</option>
                                    <option value="lte">≤ lte</option>
                                    <option value="ne">not equals</option>
                                  </select>
                                  <input
                                    value={val.value}
                                    onChange={(e) => updateValue(row.id, attr.id, val.id, "value", e.target.value)}
                                    placeholder="value"
                                    className="flex-1 min-w-0 border border-gray-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                                  />
                                  {(attr.values || []).length > 1 && (
                                    <button type="button" onClick={() => removeValue(row.id, attr.id, val.id)}
                                      className="text-gray-300 hover:text-red-400 text-xl leading-none transition-colors flex-shrink-0">
                                      ×
                                    </button>
                                  )}
                                </div>
                              ))}
                              <button type="button" onClick={() => addValue(row.id, attr.id)}
                                className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 transition-colors">
                                <span className="text-sm font-bold">+</span> Add value
                              </button>
                            </div>
                          </div>
                        ))}

                        {/* Add attribute button */}
                        <button type="button" onClick={() => addAttribute(row.id)}
                          className="text-xs text-indigo-600 hover:text-indigo-700 flex items-center gap-1 transition-colors mt-1">
                          <span className="text-sm font-bold">+</span> Add attribute
                        </button>
                      </div>
                    );
                  })()}
                </div>
              ))}

              {schemaData.length === 0 && (
                <p className="text-xs text-gray-400 pl-1">Upload a schema first to see available tables.</p>
              )}
              <button type="button" onClick={addTableRow}
                className="w-full border border-dashed border-gray-300 rounded-lg py-2 text-sm text-gray-400 hover:border-blue-400 hover:text-blue-500 transition-colors flex items-center justify-center gap-1">
                <span className="text-base font-bold">+</span> Add table
              </button>
            </div>
          )}
        </div>

        {/* Document permissions — unchanged */}
        <CheckboxGroup
          label="Allowed documents"
          allLabel="All documents (*)"
          items={docList}
          allChecked={allDocs}
          selected={selDocs}
          onToggleAll={(v) => { setAllDocs(v); setSelDocs([]); }}
          onToggle={toggleDoc}
          emptyMsg="Upload PDFs first to restrict document access."
        />

        <div className="flex gap-2">
          <button onClick={save} disabled={loading || !name}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            {loading ? "Saving…" : editingId !== null ? "Update role" : "Save role"}
          </button>
          {editingId !== null && (
            <button onClick={resetForm}
              className="border border-gray-300 text-gray-600 hover:bg-gray-50 text-sm font-medium px-4 py-2 rounded-lg transition-colors">
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* Roles table */}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left pb-2 text-gray-500 font-medium">Role</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Tables</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Documents</th>
            <th className="pb-2" />
          </tr>
        </thead>
        <tbody>
          {roles.map((r) => (
            <tr key={r.role_id} className={`border-b border-gray-100 ${editingId === r.role_id ? "bg-blue-50" : ""}`}>
              <td className="py-2 font-medium text-gray-700">{r.role_name}</td>
              <td className="py-2 text-gray-500 text-xs">
                {Array.isArray(r.allowed_tables) ? r.allowed_tables.join(", ") : r.allowed_tables}
                {r.row_filters && Object.keys(r.row_filters).length > 0 && (
                  <span className="ml-1.5 text-orange-500 font-medium">(filtered)</span>
                )}
              </td>
              <td className="py-2 text-gray-500 text-xs">
                {Array.isArray(r.allowed_documents) ? r.allowed_documents.join(", ") : (r.allowed_documents || "*")}
              </td>
              <td className="py-2 text-right whitespace-nowrap">
                <button onClick={() => loadRoleForEdit(r)}
                  className="text-xs text-blue-600 hover:text-blue-800 mr-3 transition-colors">
                  Edit
                </button>
                <button onClick={() => handleDeleteRole(r)}
                  className="text-xs text-red-400 hover:text-red-600 transition-colors">
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {roles.length === 0 && (
            <tr><td colSpan={4} className="py-4 text-gray-400 text-center">No roles yet</td></tr>
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

  const handleDeleteUser = async (user) => {
    if (!confirm(`Delete user "${user.display_name || user.login_id}"? This cannot be undone.`)) return;
    try {
      await deleteUser(user.user_id);
      notify("User deleted", "success");
      load();
    } catch (e) {
      notify(e.response?.data?.detail || "Failed to delete user", "error");
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
            <th className="pb-2" />
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
              <td className="py-2 text-right">
                <button onClick={() => handleDeleteUser(u)}
                  className="text-xs text-red-400 hover:text-red-600 transition-colors">
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {users.length === 0 && (
            <tr><td colSpan={4} className="py-4 text-gray-400 text-center">No users yet</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ── Documents tab ──────────────────────────────────────────────────────────
function DocumentsTab({ notify }) {
  const [docs, setDocs]           = useState([]);
  const [loading, setLoading]     = useState(false);
  const [uploading, setUploading] = useState(false);
  const [description, setDescription] = useState("");
  const [pendingFile, setPendingFile] = useState(null);

  const load = () => getDocuments().then(setDocs).catch(() => {});

  useEffect(() => { load(); }, []);

  const handleFileChange = (e) => {
    setPendingFile(e.target.files?.[0] || null);
  };

  const handleUpload = async () => {
    if (!pendingFile) return;
    setUploading(true);
    try {
      const result = await uploadDocument(pendingFile, true, description);
      notify(`"${result.filename}" ingested — ${result.chunks_ingested} chunks`, "success");
      setPendingFile(null);
      setDescription("");
      load();
    } catch (err) {
      notify(err.response?.data?.detail || "Upload failed", "error");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (filename) => {
    if (!confirm(`Delete "${filename}"?`)) return;
    setLoading(true);
    try {
      await deleteDocument(filename);
      notify(`"${filename}" deleted`, "success");
      load();
    } catch (err) {
      notify(err.response?.data?.detail || "Delete failed", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-50 rounded-xl p-4 border border-gray-200 space-y-3">
        <h3 className="text-sm font-medium text-gray-700">Upload PDF</h3>
        <p className="text-xs text-gray-500">
          PDFs are chunked and embedded for RAG. Uploading the same filename replaces existing chunks.
        </p>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">File</label>
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            disabled={uploading}
            className="block text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 disabled:opacity-50"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Description (optional)</label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. Q1 2025 Financial Report"
            disabled={uploading}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          />
        </div>
        <button
          onClick={handleUpload}
          disabled={uploading || !pendingFile}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          {uploading ? "Uploading…" : "Upload"}
        </button>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left pb-2 text-gray-500 font-medium">Filename</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Description</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Chunks</th>
            <th className="text-left pb-2 text-gray-500 font-medium">Uploaded</th>
            <th className="pb-2" />
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.filename} className="border-b border-gray-100">
              <td className="py-2 font-mono text-xs text-gray-700">{d.filename}</td>
              <td className="py-2 text-gray-500 text-xs">{d.description || "—"}</td>
              <td className="py-2 text-gray-500">{d.chunks_count}</td>
              <td className="py-2 text-gray-400 text-xs">
                {new Date(d.uploaded_at).toLocaleString()}
              </td>
              <td className="py-2 text-right">
                <button
                  onClick={() => handleDelete(d.filename)}
                  disabled={loading}
                  className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50 transition-colors"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {docs.length === 0 && (
            <tr><td colSpan={5} className="py-4 text-gray-400 text-center">No documents uploaded yet</td></tr>
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
          tabs={["Schema", "Roles", "Users", "Documents"]}
          active={tab}
          onChange={setTab}
        />
        {tab === "Schema"    && <SchemaTab    notify={notify} />}
        {tab === "Roles"     && <RolesTab     notify={notify} onRolesChange={setRoles} />}
        {tab === "Users"     && <UsersTab     roles={roles} notify={notify} />}
        {tab === "Documents" && <DocumentsTab notify={notify} />}
      </main>
    </div>
  );
}
