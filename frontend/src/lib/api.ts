import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const JWT_CREATE_PATH = import.meta.env.VITE_JWT_CREATE_PATH || "/api/auth/token/";
const JWT_REFRESH_PATH = import.meta.env.VITE_JWT_REFRESH_PATH || "/api/auth/token/refresh/";

export const endpoints = {
  login: `${API_BASE}${JWT_CREATE_PATH}`,
  refresh: `${API_BASE}${JWT_REFRESH_PATH}`,
  health: `${API_BASE}/api/health/`,
  teamTimeseries: (teamId: number, q: string = "") => `${API_BASE}/api/metrics/teams/${teamId}/timeseries${q ? `?${q}` : ""}`,
  teamSummary: (teamId: number, q: string = "") => `${API_BASE}/api/metrics/teams/${teamId}/summary${q ? `?${q}` : ""}`,
  teamBoards: (teamId: number) => `${API_BASE}/api/metrics/teams/${teamId}/boards`,
  workitemSearch: `${API_BASE}/api/workitems/search`, // expects query params
  workitemDetail: (id: number) => `${API_BASE}/api/workitems/${id}`,
  workitemByKey: (source: string, sourceId: string) => `${API_BASE}/api/workitems/by-key?source=${encodeURIComponent(source)}&source_id=${encodeURIComponent(sourceId)}`,
  compliance: (boardId: number, q: string = "") => `${API_BASE}/api/remediation/compliance?board_id=${boardId}${q ? `&${q}` : ""}`,
  remediationList: `${API_BASE}/api/remediation/tickets`,            // GET list
  remediationUpdate: (id: number) => `${API_BASE}/api/remediation/tickets/${id}/update`, // PATCH
  userSelfSummary: (boardId: number, q = "") =>
    `${API_BASE}/api/metrics/users/self/summary?board_id=${boardId}${q ? `&${q}` : ""}`,
  userSelfTimeseries: (boardId: number, q = "") =>
    `${API_BASE}/api/metrics/users/self/timeseries?board_id=${boardId}${q ? `&${q}` : ""}`,
  userSelfWip: (boardId: number) =>
    `${API_BASE}/api/metrics/users/self/wip?board_id=${boardId}`,
  // Admin — Boards
  adminBoards: `${API_BASE}/api/admin/boards`,
  adminBoard: (id: number) => `${API_BASE}/api/admin/boards/${id}`,

  // Admin — Mapping Versions
  adminMappings: `${API_BASE}/api/admin/mappings`,
  adminMapping: (id: number) => `${API_BASE}/api/admin/mappings/${id}`,
  adminMappingValidate: (id: number) => `${API_BASE}/api/admin/mappings/${id}/validate`,
  adminMappingActivate: (id: number) => `${API_BASE}/api/admin/mappings/${id}/activate`,

  // ETL admin (from your F-04 endpoints)
  etlRun: `${API_BASE}/api/admin/etl/run`,
  etlStatus: `${API_BASE}/api/admin/etl/status`,
  etlJobs: `${API_BASE}/api/admin/etl/jobs`,
};

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: false,
});

// --- Token storage helpers ---
const kAccess = "auth.access";
const kRefresh = "auth.refresh";

export function setTokens(access?: string, refresh?: string) {
  if (access) localStorage.setItem(kAccess, access);
  if (refresh) localStorage.setItem(kRefresh, refresh);
}
export function getAccess() { return localStorage.getItem(kAccess) || ""; }
export function getRefresh() { return localStorage.getItem(kRefresh) || ""; }
export function clearTokens() {
  localStorage.removeItem(kAccess);
  localStorage.removeItem(kRefresh);
}

// Attach Authorization header
api.interceptors.request.use((cfg) => {
  const tok = getAccess();
  if (tok && cfg.headers) cfg.headers.Authorization = `Bearer ${tok}`;
  return cfg;
});

// Auto refresh on 401 (once per request)
let refreshing = false;
let pending: Array<[(t: string)=>void, (e: any)=>void]> = [];

function onRefreshed(newAccess: string) {
  pending.forEach(([res]) => res(newAccess));
  pending = [];
}
function onRefreshError(err: any) {
  pending.forEach(([_, rej]) => rej(err));
  pending = [];
}

api.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const original = error.config;
    if (error?.response?.status === 401 && !original._retry) {
      if (refreshing) {
        return new Promise((resolve, reject) => {
          pending.push([
            (token: string) => {
              original.headers.Authorization = `Bearer ${token}`;
              resolve(api(original));
            },
            (err) => reject(err),
          ]);
        });
      }
      original._retry = true;
      refreshing = true;
      try {
        const refresh = getRefresh();
        if (!refresh) throw new Error("No refresh token");
        const r = await axios.post(endpoints.refresh, { refresh });
        const newAccess = r.data?.access;
        if (!newAccess) throw new Error("No access in refresh response");
        setTokens(newAccess, refresh);
        onRefreshed(newAccess);
        original.headers.Authorization = `Bearer ${newAccess}`;
        return api(original);
      } catch (e) {
        onRefreshError(e);
        clearTokens();
        // Let app route guard redirect to /login
        return Promise.reject(e);
      } finally {
        refreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

export async function loginApi(usernameOrEmail: string, password: string) {
  // SimpleJWT expects {username, password} OR {email, password} based on your backend.
  // Use "username" key; backend can accept either via custom serializer if needed.
  const payload: Record<string, string> = { username: usernameOrEmail, password };
  const { data } = await axios.post(endpoints.login, payload);
  return data as { access: string; refresh: string };
}
