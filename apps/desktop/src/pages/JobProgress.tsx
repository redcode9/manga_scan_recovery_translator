/**
 * Job progress live — vista a singolo job.
 *
 * Per ``url_batch`` mostra la barra manga-level (capitoli totali),
 * la card del capitolo in lavorazione con barra pagine real-time
 * basata sugli eventi SSE ``progress``, e una tabella con tutti i
 * capitoli e il loro stato (done/failed/skipped/queued/running).
 *
 * Per ``local`` / ``url`` (singolo capitolo) mostra solo la barra
 * pagine + log feed, senza la tabella.
 */

import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ChevronRight,
  CircleX,
  ExternalLink,
  FileText,
  Loader2,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../lib/api";
import type { CoverageResponse, Job, JobStatus } from "../lib/api";
import { useJobEvents } from "../lib/events";
import type { JobEvent } from "../lib/events";
import {
  formatDuration,
  formatTimestamp,
  pathBasename,
} from "../lib/format";
import { StatusPill } from "../components/StatusPill";

export function JobProgressPage() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const job = useQuery({
    queryKey: ["job", id],
    queryFn: () => api.job(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data as Job | undefined;
      if (!data) return 1_000;
      return TERMINAL_STATES.has(data.status) ? false : 2_000;
    },
  });

  const cancel = useMutation({
    mutationFn: () => api.cancelJob(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["job", id] }),
  });

  const retryFailed = useMutation({
    mutationFn: () => api.retryFailed(id),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      navigate(`/jobs/${created.id}`);
    },
  });

  const { events } = useJobEvents(id);

  // For batch jobs, fetch the coverage view so we can compute the
  // manga-level percentage ("how close are we to having every
  // available chapter on disk"). One-time fetch — refetch is driven
  // by job.refetchInterval via the chapters_done invariant.
  const isBatch = job.data?.kind === "url_batch";
  const coverage = useQuery({
    queryKey: [
      "coverage",
      job.data?.request.input_url ?? "",
      job.data?.request.options?.lang_target ?? "it",
      job.data?.request.options?.format ?? "pdf",
    ],
    enabled: Boolean(isBatch && job.data?.request.input_url),
    queryFn: () =>
      api.coverage({
        url: job.data!.request.input_url!,
        site: job.data!.request.options?.site ?? "auto",
        out_dir: String(job.data!.request.out_dir ?? "out"),
        fmt: job.data!.request.options?.format ?? "pdf",
        lang_target: job.data!.request.options?.lang_target ?? "it",
        range_filter: job.data!.request.options?.range_filter ?? null,
      }),
    staleTime: 30_000,
  });

  if (!id) {
    return <p className="text-sm text-rose-300">ID job mancante.</p>;
  }
  if (job.isLoading) {
    return (
      <p className="flex items-center gap-2 text-sm text-zinc-500">
        <Loader2 className="animate-spin" size={16} />
        Caricamento job…
      </p>
    );
  }
  if (job.error) {
    return (
      <div className="rounded-md border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
        {job.error.message}
      </div>
    );
  }
  if (!job.data) return null;

  return (
    <div className="space-y-6">
      <Header
        job={job.data}
        onCancel={() => cancel.mutate()}
        cancelling={cancel.isPending}
        onRetryFailed={() => retryFailed.mutate()}
        retrying={retryFailed.isPending}
        retryError={retryFailed.error?.message}
      />

      {isBatch && (
        <BatchProgressCard
          job={job.data}
          events={events}
          coverage={coverage.data}
        />
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <CurrentChapterCard job={job.data} events={events} />
        <OutputsCard job={job.data} />
      </div>

      {isBatch && coverage.data && (
        <ChapterTable job={job.data} coverage={coverage.data} />
      )}

      <LogFeed events={events} />
    </div>
  );
}

const TERMINAL_STATES = new Set<JobStatus>([
  "succeeded",
  "partial",
  "failed",
  "cancelled",
]);

function Header({
  job,
  onCancel,
  cancelling,
  onRetryFailed,
  retrying,
  retryError,
}: {
  job: Job;
  onCancel: () => void;
  cancelling: boolean;
  onRetryFailed: () => void;
  retrying: boolean;
  retryError: string | undefined;
}) {
  const canCancel = !TERMINAL_STATES.has(job.status);
  const canRetry =
    job.kind === "url_batch" &&
    TERMINAL_STATES.has(job.status) &&
    job.chapters_failed > 0;

  return (
    <header className="space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.12em] text-zinc-500">
            Job
          </div>
          <h1 className="font-mono text-2xl font-semibold tracking-tight text-zinc-100">
            {job.id}
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            <span className="font-medium text-zinc-300">{job.kind}</span>
            {" · "}
            <span>creato {formatTimestamp(job.created_at)}</span>
            {job.started_at && (
              <>
                {" · "}durata{" "}
                {formatDuration(
                  job.started_at,
                  job.finished_at ?? new Date().toISOString(),
                )}
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusPill tone={statusTone(job.status)}>
            {statusIcon(job.status)} {job.status}
          </StatusPill>
          {canRetry && (
            <button
              type="button"
              disabled={retrying}
              onClick={onRetryFailed}
              className="inline-flex items-center gap-1.5 rounded-md bg-amber-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-amber-400 disabled:opacity-50"
              title={`Rilancia i ${job.chapters_failed} capitoli falliti`}
            >
              {retrying ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <RotateCcw size={14} />
              )}
              Riprova falliti ({job.chapters_failed})
            </button>
          )}
          {canCancel && (
            <button
              type="button"
              disabled={cancelling}
              onClick={onCancel}
              className="inline-flex items-center gap-1.5 rounded-md bg-rose-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-rose-400 disabled:opacity-50"
            >
              <Ban size={14} />
              Annulla
            </button>
          )}
          <Link
            to="/library"
            className="inline-flex items-center gap-1.5 rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-zinc-200 transition hover:bg-white/15"
          >
            Libreria
            <ChevronRight size={14} />
          </Link>
        </div>
      </div>
      {retryError && (
        <p className="text-xs text-rose-300">Retry fallito: {retryError}</p>
      )}
    </header>
  );
}

interface PerChapter {
  number: string;
  status: "queued" | "running" | "done" | "failed" | "skipped";
  message?: string;
  output?: string;
}

/**
 * Reduce job.errors / warnings / output_files / current chapter to a
 * single map keyed by chapter number, using the canonical
 * ``msrt-run-<series>-<number>-<lang>.json`` manifest filenames as
 * the source of truth for "done".
 */
function reduceChapterStates(
  job: Job,
  events: JobEvent[],
): Map<string, PerChapter> {
  const map = new Map<string, PerChapter>();

  // ``done`` from manifest paths
  for (const path of job.manifest_paths) {
    const match = /msrt-run-.+-([\d.]+)-[a-z]{2,3}\.json$/.exec(path);
    if (match && match[1]) {
      map.set(match[1], { number: match[1], status: "done", output: path });
    }
  }
  // ``done`` from output_files (fallback if manifest_paths missed it)
  for (const path of job.output_files) {
    const match = /-([\d.]+)-[a-z]{2,3}\.(?:pdf|cbz)$/.exec(path);
    if (match && match[1] && !map.has(match[1])) {
      map.set(match[1], { number: match[1], status: "done", output: path });
    }
  }
  // ``failed`` from errors of the form ``ch.<n>: <msg>``
  for (const err of job.errors) {
    const match = /^ch\.([^:]+):\s*(.*)$/i.exec(err);
    if (match) {
      const number = match[1].trim();
      map.set(number, {
        number,
        status: "failed",
        message: match[2].slice(0, 240),
      });
    }
  }
  // ``skipped`` from warnings of the form ``ch.<n>: ...``
  for (const warn of job.warnings) {
    const match = /^ch\.([^:]+):\s*(.*)$/i.exec(warn);
    if (match) {
      const number = match[1].trim();
      // Don't overwrite a more specific status (done/failed).
      if (!map.has(number)) {
        map.set(number, {
          number,
          status: "skipped",
          message: match[2].slice(0, 240),
        });
      }
    }
  }
  // ``running`` from latest phase event with chapter set, while job still active.
  if (!TERMINAL_STATES.has(job.status)) {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const ev = events[i];
      if (ev.type === "phase" && ev.chapter) {
        const number = ev.chapter;
        const existing = map.get(number);
        if (!existing || existing.status === "queued") {
          map.set(number, { number, status: "running" });
        }
        break;
      }
    }
  }
  return map;
}

function BatchProgressCard({
  job,
  events,
  coverage,
}: {
  job: Job;
  events: JobEvent[];
  coverage: CoverageResponse | undefined;
}) {
  const total = job.chapters_total || 1;
  const done = job.chapters_done;
  const failed = job.chapters_failed;
  const pct = Math.min(100, Math.round((done / total) * 100));

  // Manga-level: how many of "all available chapters on the source"
  // are now on disk. The denominator stays stable across runs so the
  // user can see incremental progress between batches.
  const mangaDone = coverage?.on_disk_count ?? 0;
  const mangaTotal = coverage?.available_count ?? 0;
  const mangaPct = mangaTotal
    ? Math.min(100, Math.round((mangaDone / mangaTotal) * 100))
    : null;

  // Currently running chapter: latest non-terminal event with chapter.
  const running = useMemo(() => {
    if (TERMINAL_STATES.has(job.status)) return null;
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const ev = events[i];
      if (ev.chapter) return ev.chapter;
    }
    return null;
  }, [events, job.status]);

  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-6 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <header className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-[0.12em] text-zinc-400">
            Avanzamento batch
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            {running
              ? `In lavorazione: capitolo ${running}`
              : TERMINAL_STATES.has(job.status)
                ? "Job terminato"
                : "In coda"}
          </p>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="font-mono text-2xl font-semibold text-zinc-100">
            {pct}%
          </span>
        </div>
      </header>

      <div className="space-y-4">
        <ProgressBar
          label={`Batch corrente: ${done}/${total} capitoli${
            failed > 0 ? ` · ${failed} falliti` : ""
          }`}
          pct={pct}
        />
        {mangaPct !== null && (
          <ProgressBar
            label={`Manga totale (capitoli su disco): ${mangaDone}/${mangaTotal}`}
            pct={mangaPct}
            tone="emerald"
          />
        )}
      </div>
    </section>
  );
}

function ProgressBar({
  label,
  pct,
  tone = "sky",
}: {
  label: string;
  pct: number;
  tone?: "sky" | "emerald" | "amber";
}) {
  const colour = {
    sky: "bg-sky-400",
    emerald: "bg-emerald-400",
    amber: "bg-amber-400",
  }[tone];
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="text-zinc-400">{label}</span>
        <span className="font-mono text-zinc-500">{pct}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/5">
        <div
          className={`h-full rounded-full ${colour} transition-[width] duration-500 ease-out`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function CurrentChapterCard({
  job,
  events,
}: {
  job: Job;
  events: JobEvent[];
}) {
  const lastPhase = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      if (events[i].type === "phase") return events[i].phase ?? job.current_phase;
    }
    return job.current_phase;
  }, [events, job.current_phase]);

  // Latest progress event with unit=pages → per-chapter page-level
  // bar. Backend emits this every ~2s while the watcher is alive.
  const lastPagesProgress = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const ev = events[i];
      if (ev.type === "progress" && ev.unit === "pages") return ev;
    }
    return null;
  }, [events]);

  const pagesPct = lastPagesProgress
    ? Math.round(
        ((lastPagesProgress.current ?? 0) / Math.max(1, lastPagesProgress.total ?? 1)) *
          100,
      )
    : null;

  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset] lg:col-span-2">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
        Capitolo in lavorazione
      </h2>
      <div className="space-y-3 text-sm">
        {pagesPct !== null && (
          <ProgressBar
            label={`Pagine: ${lastPagesProgress!.current}/${lastPagesProgress!.total}`}
            pct={pagesPct}
            tone="sky"
          />
        )}
        <Row label="Fase corrente" value={lastPhase ?? "—"} />
        {job.request.kind !== "local" && (
          <Row label="URL" value={job.request.input_url ?? "—"} mono />
        )}
        {job.request.kind === "local" && (
          <Row
            label="Cartella"
            value={String(job.request.input_dir ?? "—")}
            mono
          />
        )}
        <Row label="Modello" value={job.request.options?.model ?? "MSRT_MODEL"} />
      </div>
    </section>
  );
}

function ChapterTable({
  job,
  coverage,
}: {
  job: Job;
  coverage: CoverageResponse;
}) {
  const states = useMemo(() => reduceChapterStates(job, []), [job]);
  // Build a row per chapter the source exposes; merge with job-derived
  // states so chapters never run yet show as "queued" but visible.
  const rows = useMemo(() => {
    const range = job.request.options?.range_filter ?? null;
    const inRange = (number: string): boolean => {
      if (!range) return true;
      const match = /^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$/.exec(range);
      if (!match) return true;
      const num = Number(number);
      const low = Number(match[1]);
      const high = Number(match[2]);
      return Number.isFinite(num) && num >= low && num <= high;
    };
    return coverage.available.map((chapter) => {
      const fromState = states.get(chapter.chapter_number);
      const status: PerChapter["status"] = fromState
        ? fromState.status
        : chapter.on_disk
          ? "done"
          : inRange(chapter.chapter_number)
            ? "queued"
            : "skipped";
      return {
        chapter,
        status,
        message: fromState?.message,
      };
    });
  }, [coverage, job.request.options?.range_filter, states]);

  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <header className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
          Capitoli ({rows.length})
        </h2>
        <div className="flex gap-2 text-[11px]">
          <Legend tone="ok" label="done" />
          <Legend tone="live" label="running" />
          <Legend tone="warn" label="skipped" />
          <Legend tone="fail" label="failed" />
          <Legend tone="muted" label="queued" />
        </div>
      </header>
      <div className="overflow-hidden rounded-lg border border-white/5">
        <table className="w-full text-sm">
          <thead className="bg-white/5 text-left text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-3 py-2 w-20">Capitolo</th>
              <th className="px-3 py-2 w-32">Stato</th>
              <th className="px-3 py-2">Note</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.map(({ chapter, status, message }) => (
              <tr
                key={chapter.chapter_number}
                className={
                  status === "running" ? "bg-sky-500/5" : "hover:bg-white/5"
                }
              >
                <td className="px-3 py-1.5 font-mono text-zinc-200">
                  {chapter.chapter_number}
                </td>
                <td className="px-3 py-1.5">
                  <ChapterStatusPill status={status} />
                </td>
                <td className="px-3 py-1.5 text-xs text-zinc-400">
                  {message ?? chapter.title ?? ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ChapterStatusPill({ status }: { status: PerChapter["status"] }) {
  const tone =
    status === "done"
      ? "ok"
      : status === "running"
        ? "live"
        : status === "failed"
          ? "fail"
          : status === "skipped"
            ? "warn"
            : "muted";
  return (
    <StatusPill tone={tone}>
      {status === "running" && (
        <span className="msrt-pulse inline-block h-1.5 w-1.5 rounded-full bg-current" />
      )}
      {status}
    </StatusPill>
  );
}

function Legend({
  tone,
  label,
}: {
  tone: "ok" | "warn" | "fail" | "info" | "muted" | "live";
  label: string;
}) {
  return <StatusPill tone={tone}>{label}</StatusPill>;
}

function OutputsCard({ job }: { job: Job }) {
  const open = useMutation({ mutationFn: (path: string) => api.openPath(path) });
  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
        Output
      </h2>
      {job.output_files.length === 0 ? (
        <p className="text-sm text-zinc-500">
          Nessun file prodotto (ancora). Compaiono qui non appena il
          packaging termina.
        </p>
      ) : (
        <ul className="space-y-1">
          {job.output_files.slice(-12).map((path) => (
            <li
              key={path}
              className="flex items-center justify-between gap-2 rounded-md bg-white/5 px-3 py-2 text-xs"
            >
              <span className="flex items-center gap-2 truncate font-mono text-zinc-300">
                <FileText size={14} className="shrink-0 text-zinc-500" />
                {pathBasename(path)}
              </span>
              <button
                type="button"
                onClick={() => open.mutate(path)}
                className="inline-flex items-center gap-1 text-sky-300 hover:text-sky-200 hover:underline"
              >
                <ExternalLink size={12} />
                apri
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function LogFeed({ events }: { events: JobEvent[] }) {
  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <details>
        <summary className="cursor-pointer select-none text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400 hover:text-zinc-200">
          Log live ({events.length})
        </summary>
        {events.length === 0 ? (
          <p className="mt-3 text-sm text-zinc-500">In attesa di eventi…</p>
        ) : (
          <ol className="mt-3 max-h-96 space-y-1 overflow-y-auto rounded-md bg-black/40 p-3 font-mono text-[11px] text-zinc-200">
            {events.map((event, i) => (
              <li key={i} className="flex gap-2">
                <span className={`shrink-0 ${eventLevelColor(event)}`}>
                  {eventLabel(event)}
                </span>
                <span className="truncate">{eventDetail(event)}</span>
              </li>
            ))}
          </ol>
        )}
      </details>
    </section>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs uppercase tracking-wide text-zinc-500">
        {label}
      </span>
      <span
        className={`truncate text-right text-sm text-zinc-200 ${mono ? "font-mono" : ""}`}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

function statusTone(status: JobStatus) {
  if (status === "succeeded") return "ok";
  if (status === "partial") return "warn";
  if (status === "failed") return "fail";
  if (status === "cancelled") return "warn";
  if (status === "running") return "info";
  return "muted";
}

function statusIcon(status: JobStatus) {
  if (status === "succeeded") return <CheckCircle2 size={12} />;
  if (status === "partial") return <AlertTriangle size={12} />;
  if (status === "failed") return <XCircle size={12} />;
  if (status === "cancelled") return <Ban size={12} />;
  if (status === "running") return <Loader2 size={12} className="animate-spin" />;
  return null;
}

function eventLevelColor(event: JobEvent) {
  if (event.type === "error") return "text-rose-300";
  if (event.type === "warning" || event.level === "warn")
    return "text-amber-300";
  if (event.type === "phase") return "text-sky-300";
  if (event.type === "output") return "text-emerald-300";
  if (event.type === "progress") return "text-zinc-400";
  if (event.type === "job_started" || event.type === "job_finished")
    return "text-zinc-500";
  return "text-zinc-500";
}

function eventLabel(event: JobEvent) {
  if (event.type === "phase") return `[phase:${event.phase}]`;
  if (event.type === "log") return `[${event.level ?? "info"}]`;
  if (event.type === "output") return "[output]";
  if (event.type === "warning") return "[warn]";
  if (event.type === "error") return "[error]";
  if (event.type === "job_started") return "[start]";
  if (event.type === "job_finished") return `[done:${event.status ?? "?"}]`;
  if (event.type === "progress") return `[${event.current}/${event.total}]`;
  return `[${event.type}]`;
}

function eventDetail(event: JobEvent) {
  if (event.message) return event.message;
  if (event.path) return event.path;
  if (event.chapter) return `ch.${event.chapter}`;
  return "";
}

const _CircleX = CircleX; // silences "unused import" while also documenting that the icon is intentionally available for future error rows
void _CircleX;
