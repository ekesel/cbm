import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { BoardRow, fetchBoard, updateBoard } from "../../hooks/useAdmin";

export default function AdminBoardEdit() {
  const { boardId } = useParams();
  const id = Number(boardId);
  const nav = useNavigate();

  const [data, setData] = useState<BoardRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [metaText, setMetaText] = useState<string>("{}");

  useEffect(() => {
    let on = true;
    setLoading(true);
    fetchBoard(id)
      .then((d) => {
        if (!on) return;
        setData(d);
        setMetaText(JSON.stringify(d.meta ?? {}, null, 2));
      })
      .catch(() => on && setErr("Failed to load board"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [id]);

  async function save() {
    if (!data) return;
    setSaving(true);
    try {
      let meta: any = {};
      try { meta = JSON.parse(metaText || "{}"); } catch {
        alert("Meta is not valid JSON");
        setSaving(false);
        return;
      }
      const patch = { name: data.name, client_id: data.client_id, is_active: data.is_active, meta };
      const res = await updateBoard(id, patch);
      setData(res);
      alert("Saved");
    } catch {
      alert("Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div style={{ padding: 16 }}>Loading…</div>;
  if (err || !data)   return <div style={{ padding: 16, color: "crimson" }}>{err || "Not found"}</div>;

  return (
    <div style={{ padding: 16, display: "grid", gap: 12 }}>
      <h2>Board #{id} — {data.name}</h2>

      <label>Name
        <input value={data.name || ""} onChange={e=>setData({...data, name: e.target.value})} />
      </label>

      <label>Client ID
        <input value={data.client_id || ""} onChange={e=>setData({...data, client_id: e.target.value})} />
      </label>

      <label>Active
        <input type="checkbox" checked={Boolean(data.is_active ?? true)} onChange={e=>setData({...data, is_active: e.target.checked})} />
      </label>

      <label>Meta (JSON)
        <textarea value={metaText} onChange={e=>setMetaText(e.target.value)} rows={14} style={{ width: "100%", fontFamily: "ui-monospace, monospace" }} />
      </label>

      <div style={{ display: "flex", gap: 8 }}>
        <button disabled={saving} onClick={save}>{saving ? "Saving…" : "Save"}</button>
        <button onClick={()=>nav(-1)}>Back</button>
      </div>
    </div>
  );
}
