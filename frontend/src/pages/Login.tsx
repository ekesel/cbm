import React, { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

export default function Login() {
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");
  const nav = useNavigate();
  const loc = useLocation() as any;
  const { login, loading, error } = useAuth();

  const doLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await login(id, pw);
    if (ok) {
      const dest = loc.state?.from || "/dashboard";
      nav(dest, { replace: true });
    }
  };

  return (
    <div style={{maxWidth:360, margin:"80px auto"}}>
      <h1>Sign in</h1>
      <form onSubmit={doLogin} style={{display:"grid", gap:12, marginTop:12}}>
        <input placeholder="Email or username" value={id} onChange={(e)=>setId(e.target.value)} />
        <input placeholder="Password" type="password" value={pw} onChange={(e)=>setPw(e.target.value)} />
        <button disabled={loading}>{loading ? "Signing in..." : "Sign in"}</button>
        {error && <div style={{color:"crimson"}}>{error}</div>}
      </form>
      <p style={{marginTop:8, color:"#666"}}>Backend: {import.meta.env.VITE_API_BASE}</p>
    </div>
  );
}
