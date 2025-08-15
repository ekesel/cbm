import React from "react";
import { Link } from "react-router-dom";
import { useBoards } from "../../hooks/useAdmin";

const Th = ({ children }: { children: React.ReactNode }) => <th style={{ textAlign: "left", padding: "10px 12px" }}>{children}</th>;
const Td = ({ children }: { children: React.ReactNode }) => <td style={{ padding: "10px 12px" }}>{children}</td>;

export default function AdminBoards() {
  const { rows, loading, err } = useBoards();
  return (
    <div style={{ padding: 16 }}>
      <h2>Boards</h2>
      {loading && <div>Loading…</div>}
      {err && <div style={{ color: "crimson" }}>{err}</div>}
      {!loading && !err && (
        <div style={{ overflow: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ background: "#fafafa" }}>
              <tr><Th>ID</Th><Th>Name</Th><Th>Source</Th><Th>Client</Th><Th>Active</Th><Th>Actions</Th></tr>
            </thead>
            <tbody>
              {rows.map(b => (
                <tr key={b.id} style={{ borderTop: "1px solid #eee" }}>
                  <Td>#{b.id}</Td>
                  <Td>{b.name}</Td>
                  <Td>{b.source || "—"}</Td>
                  <Td>{b.client_id || "—"}</Td>
                  <Td>{String(b.is_active ?? true)}</Td>
                  <Td><Link to={`/admin/boards/${b.id}`}>Edit</Link></Td>
                </tr>
              ))}
              {!rows.length && <tr><Td colSpan={6 as any}>No boards</Td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
