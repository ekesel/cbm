import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useMappings, createMapping, activateMapping } from "../../hooks/useAdmin";

const Th = ({ children }: { children: React.ReactNode }) => <th style={{ textAlign: "left", padding: "10px 12px" }}>{children}</th>;
const Td = ({ children }: { children: React.ReactNode }) => <td style={{ padding: "10px 12px" }}>{children}</td>;

export default function AdminMappings() {
  const { rows, loading, err } = useMappings();
  const [busy, setBusy] = useState(false);

  async function clone(id: number) {
    setBusy(true);
    try {
      const res = await createMapping({ from_id: id });
      window.location.href = `/admin/mappings/${res.id}`;
    } finally { setBusy(false); }
  }
  async function activate(id: number) {
    setBusy(true);
    try {
      await activateMapping(id);
      window.location.reload();
    } finally { setBusy(false); }
  }
  async function createBlank() {
    setBusy(true);
    try {
      const res = await createMapping({ config: { states: {}, fields: {}, sla: { blocked_hours: 48 } } });
      window.location.href = `/admin/mappings/${res.id}`;
    } finally { setBusy(false); }
  }

  return (
    <div style={{ padding: 16 }}>
      <h2>Mapping Versions</h2>
      <div style={{ marginBottom: 12 }}>
        <button onClick={createBlank} disabled={busy}>New Blank</button>
      </div>
      {loading && <div>Loading…</div>}
      {err && <div style={{ color: "crimson" }}>{err}</div>}
      {!loading && !err && (
        <div style={{ overflow: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ background: "#fafafa" }}>
              <tr><Th>ID</Th><Th>Version</Th><Th>Active</Th><Th>Created</Th><Th>Updated</Th><Th>Actions</Th></tr>
            </thead>
            <tbody>
              {rows.map(v => (
                <tr key={v.id} style={{ borderTop: "1px solid #eee" }}>
                  <Td>#{v.id}</Td>
                  <Td>{v.version}</Td>
                  <Td>{String(v.active)}</Td>
                  <Td>{v.created_at}</Td>
                  <Td>{v.updated_at || "—"}</Td>
                  <Td style={{ display: "flex", gap: 8 }}>
                    <Link to={`/admin/mappings/${v.id}`}>Edit</Link>
                    {!v.active && <button onClick={()=>activate(v.id)} disabled={busy}>Activate</button>}
                    <button onClick={()=>clone(v.id)} disabled={busy}>Clone</button>
                  </Td>
                </tr>
              ))}
              {!rows.length && <tr><Td colSpan={6 as any}>No versions</Td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
