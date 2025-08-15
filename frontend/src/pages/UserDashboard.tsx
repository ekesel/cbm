import React, { useMemo, useState } from "react";
import { subDays, format } from "date-fns";
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from "recharts";
import { useUserSelfSummary, useUserSelfTimeseries, useUserSelfWip } from "../hooks/useUserSelf";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
    <div style={{ color: "#666", fontSize: 12 }}>{title}</div>
    <div>{children}</div>
  </div>;
}
function fmt(n?: number | null) { return (n === null || n === undefined) ? "—" : new Intl.NumberFormat().format(n); }
function fmtH(sec?: number | null) { if (sec === null || sec === undefined) return "—"; return `${Math.round(sec/3600)}h`; }

export default function UserDashboard() {
  // Choose the board you’re focusing on (could be a selector later).
  const [boardId, setBoardId] = useState<number>(1);

  const [range, setRange] = useState<{start: Date; end: Date}>(() => {
    const end = new Date();
    const start = subDays(end, 29);
    return { start, end };
  });

  const { data: summary, loading: sumLoading } = useUserSelfSummary(boardId, range.start, range.end);
  const { rows, loading: tsLoading } = useUserSelfTimeseries(boardId, range.start, range.end);
  const { data: wip, loading: wipLoading } = useUserSelfWip(boardId);

  // Coaching tips (simple heuristics — adjust as you learn)
  const tips = useMemo(() => {
    const out: string[] = [];
    const done7 = rows.slice(-7).reduce((a, r) => a + (r.done_points || 0), 0);
    const rev7  = rows.slice(-7).reduce((a, r) => a + (r.prs_reviewed || 0), 0);

    if (done7 < 10) out.push("Try to finish at least ~10 story points per week. Negotiate scope if blocked.");
    if (rev7 < 10)  out.push("Increase review participation — target ~2 PR reviews/day to help team flow.");
    if ((summary?.results.median_lead_time_sec || 0) > 72*3600)
      out.push("Your median lead time is trending high; slice work into smaller verticals.");
    const wipTotal = (wip?.in_dev || 0) + (wip?.waiting_for_qa || 0) + (wip?.in_qa || 0);
    if (wipTotal > 3) out.push("Too much WIP — finish or park items to reduce context switching.");
    if (!out.length) out.push("Nice! Keep the steady cadence and continue reviewing PRs promptly.");
    return out;
  }, [rows, summary, wip]);

  return (
    <div style={{ padding: 16, display: "grid", gap: 16 }}>
      <header style={{ display: "flex", gap: 12, alignItems: "baseline", flexWrap: "wrap" }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>My Dashboard</h1>
        <div style={{ color: "#666" }}>
          Board: <input type="number" min={1} value={boardId} onChange={e=>setBoardId(Number(e.target.value))} style={{ width: 80 }} /> •
          Window: {format(range.start, "yyyy-MM-dd")} → {format(range.end, "yyyy-MM-dd")}
        </div>
      </header>

      {/* Summary cards */}
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
        <Card title="Done points (window)">
          <b style={{ fontSize: 22 }}>{sumLoading ? "…" : fmt(summary?.results.done_points)}</b>
        </Card>
        <Card title="Done count (window)">
          <b style={{ fontSize: 22 }}>{sumLoading ? "…" : fmt(summary?.results.done_count)}</b>
        </Card>
        <Card title="PRs opened / reviewed (window)">
          <b style={{ fontSize: 22 }}>
            {sumLoading ? "…" : `${fmt(summary?.results.prs_opened)} / ${fmt(summary?.results.prs_reviewed)}`}
          </b>
        </Card>
        <Card title="Median lead time">
          <b style={{ fontSize: 22 }}>{sumLoading ? "…" : fmtH(summary?.results.median_lead_time_sec)}</b>
        </Card>
        <Card title="Current WIP (Dev / Waiting QA / In QA)">
          <b style={{ fontSize: 22 }}>{wipLoading ? "…" : `${wip?.in_dev ?? 0} / ${wip?.waiting_for_qa ?? 0} / ${wip?.in_qa ?? 0}`}</b>
        </Card>
      </section>

      {/* Chart */}
      <section style={{ height: 340, border: "1px solid #eee", borderRadius: 8, padding: 8 }}>
        <h3 style={{ margin: "4px 8px 8px" }}>My cadence (daily): Done points & PR reviews</h3>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows || []} margin={{ top: 12, right: 24, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis yAxisId="left" />
            <YAxis yAxisId="right" orientation="right" />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="done_points"    name="Done points" yAxisId="left" dot={false} />
            <Line type="monotone" dataKey="prs_reviewed"   name="PR reviews"  yAxisId="right" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </section>

      {/* Coaching tips */}
      <section style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
        <h3 style={{ marginTop: 0 }}>Coaching tips</h3>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {tips.map((t, i) => <li key={i}>{t}</li>)}
        </ul>
      </section>
    </div>
  );
}
