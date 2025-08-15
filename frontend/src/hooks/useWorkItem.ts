import { useEffect, useState } from "react";
import { api, endpoints } from "../lib/api";

export type WorkItem = {
  id: number;
  board: number;
  client_id?: string | null;
  source: string;
  source_id: string;
  title: string;
  description?: string | null;
  item_type?: string | null;
  status?: string | null;
  story_points?: number | null;
  assignees?: string[] | null;
  dev_owner?: string | null;
  sprint_id?: string | null;
  closed: boolean;

  created_at?: string | null;
  started_at?: string | null;
  dev_started_at?: string | null;
  dev_done_at?: string | null;
  ready_for_qa_at?: string | null;
  qa_started_at?: string | null;
  qa_verified_at?: string | null;
  signed_off_at?: string | null;
  ready_for_uat_at?: string | null;
  deployed_uat_at?: string | null;
  done_at?: string | null;

  blocked_flag?: boolean;
  blocked_since?: string | null;
  blocked_reason?: string | null;

  linked_prs?: string[] | null;
  linked_prs_full?: Array<{
    pr_id: string;
    source: string;
    title?: string | null;
    branch?: string | null;
    opened_at?: string | null;
    first_reviewed_at?: string | null;
    merged_at?: string | null;
    author_id?: string | null;
    reviewer_ids?: string[] | null;
    meta?: any;
  }>;
  remediation_tickets?: Array<{
    id: number;
    rule_code: string;
    status: string;
    message?: string | null;
    meta?: any;
    created_at: string;
    updated_at: string;
    resolved_at?: string | null;
  }>;
  meta?: any;
};

export function useWorkItemById(id?: number) {
  const [data, setData] = useState<WorkItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let on = true;
    if (!id) { setLoading(false); setErr("Missing id"); return; }
    setLoading(true);
    api.get(endpoints.workitemDetail(id))
      .then(({ data }) => on && setData(data))
      .catch(() => on && setErr("Failed to load work item"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [id]);

  return { data, loading, err };
}

export function useWorkItemByKey(source?: string, sourceId?: string) {
  const [data, setData] = useState<WorkItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let on = true;
    if (!source || !sourceId) { setLoading(false); setErr("Missing key"); return; }
    setLoading(true);
    api.get(endpoints.workitemByKey(source, sourceId))
      .then(({ data }) => on && setData(data))
      .catch(() => on && setErr("Failed to load work item"))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [source, sourceId]);

  return { data, loading, err };
}
