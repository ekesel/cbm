import React, { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { subDays, format } from "date-fns";
import { useCompliance, useRemediationList, remediationAck, remediationAssign, remediationResolve, remediationSnooze } from "../hooks/useCompliance";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
    <div style={{ color: "#666", fontSize: 12 }}>{title}</div>
    <div>{children}</div>
  </div>;
}
function Th({ children }: { children: React.ReactNode }) {
  return <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, fontSize: 13 }}>{children}</th>;
}
function Td({ children, mono=false }: { children: React.ReactNode; mono?: boolean }) {
  return <td style={{ padding: "10px 12px", fontFamily: mono ? "ui-monospace, SFMono-Regular, Menlo, monospace" : undefined }}>{children}</td>;
}

export default function ComplianceDashboard() {
  const { boardId: boardIdParam } = useParams();
  const boardId = Number(boardIdParam);
  const [range, setRange] = useState<{start: Date; end: Date}>(() => {
    const end = new Date();
    const start = subDays(end, 29);
    return { start, end };
  });

  // filters for table
  const [rule, setRule] = useState<string>("");
  const [owner, setOwner] = useState<string>("");
  const [snoozed, setSnoozed] = useState<"all"|"yes"|"no">("all");
  const [search, setSearch] = useState<string>("");
  const [ordering, setOrdering] = useState<string>("-updated_at");
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const snoozedFlag = useMemo(() => (snoozed === "all" ? null : snoozed === "yes"), [snoozed]);

  const { data: snap, loading: snapLoading } = useCompliance(boardId, range.start, range.end);
  const { rows, total, loading: listLoading } = useRemediationList({
    boardId, rule: rule || undefined, owner: owner || undefined, snoozed: snoozedFlag,
    status: "OPEN", limit: pageSize, offset: page * pageSize, search, ordering
  });

  // quick actions
  async function doAck(id: number) {
    await remediationAck(id);
    // naive refresh
    window.location.reload();
  }
  async function doResolve(id: number) {
    await remediationResolve(id);
    window.location.reload();
  }
  async function doSnooze(id: number) {
    const until = prompt("Snooze until (ISO, e.g., 2025-08-20T09:00:00Z):");
    if (!until) return;
    await remediationSnooze(id, until);
    window.location.reload();
  }
  async function doAssign(id: number) {
    const who = prompt("Assign to (email/username):");
    if (!who) return;
    await remediationAssign(id, who);
    window.location.reload();
  }

  return (
    <div style={{ padding: 16, display: "grid", gap: 16 }}>
      <header>
        <h1 style={{ fontSize: 22, marginBottom: 6 }}>Board {boardId} — Compliance</h1>
        <div style={{ color: "#666" }}>
          Window: {format(range.start, "yyyy-MM-dd")} → {format(range.end, "yyyy-MM-dd")}
        </div>
      </header>

      {/* Snapshot cards */}
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
        <Card title="Open remediation tickets">
          <b style={{ fontSize: 22 }}>{snapLoading ? "…" : snap?.total_open ?? "—"}</b>
        </Card>
        <Card title="Silenced (snoozed)">
          <b style={{ fontSize: 22 }}>{snapLoading ? "…" : snap?.silenced_open ?? "—"}</b>
        </Card>
        <Card title="Resolved (last 7d)">
          <b style={{ fontSize: 22 }}>{snapLoading ? "…" : snap?.recent_resolved_7d ?? "—"}</b>
        </Card>
        <Card title="Aging (0–2 / 3–5 / 6–10 / 10+)">
          <b style={{ fontSize: 22 }}>
            {snapLoading ? "…" :
              `${snap?.aging_buckets["0_2d"] ?? 0} / ${snap?.aging_buckets["3_5d"] ?? 0} / ${snap?.aging_buckets["6_10d"] ?? 0} / ${snap?.aging_buckets["gt_10d"] ?? 0}`
            }
          </b>
        </Card>
      </section>

      {/* By-rule breakdown */}
      <section style={{ border: "1px solid #eee", borderRadius: 8 }}>
        <div style={{ padding: "8px 12px", borderBottom: "1px solid #eee", display: "flex", alignItems: "center", gap: 8 }}>
          <h3 style={{ margin: 0 }}>Open by Rule</h3>
        </div>
        <div style={{ overflow: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ background: "#fafafa" }}><tr><Th>Rule</Th><Th>Count</Th></tr></thead>
            <tbody>
              {(snap?.by_rule || []).map(r => (
                <tr key={r.rule_code} style={{ borderTop: "1px solid #f0f0f0" }}>
                  <Td mono>{r.rule_code}</Td>
                  <Td>{r.count}</Td>
                </tr>
              ))}
              {!snap?.by_rule?.length && !snapLoading && (
                <tr><Td colSpan={2 as any}>No open tickets 🎉</Td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Filters */}
      <section style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 12, color: "#666" }}>Rule</div>
            <input value={rule} onChange={e=>setRule(e.target.value)} placeholder="e.g., MISSING_POINTS" />
          </div>
          <div>
            <div style={{ fontSize: 12, color: "#666" }}>Owner</div>
            <input value={owner} onChange={e=>setOwner(e.target.value)} placeholder="email/username" />
          </div>
          <div>
            <div style={{ fontSize: 12, color: "#666" }}>Snoozed</div>
            <select value={snoozed} onChange={e=>setSnoozed(e.target.value as any)}>
              <option value="all">All</option>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, color: "#666" }}>Search</div>
            <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="message, rule, owner..." style={{ width: "100%" }} />
          </div>
          <div>
            <div style={{ fontSize: 12, color: "#666" }}>Sort</div>
            <select value={ordering} onChange={e=>setOrdering(e.target.value)}>
              <option value="-updated_at">Updated ↓</option>
              <option value="updated_at">Updated ↑</option>
              <option value="-created_at">Created ↓</option>
              <option value="created_at">Created ↑</option>
              <option value="-resolved_at">Resolved ↓</option>
              <option value="resolved_at">Resolved ↑</option>
              <option value="rule_code">Rule A→Z</option>
              <option value="-rule_code">Rule Z→A</option>
              <option value="owner">Owner A→Z</option>
              <option value="-owner">Owner Z→A</option>
            </select>
          </div>
          <button onClick={()=>setPage(0)}>Apply</button>
        </div>
      </section>

      {/* Tickets table */}
      <section style={{ border: "1px solid #eee", borderRadius: 8 }}>
        <div style={{ padding: "8px 12px", borderBottom: "1px solid #eee", display: "flex", alignItems: "center", gap: 8 }}>
          <h3 style={{ margin: 0 }}>Open Remediation Tickets</h3>
          <span style={{ color: "#666" }}>{listLoading ? "Loading…" : `${total} total`}</span>
        </div>
        <div style={{ overflow: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ background: "#fafafa" }}>
              <tr>
                <Th>ID</Th><Th>Rule</Th><Th>Owner</Th><Th>Message</Th><Th>Snoozed Until</Th><Th>Created</Th><Th>Updated</Th><Th>Actions</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} style={{ borderTop: "1px solid #f0f0f0" }}>
                  <Td mono>#{r.id}</Td>
                  <Td mono>{r.rule_code}</Td>
                  <Td>{r.owner || "—"}</Td>
                  <Td>{r.message || "—"}</Td>
                  <Td>{r.snoozed_until ? format(new Date(r.snoozed_until), "yyyy-MM-dd HH:mm") : "—"}</Td>
                  <Td>{format(new Date(r.created_at), "yyyy-MM-dd HH:mm")}</Td>
                  <Td>{format(new Date(r.updated_at), "yyyy-MM-dd HH:mm")}</Td>
                  <Td>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <button onClick={()=>doAck(r.id)}>Ack</button>
                      <button onClick={()=>doAssign(r.id)}>Assign</button>
                      <button onClick={()=>doSnooze(r.id)}>Snooze</button>
                      <button onClick={()=>doResolve(r.id)}>Resolve</button>
                    </div>
                  </Td>
                </tr>
              ))}
              {!rows.length && !listLoading && (
                <tr><Td colSpan={8 as any}>No open tickets 🎉</Td></tr>
              )}
            </tbody>
          </table>
        </div>
        {/* Pagination */}
        <div style={{ padding: 12, display: "flex", gap: 8, justifyContent: "flex-end", alignItems: "center" }}>
          <button disabled={page===0} onClick={()=>setPage(p=>Math.max(0,p-1))}>Prev</button>
          <span>Page {page+1}</span>
          <button disabled={(page+1)*20 >= total} onClick={()=>setPage(p=>p+1)}>Next</button>
        </div>
      </section>
    </div>
  );
}
