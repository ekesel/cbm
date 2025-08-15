import React from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

export default function NavBar() {
  const { isAuthed, logout } = useAuth();
  return (
    <nav style={{display:"flex", alignItems:"center", gap:12, padding:"10px 16px", borderBottom:"1px solid #eee"}}>
      <Link to="/">Home</Link>
      <Link to="/dashboard">Dashboard</Link>
      <Link to="/teams/1/dashboard">Team 1</Link>
      <Link to="/boards/1/compliance">Compliance</Link>
      <Link to="/me/dashboard">My Dashboard</Link>
      <Link to="/admin">Admin</Link>
      <div style={{marginLeft:"auto"}}>
        {isAuthed ? (
          <button onClick={logout}>Logout</button>
        ) : (
          <Link to="/login">Login</Link>
        )}
      </div>
    </nav>
  );
}
