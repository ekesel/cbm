import { api, endpoints } from "../lib/api";
import { useEffect, useState } from "react";

export type BoardRow = { id: number; name: string; source?: string; client_id?: string; is_active?: boolean; meta?: any; };

export function useBoards() {
  const [rows, setRows] = useState<BoardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let on = true;
    setLoading(true);
    api.get(endpoints.adminBoards)
      .then(({ data }) => on && setRows(data.results || []))
      .catch(() => on && setErr("Failed to load boards"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, []);
  return { rows, loading, err };
}

export async function fetchBoard(id: number) {
  const { data } = await api.get(endpoints.adminBoard(id));
  return data as BoardRow;
}
export async function updateBoard(id: number, patch: Partial<BoardRow>) {
  const { data } = await api.patch(endpoints.adminBoard(id), patch);
  return data as BoardRow;
}

export type MappingRow = { id: number; version: string; active: boolean; created_at: string; updated_at?: string };

export function useMappings() {
  const [rows, setRows] = useState<MappingRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let on = true;
    setLoading(true);
    api.get(endpoints.adminMappings)
      .then(({ data }) => on && setRows(data.results || []))
      .catch(() => on && setErr("Failed to load mappings"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, []);
  return { rows, loading, err };
}

export async function createMapping(params: { version?: string; from_id?: number; config?: any }) {
  const { data } = await api.post(endpoints.adminMappings, params);
  return data as { id: number; version: string; active: boolean };
}
export async function fetchMapping(id: number) {
  const { data } = await api.get(endpoints.adminMapping(id));
  return data as { id: number; version: string; active: boolean; config: any; created_at: string; updated_at?: string };
}
export async function saveMapping(id: number, config: any) {
  const { data } = await api.patch(endpoints.adminMapping(id), { config });
  return data as { ok: boolean; id: number };
}
export async function validateMapping(id: number, config?: any) {
  const { data } = await api.post(endpoints.adminMappingValidate(id), { config });
  return data as { errors: string[]; warnings: string[] };
}
export async function activateMapping(id: number) {
  const { data } = await api.post(endpoints.adminMappingActivate(id), {});
  return data as { ok: boolean; id: number; version: string; active: boolean };
}

// ETL admin
export type ETLRunResp = { ok: boolean; task_id: string; board_id: number; stages: string[] };
export async function runETL(board_id: number, stages: string[], mapping_version = "v1", date_for_snapshot?: string) {
  const { data } = await api.post(endpoints.etlRun, { board_id, stages, mapping_version, date_for_snapshot });
  return data as ETLRunResp;
}
export async function listJobs(board_id?: number, limit = 20, offset = 0) {
  const { data } = await api.get(endpoints.etlJobs, { params: { board_id, limit, offset } });
  return data as { total: number; results: any[] };
}
