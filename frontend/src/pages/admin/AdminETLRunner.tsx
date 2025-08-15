import React, { useEffect, useState } from "react";
import { useBoards, listJobs, runETL } from "../../hooks/useAdmin";

const Th = ({ children }: { children: React.ReactNode }) => <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, fontSize: 13 }}>{children}</th>;
const Td = ({ children, mono=false }: { children: React.ReactNode; mono?: boolean }) =>
  <td style={{ padding: "10px 12px", fontFamily: mono ? "ui-monospace, SFMono-Regular, Menlo, monospace" : undefined }}>{children}</td>;

export default function AdminETLRunner() {
  const { rows: boards, loading } = useBoards();
  const [boardId, setBoardId] = useState<number | undefined>(undefined);
  const [stages, setStages] = useState<string[]>(["fetch","normalize","validate","snapshot"]);
  const [date, setDate] = useState<string>(""); // YYYY-MM-DD
  const [busy, setBusy] = useState(false);
  const [jobs, setJobs] = useState<any[]>([]);

  useEffect(() => {
    if (!boardId) return;
    (async () => {
      const j = await listJobs(boardId, 20, 0);
      setJobs(j.results || []);
    })();
  }, [boardId]);

  function toggleStage(s: string) {
    setStages((prev) => prev.includes(s) ? prev.filter(x=>x!==s) : [...prev, s]);
  }

  async function run() {
    if (!boardId) { alert("Choose a board"); return; }
    setBusy(true);
    try {
      const payloadDate = date ? date : undefined;
      const res = await runETL(boardId, stages, "v1", payloadDate);
      alert(`Enqueued task ${res.task_id}`);
      const j = await listJobs(boardId, 20, 0);
      setJobs(j.results || []);
    } catch { alert("Failed to run ETL"); }
    finally { setBusy(false); }
  }

  return (
    <div style={{ padding: 16, display: "grid", gap: 12 }}>
      <h2>ETL Runner</h2>

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 12, maxWidth: 720 }}>
        <label>Board
          <select value={boardId ?? ""} onChange={e=>setBoardId(Number(e.target.value) || undefined)}>
            <option value="">— select —</option>
            {!loading && boards.map(b => <option key={b.id} value={b.id}>{`#${b.id} — ${b.name}`}</option>)}
          </select>
        </label>

        <label>Stages</label>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {["fetch","normalize","validate","snapshot"].map(s => (
            <label key={s} style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
              <input type="checkbox" checked={stages.includes(s)} onChange={()=>toggleStage(s)} /> {s}
            </label>
          ))}
        </div>

        <label>Snapshot date (optional, YYYY-MM-DD)
          <input placeholder="YYYY-MM-DD" value={date} onChange={e=>setDate(e.target.value)} />
        </label>

        <button onClick={run} disabled={busy}>{busy ? "Running…" : "Run ETL"}</button>
      </div>

      <section style={{ border: "1px solid #eee", borderRadius: 8 }}>
        <div style={{ padding: "8px 12px", borderBottom: "1px solid #eee" }}>
          <h3 style={{ margin: 0 }}>Recent Jobs</h3>
        </div>
        <div style={{ overflow: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ background: "#fafafa" }}>
              <tr><Th>ID</Th><Th>Stage</Th><Th>Status</Th><Th>Task</Th><Th>Created</Th><Th>Started</Th><Th>Finished</Th></tr>
            </thead>
            <tbody>
              {jobs.map((j:any) => (
                <tr key={j.id} style={{ borderTop: "1px solid #f0f0f0" }}>
                  <Td>#{j.id}</Td>
                  <Td>{j.stage}</Td>
                  <Td>{j.status}</Td>
                  <Td mono>{j.task_id || "—"}</Td>
                  <Td>{j.created_at}</Td>
                  <Td>{j.started_at || "—"}</Td>
                  <Td>{j.finished_at || "—"}</Td>
                </tr>
              ))}
              {!jobs.length && <tr><Td colSpan={7 as any}>No jobs</Td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
