export interface User {
  id: string;
  email: string;
  full_name: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export interface Project {
  id: string;
  title: string;
  description: string | null;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
}

export interface ResearchBrief {
  id: string;
  project_id: string;
  research_question: string;
  objectives: string[];
  scope: string | null;
  depth: "quick" | "standard" | "deep";
  source_preferences: string[];
  recency_days: number | null;
  output_format: "markdown";
  output_language: string;
  created_at: string;
}

export interface ProjectDocument {
  id: string;
  project_id: string;
  file_name: string;
  file_type: string;
  size_bytes: number;
  extracted_characters: number;
  chunk_count: number;
  created_at: string;
}

export interface ResearchTask {
  id: string;
  project_id: string;
  brief_id: string;
  status:
    | "queued"
    | "running"
    | "waiting_review"
    | "completed"
    | "failed"
    | "cancelled";
  current_stage: string | null;
  attempt_count: number;
  safe_error_code: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface WorkspaceAnalytics {
  period_days: 7 | 30 | 90;
  generated_at: string;
  projects_total: number;
  projects_active: number;
  tasks_total: number;
  tasks_by_status: Array<{ status: ResearchTask["status"]; count: number }>;
  reports_total: number;
  reports_by_status: Array<{ status: "pending" | "approved" | "rejected"; count: number }>;
  sources_total: number;
  daily_tasks: Array<{ day: string; total: number; failed: number }>;
  recent_tasks: Array<
    Pick<ResearchTask, "id" | "project_id" | "status" | "created_at"> & {
      project_title: string;
    }
  >;
}

export interface TaskEvent {
  event_id: number;
  task_id: string;
  type: string;
  stage: string | null;
  agent: string | null;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface ReportDetail {
  id: string;
  task_id: string;
  review_status: "pending" | "approved" | "rejected";
  current_version: number;
  version: {
    id: string;
    version: number;
    executive_summary: string;
    sections: Array<{
      title: string;
      content: string;
      source_ids: string[];
    }>;
    methodology: string;
    limitations: string[];
    markdown: string;
    verification_status: "pending" | "running" | "completed" | "failed";
    verification_results: Array<{
      claim_id?: string;
      text?: string;
      status?: string;
      explanation: string;
      evidence_ids?: string[];
    }>;
    created_at: string;
  };
  sources: Array<{
    id: string;
    provider_source_id: string;
    url: string;
    title: string;
    publisher: string | null;
    published_date: string | null;
    source_type: string;
    retrieval_status: string;
    created_at: string;
    passages: Array<{
      id: string;
      text: string;
      locator: string | null;
      created_at: string;
    }>;
  }>;
  claims: Array<{
    id: string;
    claim_key: string;
    text: string;
    claim_type: string;
    evidence: Array<{
      evidence_id: string;
      source_id: string;
      provider_source_id: string;
      passage: string;
    }>;
    verifications: Array<{
      id: string;
      status:
        | "supported"
        | "partially_supported"
        | "contradicted"
        | "unsupported"
        | "not_checked"
        | "source_unavailable";
      explanation: string;
      checked_at: string;
    }>;
  }>;
}

export interface ReportRevision {
  base_version: number;
  executive_summary: string;
  sections: ReportDetail["version"]["sections"];
  methodology: string;
  limitations: string[];
  source_ids: string[];
}

interface ProjectPage {
  items: Project[];
  total: number;
  limit: number;
  offset: number;
}

interface ResearchTaskPage {
  items: ResearchTask[];
  total: number;
  limit: number;
  offset: number;
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
let accessToken: string | null = null;
let refreshInProgress: Promise<AuthResponse> | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

function csrfToken(): string | undefined {
  return document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("csrf_token="))
    ?.slice("csrf_token=".length);
}

async function errorMessage(response: Response): Promise<string> {
  const body = (await response.json().catch(() => null)) as
    | { detail?: unknown }
    | null;
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        typeof item === "object" && item !== null && "msg" in item
          ? String(item.msg)
          : "",
      )
      .filter(Boolean);
    if (messages.length) return messages.join(" ");
  }
  return `Request failed (${response.status}).`;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  retryAfterRefresh = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const csrf = csrfToken();
  if (csrf && ["POST", "PUT", "PATCH", "DELETE"].includes(init.method ?? "GET")) {
    headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (
    response.status === 401 &&
    retryAfterRefresh &&
    !["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout"].includes(path)
  ) {
    await authApi.refresh();
    return request<T>(path, init, false);
  }
  if (!response.ok) throw new Error(await errorMessage(response));
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const authApi = {
  register: (input: { email: string; full_name: string; password: string }) =>
    request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  login: (input: { email: string; password: string }) =>
    request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  refresh: () => {
    if (!refreshInProgress) {
      refreshInProgress = request<AuthResponse>(
        "/auth/refresh",
        { method: "POST" },
        false,
      )
        .then((result) => {
          setAccessToken(result.access_token);
          return result;
        })
        .catch((error: unknown) => {
          setAccessToken(null);
          throw error;
        })
        .finally(() => {
          refreshInProgress = null;
        });
    }
    return refreshInProgress;
  },
  logout: () => request<void>("/auth/logout", { method: "POST" }),
};

export const projectsApi = {
  list: (status: Project["status"] | null = "active") => {
    const params = new URLSearchParams({ limit: "100" });
    if (status) params.set("status", status);
    return request<ProjectPage>(`/projects?${params.toString()}`);
  },
  create: (input: { title: string; description?: string }) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(input) }),
  archive: (id: string) =>
    request<Project>(`/projects/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "archived" }),
    }),
};

export const documentsApi = {
  list: (projectId: string) =>
    request<ProjectDocument[]>(`/projects/${encodeURIComponent(projectId)}/documents`),
  upload: (projectId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<ProjectDocument>(
      `/projects/${encodeURIComponent(projectId)}/documents`,
      { method: "POST", body },
    );
  },
  remove: (projectId: string, documentId: string) =>
    request<void>(
      `/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(documentId)}`,
      { method: "DELETE" },
    ),
};

export const researchApi = {
  listTasks: (limit = 20, offset = 0) =>
    request<ResearchTaskPage>(`/tasks?limit=${limit}&offset=${offset}`),
  createBrief: (
    projectId: string,
    input: {
      research_question: string;
      objectives: string[];
      scope?: string;
      depth: ResearchBrief["depth"];
      source_preferences: string[];
      recency_days?: number;
      output_format: ResearchBrief["output_format"];
      output_language: string;
    },
  ) =>
    request<ResearchBrief>(`/projects/${encodeURIComponent(projectId)}/briefs`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  start: (projectId: string, briefId: string, idempotencyKey: string) =>
    request<ResearchTask>(
      `/projects/${encodeURIComponent(projectId)}/briefs/${encodeURIComponent(briefId)}/tasks`,
      {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
      },
    ),
  task: (taskId: string) =>
    request<ResearchTask>(`/tasks/${encodeURIComponent(taskId)}`),
  cancel: (taskId: string) =>
    request<ResearchTask>(`/tasks/${encodeURIComponent(taskId)}/cancel`, {
      method: "POST",
    }),
  resume: (taskId: string) =>
    request<ResearchTask>(`/tasks/${encodeURIComponent(taskId)}/resume`, {
      method: "POST",
    }),
  report: (taskId: string) =>
    request<ReportDetail>(`/reports/tasks/${encodeURIComponent(taskId)}/report`),
  review: (
    reportId: string,
    input: { decision: "approved" | "rejected"; comment?: string },
  ) =>
    request<{
      report_id: string;
      task_id: string;
      review_status: string;
      task_status: string;
      current_version: number;
    }>(`/reports/${encodeURIComponent(reportId)}/review`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  retryVerification: (reportId: string, version: number) =>
    request<{
      report_id: string;
      task_id: string;
      review_status: string;
      task_status: string;
      current_version: number;
    }>(
      `/reports/${encodeURIComponent(reportId)}/versions/${version}/reverify`,
      { method: "POST" },
    ),
  revise: (reportId: string, input: ReportRevision) =>
    request<{
      report_id: string;
      task_id: string;
      review_status: string;
      task_status: string;
      current_version: number;
    }>(`/reports/${encodeURIComponent(reportId)}/revisions`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
};

export const analyticsApi = {
  workspace: (days: 7 | 30 | 90) =>
    request<WorkspaceAnalytics>(`/analytics/workspace?days=${days}`),
};

const terminalEventTypes = new Set([
  "task.awaiting_review",
  "task.failed",
  "task.cancelled",
  "task.completed",
  "report.approved",
  "report.rejected",
  "report.revised",
]);

function waitForReconnect(delay: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const finish = () => {
      window.clearTimeout(timer);
      signal.removeEventListener("abort", finish);
      resolve();
    };
    const timer = window.setTimeout(finish, delay);
    signal.addEventListener("abort", finish, {
      once: true,
    });
  });
}

export async function streamTaskEvents(
  taskId: string,
  onEvent: (event: TaskEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  let cursor = 0;
  let delay = 1000;
  let refreshed = false;
  while (!signal.aborted) {
    const headers = new Headers({
      Accept: "text/event-stream",
      "Last-Event-ID": String(cursor),
    });
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

    let response: Response;
    try {
      response = await fetch(
        `${apiBaseUrl}/tasks/${encodeURIComponent(taskId)}/events`,
        { headers, credentials: "include", signal },
      );
    } catch (error) {
      if (signal.aborted) return;
      delay = Math.min(delay * 2, 15_000);
      await waitForReconnect(delay, signal);
      continue;
    }
    if (response.status === 401 && !refreshed) {
      await authApi.refresh();
      refreshed = true;
      continue;
    }
    if (response.status >= 500) {
      delay = Math.min(delay * 2, 15_000);
      await waitForReconnect(delay, signal);
      continue;
    }
    if (!response.ok || !response.body) {
      throw new Error(`Unable to connect to task events (${response.status}).`);
    }
    refreshed = false;
    delay = 1000;

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let terminal = false;
    try {
      while (!signal.aborted) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        let boundary = buffer.indexOf("\n\n");
        while (boundary >= 0) {
          const block = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          const lines = block.split("\n");
          const idLine = lines.find((line) => line.startsWith("id:"));
          const data = lines
            .filter((line) => line.startsWith("data:"))
            .map((line) => line.slice(5).trim())
            .join("\n");
          if (idLine) cursor = Math.max(cursor, Number(idLine.slice(3).trim()) || 0);
          if (data) {
            const event = JSON.parse(data) as TaskEvent;
            event.event_id = cursor;
            onEvent(event);
            terminal = terminalEventTypes.has(event.type);
          }
          boundary = buffer.indexOf("\n\n");
        }
      }
    } catch (error) {
      if (signal.aborted) return;
      throw error;
    } finally {
      await reader.cancel().catch(() => undefined);
    }
    if (terminal || signal.aborted) return;
    delay = Math.min(delay * 2, 15_000);
    await waitForReconnect(delay, signal);
  }
}

export async function downloadApprovedReport(
  reportId: string,
  format: "markdown" | "pdf" | "docx",
): Promise<void> {
  const url = `${apiBaseUrl}/reports/${encodeURIComponent(reportId)}/export/${format}`;
  const requestDownload = () =>
    fetch(url, {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
      credentials: "include",
    });
  let response = await requestDownload();
  if (response.status === 401) {
    await authApi.refresh();
    response = await requestDownload();
  }
  if (!response.ok) throw new Error(await errorMessage(response));
  const objectUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = `research-report-${reportId}.${format === "markdown" ? "md" : format}`;
  link.click();
  URL.revokeObjectURL(objectUrl);
}

export async function checkReadiness(): Promise<boolean> {
  try {
    const response = await fetch(`${apiBaseUrl.replace(/\/api\/v1\/?$/, "")}/health/ready`);
    return response.ok;
  } catch {
    return false;
  }
}
