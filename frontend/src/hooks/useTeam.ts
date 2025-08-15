import { useEffect, useMemo, useState } from "react";
import { api, endpoints } from "../lib/api";
import { format } from "date-fns";

export type TeamTimeseriesRow = {
  date: string;                // YYYY-MM-DD
  throughput: number;          // count
  velocity_points: number;     // sum of story points
  defect_density: number;      // 0..1
  median_lead_time_sec: number | null;
};

export type TeamSummary = {
  throughput: number;
  velocity_points: number;
  defect_density: number;
  median_lead_time_sec: number | null;
};

export type TeamBoard = { id: number; name: string };

export function useTeamBoards(teamId: number) {
  const [boards, setBoards] = useState<TeamBoard[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let on = true;
    setLoading(true);
    api.get(endpoints.teamBoards(teamId))
      .then(({ data }) => on && setBoards(data.boards || []))
      .catch(() => on && setErr("Failed to load boards"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [teamId]);
  return { boards, loading, err };
}

export function useTeamTimeseries(teamId: number, start?: Date, end?: Date) {
  const q = useMemo(() => {
    const params = new URLSearchParams();
    if (start) params.set("start", format(start, "yyyy-MM-dd"));
    if (end) params.set("end", format(end, "yyyy-MM-dd"));
    return params.toString();
  }, [start, end]);

  const [data, setData] = useState<TeamTimeseriesRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let on = true;
    setLoading(true);
    api.get(endpoints.teamTimeseries(teamId, q))
      .then(({ data }) => on && setData(data.results || []))
      .catch(() => on && setErr("Failed to load timeseries"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [teamId, q]);

  return { data, loading, err };
}

export function useTeamSummary(teamId: number, start?: Date, end?: Date) {
  const q = useMemo(() => {
    const params = new URLSearchParams();
    if (start) params.set("start", format(start, "yyyy-MM-dd"));
    if (end) params.set("end", format(end, "yyyy-MM-dd"));
    return params.toString();
  }, [start, end]);

  const [data, setData] = useState<TeamSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let on = true;
    setLoading(true);
    api.get(endpoints.teamSummary(teamId, q))
      .then(({ data }) => on && setData(data))
      .catch(() => on && setErr("Failed to load summary"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [teamId, q]);

  return { data, loading, err };
}

export type BlockedItem = {
  id: number;
  board: number;
  source: string;
  source_id: string;
  title: string;
  dev_owner?: string | null;
  blocked_reason?: string | null;
  blocked_since?: string | null;
  updated_at?: string;
  status?: string;
};

export function useTeamBlocked(teamId: number, limitTotal = 50) {
  const { boards } = useTeamBoards(teamId);
  const [items, setItems] = useState<BlockedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let on = true;
    async function run() {
      if (!boards.length) { setItems([]); setLoading(false); return; }
      setLoading(true);
      try {
        // fetch top blocked items per board (client sorts by blocked_since desc)
        const perBoard = Math.max(10, Math.ceil(limitTotal / boards.length));
        const calls = boards.map(b =>
          api.get(endpoints.workitemSearch, {
            params: {
              board: b.id,
              blocked: true,
              closed: false,
              ordering: "-updated_at",
              limit: perBoard,
              offset: 0
            }
          }).then(r => ({ board: b, rows: (r.data?.results || []) as BlockedItem[] }))
        );
        const res = await Promise.all(calls);
        const merged = res.flatMap(x => x.rows.map(r => ({ ...r, board: r.board || x.board.id })));
        // sort by blocked_since desc, then updated_at desc
        merged.sort((a, b) => {
          const as = a.blocked_since ? Date.parse(a.blocked_since) : 0;
          const bs = b.blocked_since ? Date.parse(b.blocked_since) : 0;
          if (bs !== as) return bs - as;
          const au = a.updated_at ? Date.parse(a.updated_at) : 0;
          const bu = b.updated_at ? Date.parse(b.updated_at) : 0;
          return bu - au;
        });
        const trimmed = merged.slice(0, limitTotal);
        if (on) setItems(trimmed);
      } catch (e) {
        if (on) setErr("Failed to load blocked items");
      } finally {
        if (on) setLoading(false);
      }
    }
    run();
    return () => { on = false; };
  }, [teamId, boards.map(b => b.id).join(","), limitTotal]);

  return { items, loading, err, boards };
}
