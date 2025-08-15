import { useEffect, useMemo, useState } from "react";
import { api, endpoints } from "../lib/api";
import { format } from "date-fns";

export type UserSelfSummary = {
  user_id: string;
  results: {
    done_count: number;
    done_points: number;
    median_lead_time_sec: number | null;
    prs_opened: number;
    prs_reviewed: number;
  };
};

export type UserSelfTimeseriesRow = {
  date: string;           // YYYY-MM-DD
  done_count: number;
  done_points: number;
  prs_opened: number;
  prs_reviewed: number;
};

export type UserSelfWip = {
  user_id: string;
  in_dev: number;
  waiting_for_qa: number;
  in_qa: number;
};

function qRange(start?: Date, end?: Date) {
  const p = new URLSearchParams();
  if (start) p.set("start", format(start, "yyyy-MM-dd"));
  if (end) p.set("end", format(end, "yyyy-MM-dd"));
  return p.toString();
}

export function useUserSelfSummary(boardId: number, start?: Date, end?: Date) {
  const q = useMemo(() => qRange(start, end), [start, end]);
  const [data, setData] = useState<UserSelfSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let on = true;
    setLoading(true);
    api.get(endpoints.userSelfSummary(boardId, q))
      .then(({ data }) => on && setData(data))
      .catch(() => on && setErr("Failed to load summary"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [boardId, q]);
  return { data, loading, err };
}

export function useUserSelfTimeseries(boardId: number, start?: Date, end?: Date) {
  const q = useMemo(() => qRange(start, end), [start, end]);
  const [rows, setRows] = useState<UserSelfTimeseriesRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let on = true;
    setLoading(true);
    api.get(endpoints.userSelfTimeseries(boardId, q))
      .then(({ data }) => on && setRows(data.results || []))
      .catch(() => on && setErr("Failed to load timeseries"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [boardId, q]);
  return { rows, loading, err };
}

export function useUserSelfWip(boardId: number) {
  const [data, setData] = useState<UserSelfWip | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let on = true;
    setLoading(true);
    api.get(endpoints.userSelfWip(boardId))
      .then(({ data }) => on && setData(data))
      .catch(() => on && setErr("Failed to load WIP"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [boardId]);
  return { data, loading, err };
}
