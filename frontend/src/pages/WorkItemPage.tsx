import React, { useMemo } from "react";
import { useParams } from "react-router-dom";
import { format } from "date-fns";
import { useWorkItemById, useWorkItemByKey, WorkItem } from "../hooks/useWorkItem";

const STEPS: Array<{key: keyof WorkItem; label: string}> = [
  { key: "dev_started_at", label: "Dev Started" },
  { key: "dev_done_at", label: "Dev Done" },
  { key: "ready_for_qa_at", label: "Ready for QA" },
  { key: "qa_started_at", label: "QA Started" },
  { key: "qa_verified_at", label: "QA Verified" },
  { key: "signed_off_at", label: "Signed Off" },
  { key: "ready_for_uat_at", label: "Ready for UAT" },
  { key: "deployed_uat_at", label: "Deployed to UAT" },
  { key: "done_at", label: "Done" },
];

function Badge({ children, kind = "default" }: { children: React.ReactNode; kind?: "default"|"warn"|"ok"|"danger" }) {
  const bg = kind === "warn" ? "#fff7e6" : kind === "ok" ? "#e6ffed" : kind === "danger" ? "#ffe6e6" : "#f2f2f2";
  const color = kind === "warn" ? "#8a5a00" : kind === "ok" ? "#0a5" : kind === "danger" ? "#b30000" : "#444";
  return <span style={{ background: bg, color, borderRadius: 999, padding: "2px 8px", fontSize: 12 }}>{children}</span>;
}

function MetaRow({ label, value, mono=false }: { label: string; value?: React.ReactNode; mono?: boolean }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "160px 1fr", gap: 8 }}>
      <div style={{ color: "#666" }}>{label}</div>
      <div style={{ fontFamily: mono ? "ui-monospace, SFMono-Regular, Menlo, monospace" : undefined }}>{value ?? "—"}</div>
    </div>
  );
}

function Timeline({ item }: { item: WorkItem }) {
  return (
    <div style={{ position: "relative", paddingLeft: 24 }}>
      <div style={{ position: "absolute", left: 10, top: 8, bottom: 8, width: 2, background: "#eee" }} />
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {STEPS.map(({ key, label }) => {
          const ts = item[key] as string | null | undefined;
          return (
            <li key={String(key)} style={{ display: "grid", gridTemplateColumns: "16px 1fr", gap: 8, marginBottom: 8, alignItems: "center" }}>
              <span style={{ width: 12, height: 12, borderRadius: 999, background: ts ? "#0a5" : "#ccc", display: "inline-block" }} />
              <div>
                <div style={{ fontWeight: 600 }}>{label}</div>
                <div style={{ color: "#666", fontSize: 12 }}>{ts ? format(new Date(ts), "yyyy-MM-dd HH:mm") : "not yet"}</div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function PRs({ item }: { item: WorkItem }) {
  const prs = item.linked_prs_full || [];
  if (!prs.length) return <div style={{ color: "#666" }}>No linked PRs.</div>;
  return (
    <div style={{ overflow: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead style={{ background: "#fafafa" }}>
          <tr>
            <Th>PR</Th><Th>Title</Th><Th>Branch</Th><Th>Author</Th><Th>Reviewers</Th><Th>Opened</Th><Th>First Review</Th><Th>Merged</Th>
          </tr>
        </thead>
        <tbody>
          {prs.map((pr, i) => (
            <tr key={i} style={{ borderTop: "1px solid #f0f0f0" }}>
              <Td mono>{pr.source?.toUpperCase()}:{pr.pr_id}</Td>
              <Td>{pr.title || "—"}</Td>
              <Td mono>{pr.branch || "—"}</Td>
              <Td>{pr.author_id || "—"}</Td>
              <Td>{(pr.reviewer_ids || []).join(", ") || "—"}</Td>
              <Td>{pr.opened_at ? format(new Date(pr.opened_at), "yyyy-MM-dd HH:mm") : "—"}</Td>
              <Td>{pr.first_reviewed_at ? format(new Date(pr.first_reviewed_at), "yyyy-MM-dd HH:mm") : "—"}</Td>
              <Td>{pr.merged_at ? format(new Date(pr.merged_at), "yyyy-MM-dd HH:mm") : "—"}</Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Remediation({ item }: { item: WorkItem }) {
  const rts = item.remediation_tickets || [];
  if (!rts.length) return <div style={{ color: "#666" }}>No remediation tickets.</div>;
  return (
    <div style={{ overflow: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead style={{ background: "#fafafa" }}>
          <tr>
            <Th>ID</Th><Th>Rule</Th><Th>Status</Th><Th>Message</Th><Th>Created</Th><Th>Updated</Th><Th>Resolved</Th>
          </tr>
        </thead>
        <tbody>
          {rts.map((rt) => (
            <tr key={rt.id} style={{ borderTop: "1px solid #f0f0f0" }}>
              <Td mono>#{rt.id}</Td>
              <Td mono>{rt.rule_code}</Td>
              <Td>{rt.status}</Td>
              <Td>{rt.message || "—"}</Td>
              <Td>{format(new Date(rt.created_at), "yyyy-MM-dd HH:mm")}</Td>
              <Td>{format(new Date(rt.updated_at), "yyyy-MM-dd HH:mm")}</Td>
              <Td>{rt.resolved_at ? format(new Date(rt.resolved_at), "yyyy-MM-dd HH:mm") : "—"}</Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, fontSize: 13 }}>{children}</th>;
}
function Td({ children, mono = false }: { children: React.ReactNode; mono?: boolean }) {
  return <td style={{ padding: "10px 12px", fontFamily: mono ? "ui-monospace, SFMono-Regular, Menlo, monospace" : undefined }}>{children}</td>;
}

export default function WorkItemPage() {
  const { id, source, sourceId } = useParams();
  const numericId = id ? Number(id) : undefined;
  const { data: byId, loading: loadId } = useWorkItemById(numericId);
  const { data: byKey, loading: loadKey } = useWorkItemByKey(source, sourceId);
  const item = (id ? byId : byKey) as WorkItem | null;
  const loading = id ? loadId : loadKey;

  const headerBadges = useMemo(() => {
    const out: React.ReactNode[] = [];
    if (item?.blocked_flag) out.push(<Badge key="blk" kind="warn">Blocked</Badge>);
    if (item?.item_type?.toLowerCase() === "bug") out.push(<Badge key="bug" kind="danger">Bug</Badge>);
    if (item?.closed) out.push(<Badge key="cls">Closed</Badge>);
    return out;
  }, [item]);

  if (loading) return <div style={{ padding: 16 }}>Loading…</div>;
  if (!item) return <div style={{ padding: 16 }}>Not found.</div>;

  return (
    <div style={{ padding: 16, display: "grid", gap: 16 }}>
      {/* Header */}
      <header>
        <h1 style={{ marginBottom: 6 }}>
          {item.title}
        </h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", color: "#666" }}>
          <span><b>Key:</b> <code>{item.source.toUpperCase()}:{item.source_id}</code></span>
          <span><b>Status:</b> {item.status || "—"}</span>
          <span><b>Type:</b> {item.item_type || "—"}</span>
          <span><b>Points:</b> {item.story_points ?? "—"}</span>
          <span><b>Owner:</b> {item.dev_owner || "—"}</span>
          <span><b>Sprint:</b> {item.sprint_id || "—"}</span>
          <span style={{ display: "flex", gap: 6 }}>{headerBadges}</span>
        </div>
      </header>

      {/* Layout: 2 columns on wide screens */}
      <section style={{ display: "grid", gridTemplateColumns: "1fr", gap: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(260px, 360px) 1fr", gap: 16 }}>
          {/* Timeline card */}
          <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Timeline</div>
            <Timeline item={item} />
          </div>

          {/* Meta card */}
          <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Meta</div>
            <div style={{ display: "grid", gap: 8 }}>
              <MetaRow label="Board ID" value={item.board} mono />
              <MetaRow label="Client" value={item.client_id} />
              <MetaRow label="Created" value={item.created_at ? format(new Date(item.created_at), "yyyy-MM-dd HH:mm") : "—"} />
              <MetaRow label="Blocked Since" value={item.blocked_since ? format(new Date(item.blocked_since), "yyyy-MM-dd HH:mm") : "—"} />
              <MetaRow label="Blocked Reason" value={item.blocked_reason || "—"} />
              <MetaRow label="Assignees" value={(item.assignees || []).join(", ") || "—"} />
            </div>
          </div>
        </div>

        {/* PRs */}
        <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Pull Requests</div>
          <PRs item={item} />
        </div>

        {/* Remediation tickets */}
        <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Remediation Tickets</div>
          <Remediation item={item} />
        </div>

        {/* Description */}
        <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Description</div>
          <div style={{ whiteSpace: "pre-wrap" }}>{item.description || "—"}</div>
        </div>
      </section>
    </div>
  );
}
