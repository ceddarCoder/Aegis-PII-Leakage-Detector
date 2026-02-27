// API client for Aegis PII Scanner FastAPI backend — with JWT auth support
const DEFAULT_API_URL = import.meta.env.VITE_API_URL;
export function getApiUrl(): string {
  return localStorage.getItem("aegis_api_url") || DEFAULT_API_URL;
}
export function setApiUrl(url: string) {
  localStorage.setItem("aegis_api_url", url.replace(/\/+$/, ""));
}

function getToken(): string | null {
  return localStorage.getItem("aegis_token");
}

export interface Finding {
  type: string;
  value: string;
  value_masked: string;
  snippet: string;
  confidence: number;
  risk: string;
  annotation: string;
  file_path?: string;
  source?: string;
  source_url?: string;
  platform?: string;
  content_type?: string;
}

export interface ESSSummary {
  max_ess: number;
  avg_ess: number;
  label: string;
  color: string;
  total_sources: number;
  all_types: string[];
}

export interface ScanResponse {
  findings: Finding[];
  ess_summary: ESSSummary | null;
  total_sources_scanned: number;
  scan_duration: number;
}

export interface ScanHistoryItem {
  id: number;
  scan_type: string;
  target: string;
  findings_count: number;
  max_ess: number;
  ess_label: string;
  sources_scanned: number;
  scan_duration: number;
  created_at: string | null;
}

// ── Authenticated POST helper ───────────────────────────────────
async function post<T>(endpoint: string, body: Record<string, unknown>): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${getApiUrl()}${endpoint}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    if (res.status === 401) throw new Error("Session expired. Please log in again.");
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

// ── Authenticated GET helper ────────────────────────────────────
async function get<T>(endpoint: string): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${getApiUrl()}${endpoint}`, { headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    if (res.status === 401) throw new Error("Session expired. Please log in again.");
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

// ── Authenticated DELETE helper ─────────────────────────────────
async function del<T>(endpoint: string): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${getApiUrl()}${endpoint}`, { method: "DELETE", headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

// ── Scan endpoints ──────────────────────────────────────────────
export async function scanGithubSingle(repo: string, branch = "main", maxFiles = 40, useNlp = false) {
  return post<ScanResponse>("/scan/github/single", { repo, branch, max_files: maxFiles, use_nlp: useNlp });
}

export async function scanGithubUser(username: string, maxRepos = 5, maxFilesPerRepo = 40, useNlp = false) {
  return post<ScanResponse>("/scan/github/user", { username, max_repos: maxRepos, max_files_per_repo: maxFilesPerRepo, use_nlp: useNlp });
}

export async function scanPastebin(limit = 15, useNlp = false) {
  return post<ScanResponse>("/scan/pastebin", { limit, use_nlp: useNlp });
}

export async function scanSocial(opts: {
  reddit_username?: string;
  reddit_max_posts?: number;
  telegram_channels?: string[];
  telegram_messages_per_channel?: number;
  use_nlp?: boolean;
}) {
  return post<ScanResponse>("/scan/social", {
    reddit_username: opts.reddit_username || null,
    reddit_max_posts: opts.reddit_max_posts || 20,
    telegram_channels: opts.telegram_channels || null,
    telegram_messages_per_channel: opts.telegram_messages_per_channel || 50,
    use_nlp: opts.use_nlp || false,
  });
}

// ── History endpoints ───────────────────────────────────────────
export async function saveScanHistory(item: Omit<ScanHistoryItem, "id" | "created_at">) {
  return post<ScanHistoryItem>("/history/save", item as Record<string, unknown>);
}

export async function getScanHistory() {
  return get<ScanHistoryItem[]>("/history");
}

export async function deleteScanHistory(id: number) {
  return del<{ deleted: number }>(`/history/${id}`);
}

// ── Health check ────────────────────────────────────────────────
export async function healthCheck(): Promise<boolean> {
  try {
    const res = await fetch(`${getApiUrl()}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

// ── Profile map ─────────────────────────────────────────────────
export interface ProfileEntry {
  kind: string;   // github | reddit | telegram | twitter | linkedin | email | website | custom
  label: string;
  value: string;
}

export interface UserProfile {
  entries: ProfileEntry[];
  notes?: string;
}

export interface ProfileScanResult {
  scanned_at: string;
  total_findings: number;
  max_ess: number;
  ess_label: string;
  findings: Finding[];
  ess_summary: ESSSummary | null;
}

export async function getProfile() {
  return get<UserProfile>("/profile");
}

export async function saveProfile(profile: UserProfile) {
  const token = localStorage.getItem("aegis_token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${getApiUrl()}/profile`, {
    method: "PUT",
    headers,
    body: JSON.stringify(profile),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json() as Promise<UserProfile>;
}

export async function scanProfile() {
  return post<ProfileScanResult>("/profile/scan", {});
}

export async function getLastProfileScan() {
  return get<ProfileScanResult | null>("/profile/scan/last");
}
