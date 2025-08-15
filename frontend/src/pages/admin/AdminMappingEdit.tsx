import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { fetchMapping, saveMapping, validateMapping, activateMapping } from "../../hooks/useAdmin";

export default function AdminMappingEdit() {
  const { mappingId } = useParams();
  const id = Number(mappingId);
  const nav = useNavigate();

  const [title, setTitle] = useState<string>("");
  const [text, setText] = useState<string>("{}");
  const [active, setActive] = useState<boolean>(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[] | null>(null);
  const [warnings, setWarnings] = useState<string[] | null>(null);

  useEffect(() => {
    let on = true;
    setLoading(true);
    fetchMapping(id)
      .then((m) => {
        if (!on) return;
        setTitle(`${m.version} ${m.active ? "(active)" : ""}`);
        setActive(m.active);
        setText(JSON.stringify(m.config ?? {}, null, 2));
      })
      .catch(() => alert("Failed to load mapping"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [id]);

  const prettify = () => {
    try { setText(JSON.stringify(JSON.parse(text), null, 2)); } catch { alert("Invalid JSON"); }
  };

  const doValidate = async () => {
    try {
      const obj = JSON.parse(text);
      const res = await validateMapping(id, obj);
      setErrors(res.errors || []);
      setWarnings(res.warnings || []);
      if (!res.errors?.length) alert("Looks good!");
    } catch { alert("Validation failed (invalid JSON?)"); }
  };

  const save = async () => {
    setBusy(true);
    try { 
      const obj = JSON.parse(text);
      await saveMapping(id, obj);
      alert("Saved");
    } catch { alert("Save failed"); }
    finally { setBusy(false); }
  };

  const activate = async () => {
    if (!confirm("Activate this mapping version?")) return;
    setBusy(true);
    try { await activateMapping(id); setActive(true); alert("Activated"); }
    catch { alert("Activate failed"); }
    finally { setBusy(false); }
  };

  if (loading) return <div style={{ padding: 16 }}>Loading…</div>;

  return (
    <div style={{ padding: 16, display: "grid", gap: 12 }}>
      <h2>Mapping #{id} — {title}</h2>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button onClick={prettify}>Prettify</button>
        <button onClick={doValidate}>Validate</button>
        <button onClick={save} disabled={busy}>Save</button>
        <button onClick={activate} disabled={busy || active}>Activate</button>
        <button onClick={()=>nav(-1)}>Back</button>
      </div>

      <textarea
        value={text}
        onChange={e=>setText(e.target.value)}
        rows={28}
        style={{ width: "100%", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" }}
      />

      {(errors || warnings) && (
        <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
          <h3 style={{ marginTop: 0 }}>Validation</h3>
          {errors?.length ? (<>
            <div style={{ color: "crimson", fontWeight: 600 }}>Errors</div>
            <ul>{errors.map((e,i)=><li key={i}>{e}</li>)}</ul>
          </>) : <div>No blocking errors</div>}
          {warnings?.length ? (<>
            <div style={{ color: "#8a5a00", fontWeight: 600 }}>Warnings</div>
            <ul>{warnings.map((w,i)=><li key={i}>{w}</li>)}</ul>
          </>) : null}
        </div>
      )}
    </div>
  );
}
