/**
 * Typed client for the v0.4a backend.
 *
 * Endpoint shapes mirror ``src/msrt/ui_server/schemas.py`` exactly.
 * Keep the two in sync; if the Python side adds a field, add it here
 * and lean on TypeScript to flag the call sites that need updating.
 */

export type JobKind = "local" | "url" | "url_batch";

export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "partial"
  | "failed"
  | "cancelled";

export type JobPhase =
  | "queued"
  | "preflight"
  | "fetch"
  | "auto_glossary"
  | "collect"
  | "translate"
  | "postprocess"
  | "package"
  | "done"
  | "error";

export type Renderer = "mitr-default" | "mitr-manga2eng" | "custom-postprocess";

export interface JobOptions {
  format: "pdf" | "cbz" | "both";
  model: string | null;
  renderer: Renderer;
  lang_source: string;
  lang_target: string;
  no_gpu: boolean;
  auto_glossary: boolean;
  glossary_path: string | null;
  pre_dict_path: string | null;
  font_path: string | null;
  site: string;
  skip_existing: boolean;
  continue_on_error: boolean;
  range_filter: string | null;
  chapters_filter: string | null;
  limit: number | null;
}

export interface JobCreate {
  kind: JobKind;
  input_url?: string | null;
  input_dir?: string | null;
  out_dir?: string;
  series?: string | null;
  chapter_number?: string | null;
  chapter_title?: string | null;
  options?: Partial<JobOptions>;
  i_own_rights?: boolean;
}

export interface Job {
  id: string;
  kind: JobKind;
  status: JobStatus;
  request: JobCreate;
  current_phase: JobPhase;
  chapters_total: number;
  chapters_done: number;
  chapters_failed: number;
  output_files: string[];
  manifest_paths: string[];
  errors: string[];
  warnings: string[];
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface JobList {
  jobs: Job[];
}

export interface SettingsView {
  default_model: string;
  /** Per-provider preferred model alias used by the fallback chain. */
  model_openai: string;
  model_anthropic: string;
  model_google: string;
  litellm_port: number;
  litellm_base_url: string;
  cache_dir: string;
  mitr_bin_path: string | null;
  has_anthropic_key: boolean;
  has_openai_key: boolean;
  has_gemini_key: boolean;
  auto_cover_enabled: boolean;
  /** Persisted UI language, mirrored from MSRT_UI_LANG. */
  ui_language: "it" | "en";
}

export type SecretName =
  | "OPENAI_API_KEY"
  | "ANTHROPIC_API_KEY"
  | "GEMINI_API_KEY";

export interface SecretReportResponse {
  name: SecretName;
  backend: "keychain" | "dotenv";
  message: string;
}

export interface SetupTestResult {
  ok: boolean;
  message: string;
  latency_ms: number | null;
}

export interface DefaultModelResponse {
  default_model: string;
}

export interface ProviderModelsRequest {
  openai?: string;
  anthropic?: string;
  google?: string;
}

export interface ProviderModelsResponse {
  model_openai: string;
  model_anthropic: string;
  model_google: string;
  message: string;
}

export interface DoctorCheckView {
  name: string;
  status: string;
  message: string;
  detail: string | null;
}

export interface DoctorReport {
  checks: DoctorCheckView[];
  overall_status: "ok" | "warn" | "fail";
}

export interface ServerActionResponse {
  action: "up" | "down" | "status";
  running: boolean;
  healthy: boolean;
  pid: number | null;
  message: string;
  log_path: string;
}

export interface DryRunRequest {
  url: string;
  site?: string;
  range_filter?: string | null;
  chapters_filter?: string | null;
  limit?: number | null;
}

export interface DryRunChapter {
  url: string;
  chapter_number: string;
  title: string | null;
  series: string | null;
  output_exists: boolean;
}

export interface DryRunResponse {
  site: string;
  total: number;
  selected: number;
  chapters: DryRunChapter[];
}

export interface CoverageChapter {
  chapter_number: string;
  url: string;
  title: string | null;
  series: string | null;
  on_disk: boolean;
  in_range: boolean;
}

export interface CoverageRequest {
  url: string;
  site?: string;
  out_dir?: string;
  range_filter?: string | null;
  fmt?: "pdf" | "cbz" | "both";
  lang_target?: string;
}

export interface CoverageResponse {
  site: string;
  available: CoverageChapter[];
  available_count: number;
  on_disk_count: number;
  missing_before_range: CoverageChapter[];
  missing_after_range: CoverageChapter[];
}

export interface LibraryEntry {
  manifest_id: string;
  manifest_path: string;
  series: string | null;
  chapter_number: string | null;
  chapter_title: string | null;
  language_target: string | null;
  output_files: string[];
  started_at: string | null;
  finished_at: string | null;
  model_alias: string | null;
  provider: string | null;
  strategy: string | null;
  source_url: string | null;
  errors: string[];
  warnings: string[];
}

export interface LibraryResponse {
  entries: LibraryEntry[];
}

export interface HealthResponse {
  status: "ok";
  version: string;
  server_started_at: string;
}

class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly url: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail = await response.text();
    try {
      const parsed = JSON.parse(detail) as { detail?: string };
      if (parsed.detail) detail = parsed.detail;
    } catch {
      // Non-JSON error body — keep raw text.
    }
    throw new ApiError(
      detail || `HTTP ${response.status} on ${path}`,
      response.status,
      path,
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  settings: () => request<SettingsView>("/api/settings"),
  doctor: (model?: string) =>
    request<DoctorReport>(
      `/api/doctor${model ? `?model=${encodeURIComponent(model)}` : ""}`,
    ),

  serverStatus: () => request<ServerActionResponse>("/api/server"),
  serverUp: () =>
    request<ServerActionResponse>("/api/server/up", { method: "POST" }),
  serverDown: () =>
    request<ServerActionResponse>("/api/server/down", { method: "POST" }),

  saveKey: (name: SecretName, value: string) =>
    request<SecretReportResponse>("/api/setup/save-key", {
      method: "POST",
      body: JSON.stringify({ name, value }),
    }),
  deleteKey: (name: SecretName) =>
    request<SecretReportResponse>("/api/setup/delete-key", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  testModel: (model: string) =>
    request<SetupTestResult>("/api/setup/test-key", {
      method: "POST",
      body: JSON.stringify({ model }),
    }),
  setDefaultModel: (model: string) =>
    request<DefaultModelResponse>("/api/setup/default-model", {
      method: "POST",
      body: JSON.stringify({ model }),
    }),
  setAutoCover: (enabled: boolean) =>
    request<{ auto_cover_enabled: boolean }>("/api/setup/auto-cover", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
  setProviderModels: (body: ProviderModelsRequest) =>
    request<ProviderModelsResponse>("/api/setup/provider-models", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  setUiLanguage: (language: "it" | "en") =>
    request<{ ui_language: "it" | "en" }>("/api/setup/ui-language", {
      method: "POST",
      body: JSON.stringify({ language }),
    }),

  dryRun: (body: DryRunRequest) =>
    request<DryRunResponse>("/api/chapters/dry-run", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  coverage: (body: CoverageRequest) =>
    request<CoverageResponse>("/api/chapters/coverage", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  jobs: () => request<JobList>("/api/jobs"),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  createJob: (body: JobCreate) =>
    request<Job>("/api/jobs", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  cancelJob: (id: string) =>
    request<Job>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  retryFailed: (id: string) =>
    request<Job>(`/api/jobs/${id}/retry-failed`, { method: "POST" }),

  diagnostics: () => request<Record<string, unknown>>("/api/diagnostics"),

  library: (out = "out") =>
    request<LibraryResponse>(`/api/library?out=${encodeURIComponent(out)}`),
  libraryEntry: (manifestId: string, out = "out") =>
    request<LibraryEntry>(
      `/api/library/${encodeURIComponent(manifestId)}?out=${encodeURIComponent(out)}`,
    ),

  openPath: (path: string) =>
    request<void>("/api/open-path", {
      method: "POST",
      body: JSON.stringify({ path }),
    }),

  /** Build a cover-image URL the browser can load via ``<img src>``.
   *  The endpoint falls back through MangaDex → AniList → composite
   *  poster from on-disk scans → AI-generated → 404. The UI swaps to
   *  a gradient placeholder ``onError``. */
  coverUrl: (
    series: string,
    options: { sourceUrl?: string | null; outDir?: string } = {},
  ): string => {
    const params = new URLSearchParams({ series });
    if (options.sourceUrl) params.set("source_url", options.sourceUrl);
    if (options.outDir) params.set("out_dir", options.outDir);
    return `/api/covers?${params.toString()}`;
  },
};

export { ApiError };
