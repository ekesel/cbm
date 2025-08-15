import React, { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { format, subDays } from "date-fns";
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from "recharts";
import { useTeamTimeseries, useTeamSummary, useTeamBlocked, useTeamBoards } from "../hooks/useTeam";

function fmtNum(n?: number | null) {
  if (n === null || n === undefined) return "—";
  return new Intl.NumberFormat().format(n);
}
function fmtSec(s?: number | null) {
  if (!s && s !== 0) return "—";
  const h = Math.round((s as number) / 3600);
  return `${h}h`;
}

export default function TeamDashboard() {
  const { teamId: teamIdParam } = useParams();
  const teamId = Number(teamIdParam);
  const [range, setRange] = useState<{start: Date; end: Date}>(() => {
    const end = new Date();
    const start = subDays(end, 29);
    return { start, end };
  });

  const { data: series, loading: tsLoading } = useTeamTimeseries(teamId, range.start, range.end);
  const { data: summary, loading: sumLoading } = useTeamSummary(teamId, range.start, range.end);
  const { items: blocked, loading: blockedLoading, boards } = useTeamBlocked(teamId, 60);

  const boardMap = useMemo(() => Object.fromEntries((boards || []).map(b => [b.id, b.name])), [boards]);

  return (
    <div style={{ padding: 16, display: "grid", gap: 16 }}>
      <header>
        <h1 style={{ fontSize: 22, marginBottom: 6 }}>Team {teamId} — Dashboard</h1>
        <div style={{ color: "#666" }}>
          Window: {format(range.start, "yyyy-MM-dd")} → {format(range.end, "yyyy-MM-dd")}
        </div>
      </header>

      {/* Summary cards */}
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12 }}>
        <Card title="Velocity (points)">
          <b style={{ fontSize: 22 }}>{fmtNum(summary?.velocity_points)}</b>
        </Card>
        <Card title="Throughput (items)">
          <b style={{ fontSize: 22 }}>{fmtNum(summary?.throughput)}</b>
        </Card>
        <Card title="Defect Density">
          <b style={{ fontSize: 22 }}>{summary ? (summary.defect_density * 100).toFixed(1) + "%" : "—"}</b>
        </Card>
        <Card title="Median Lead Time">
          <b style={{ fontSize: 22 }}>{fmtSec(summary?.median_lead_time_sec)}</b>
        </Card>
      </section>

      {/* Chart */}
      <section style={{ height: 340, border: "1px solid #eee", borderRadius: 8, padding: 8 }}>
        <h3 style={{ margin: "4px 8px 8px" }}>Velocity & Throughput (daily)</h3>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={series || []} margin={{ top: 12, right: 24, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis yAxisId="left" />
            <YAxis yAxisId="right" orientation="right" />
            <Tooltip />
            <Legend />
            {/* velocity as points */}
            <Line type="monotone" dataKey="velocity_points" name="Velocity (pts)" yAxisId="left" dot={false} />
            {/* throughput as count */}
            <Line type="monotone" dataKey="throughput" name="Throughput (count)" yAxisId="right" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </section>

      {/* Blocked list */}
      <section style={{ border: "1px solid #eee", borderRadius: 8 }}>
        <div style={{ display: "flex", alignItems: "center", padding: "8px 12px", borderBottom: "1px solid #eee" }}>
          <h3 style={{ margin: 0 }}>Currently Blocked</h3>
          <span style={{ marginLeft: 8, color: "#666" }}>
            {blockedLoading ? "Loading…" : `${blocked.length} items`}
          </span>
        </div>
        <div style={{ overflow: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ background: "#fafafa" }}>
              <tr>
                <Th>Board</Th>
                <Th>Key</Th>
                <Th>Title</Th>
                <Th>Owner</Th>
                <Th>Status</Th>
                <Th>Blocked Since</Th>
                <Th>Reason</Th>
              </tr>
            </thead>
            <tbody>
              {blocked.map((it) => {
                const since = it.blocked_since ? new Date(it.blocked_since) : null;
                return (
                  <tr key={it.id} style={{ borderTop: "1px solid #f0f0f0" }}>
                    <Td>{boardMap[it.board] || it.board}</Td>
                    <Td mono>{`${it.source?.toUpperCase()}:${it.source_id}`}</Td>
                    <Td>{it.title}</Td>
                    <Td>{it.dev_owner || "—"}</Td>
                    <Td>{it.status || "—"}</Td>
                    <Td>{since ? format(since, "yyyy-MM-dd HH:mm") : "—"}</Td>
                    <Td>{it.blocked_reason || "—"}</Td>
                  </tr>
                );
              })}
              {!blocked.length && !blockedLoading && (
                <tr><Td colSpan={7} center>No blocked items 🎉</Td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
      <div style={{ color: "#666", fontSize: 12 }}>{title}</div>
      <div>{children}</div>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, fontSize: 13 }}>{children}</th>;
}
function Td({ children, mono = false, center = false, colSpan }: { children: React.ReactNode; mono?: boolean; center?: boolean; colSpan?: number }) {
  return <td colSpan={colSpan} style={{ padding: "10px 12px", fontFamily: mono ? "ui-monospace, SFMono-Regular, Menlo, monospace" : undefined, textAlign: center ? "center" : "left" }}>{children}</td>;
}
