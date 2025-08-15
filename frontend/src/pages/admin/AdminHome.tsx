import React from "react";
import { Link } from "react-router-dom";

export default function AdminHome() {
  return (
    <div style={{ padding: 16, display: "grid", gap: 12 }}>
      <h1>Admin</h1>
      <ul>
        <li><Link to="/admin/boards">Boards</Link></li>
        <li><Link to="/admin/mappings">Mapping Versions</Link></li>
        <li><Link to="/admin/etl">ETL Runner</Link></li>
      </ul>
      <p style={{ color: "#666" }}>Access is restricted by backend roles (PROCESS/CTO/ADMIN).</p>
    </div>
  );
}
