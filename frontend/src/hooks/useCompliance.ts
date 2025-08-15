import { useEffect, useMemo, useState } from "react";
import { api, endpoints } from "../lib/api";
import { format } from "date-fns";

export type ComplianceSnapshot = {
  board_id: number;
  total_open: number;
  by_rule: { rule_code: string; count: number }[];
  aging_buckets: { "0_2d": number; "3_5d": number; "6_10d": number; "gt_10d": number };
  silenced_open: number;
  recent_resolved_7d: number;
};

export function useCompliance(boardId: number, start?: Date, end?: Date) {
  const q = useMemo(() => {
    const p = new URLSearchParams();
    if (start) p.set("start", format(start, "yyyy-MM-dd"));
    if (end) p.set("end", format(end, "yyyy-MM-dd"));
    return p.toString();
  }, [start, end]);
  const [data, setData] = useState<ComplianceSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let on = true;
    setLoading(true);
    api.get(endpoints.compliance(boardId, q))
      .then(({ data }) => on && setData(data))
      .catch(() => on && setErr("Failed to load compliance"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [boardId, q]);

  return { data, loading, err };
}

export type RemediationRow = {
  id: number;
  board: number;
  work_item: number;
  rule_code: string;
  status: string;
  owner?: string | null;
  message?: string | null;
  meta?: any;
  acknowledged_at?: string | null;
  snoozed_until?: string | null;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
};

export function useRemediationList(params: {
  boardId: number;
  rule?: string;
  owner?: string;
  snoozed?: boolean | null;
  status?: string;           // e.g., OPEN / IN_PROGRESS / DONE
  limit?: number;
  offset?: number;
  search?: string;
  ordering?: string;         // e.g., "-created_at"
}) {
  const [rows, setRows] = useState<RemediationRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const q = useMemo(() => {
    const p = new URLSearchParams();
    p.set("board", String(params.boardId));
    if (params.rule) p.set("rule_code", params.rule);
    if (params.owner) p.set("owner", params.owner);
    if (params.snoozed !== null && params.snoozed !== undefined) p.set("snoozed", String(params.snoozed));
    if (params.status) p.set("status", params.status);
    p.set("limit", String(params.limit ?? 20));
    p.set("offset", String(params.offset ?? 0));
    if (params.search) p.set("search", params.search);
    p.set("ordering", params.ordering ?? "-updated_at");
    return p.toString();
  }, [params.boardId, params.rule, params.owner, params.snoozed, params.status, params.limit, params.offset, params.search, params.ordering]);

  useEffect(() => {
    let on = true;
    setLoading(true);
    api.get(endpoints.remediationList, { params: Object.fromEntries(new URLSearchParams(q)) })
      .then(({ data }) => {
        if (!on) return;
        setRows(data.results || []);
        setTotal(data.count ?? data.total ?? (data.results?.length || 0));
      })
      .catch(() => on && setErr("Failed to load tickets"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [q]);

  return { rows, total, loading, err };
}

export async function remediationAck(id: number, note?: string) {
  return api.patch(endpoints.remediationUpdate(id), { append_note: note || "Acknowledged" });
}
export async function remediationResolve(id: number, note?: string) {
  return api.patch(endpoints.remediationUpdate(id), { status: "DONE", append_note: note || "Resolved" });
}
export async function remediationSnooze(id: number, isoUntil: string, note?: string) {
  return api.patch(endpoints.remediationUpdate(id), { snoozed_until: isoUntil, append_note: note || `Snoozed until ${isoUntil}` });
}
export async function remediationAssign(id: number, owner: string, note?: string) {
  return api.patch(endpoints.remediationUpdate(id), { owner, append_note: note || `Assigned to ${owner}` });
}
