/**
 * Job progress live — vista a singolo job con SSE log feed.
 *
 * Polling state HTTP per i totali (ogni 2s) + SSE per gli eventi
 * granulari. Quando il job finisce, lo stream si chiude da solo
 * (sentinel) e il polling smette.
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
import type { Job, JobStatus } from "../lib/api";
import { useJobEvents } from "../lib/events";
import type { JobEvent } from "../lib/events";
import { formatDuration, formatTimestamp, pathBasename } from "../lib/format";
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

  if (!id) {
    return <p className="text-sm text-rose-600">ID job mancante.</p>;
  }

  if (job.isLoading) {
    return (
      <p className="flex items-center gap-2 text-sm text-slate-500">
        <Loader2 className="animate-spin" size={16} />
        Caricamento job…
      </p>
    );
  }

  if (job.error) {
    return (
      <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
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
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <SummaryCard job={job.data} events={events} />
        <OutputsCard job={job.data} />
      </div>
      <LogFeed events={events} />
    </div>
  );
}

const TERMINAL_STATES = new Set<JobStatus>(["succeeded", "failed", "cancelled"]);

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
          <div className="text-xs uppercase tracking-wide text-slate-500">Job</div>
          <h1 className="font-mono text-2xl font-semibold tracking-tight">{job.id}</h1>
          <p className="mt-1 text-sm text-slate-500">
            <span className="font-medium">{job.kind}</span>
            {" · "}
            <span>creato {formatTimestamp(job.created_at)}</span>
            {job.started_at && (
              <>
                {" · "}durata{" "}
                {formatDuration(job.started_at, job.finished_at ?? new Date().toISOString())}
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
              className="inline-flex items-center gap-1.5 rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-amber-700 disabled:opacity-50"
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
              className="inline-flex items-center gap-1.5 rounded-md bg-rose-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-rose-700 disabled:opacity-50"
            >
              <Ban size={14} />
              Annulla
            </button>
          )}
          <Link
            to="/library"
            className="inline-flex items-center gap-1.5 rounded-md bg-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-300"
          >
            Libreria
            <ChevronRight size={14} />
          </Link>
        </div>
      </div>
      {retryError && (
        <p className="text-xs text-rose-600">Retry fallito: {retryError}</p>
      )}
    </header>
  );
}

function SummaryCard({ job, events }: { job: Job; events: JobEvent[] }) {
  const lastPhase = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      if (events[i].type === "phase") return events[i].phase ?? job.current_phase;
    }
    return job.current_phase;
  }, [events, job.current_phase]);

  const total = job.chapters_total || 1;
  const done = job.chapters_done;
  const failed = job.chapters_failed;
  const pct = Math.min(100, Math.round((done / total) * 100));

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Avanzamento
      </h2>
      <div className="space-y-3 text-sm">
        <div>
          <div className="mb-1 flex justify-between text-xs">
            <span className="text-slate-500">
              Capitoli: {done}/{total}
              {failed > 0 && (
                <span className="ml-2 text-rose-600">
                  {failed} falliti
                </span>
              )}
            </span>
            <span className="font-mono text-slate-500">{pct}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full bg-sky-500 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
        <Row label="Fase corrente" value={lastPhase ?? "—"} />
        {job.request.kind !== "local" && (
          <Row label="URL" value={job.request.input_url ?? "—"} mono />
        )}
        {job.request.kind === "local" && (
          <Row label="Cartella" value={String(job.request.input_dir ?? "—")} mono />
        )}
        <Row
          label="Modello"
          value={job.request.options?.model ?? "MSRT_MODEL"}
        />
      </div>
      {(job.errors.length > 0 || job.warnings.length > 0) && (
        <ul className="mt-4 space-y-1">
          {job.errors.map((e) => (
            <li
              key={`e-${e}`}
              className="rounded-md bg-rose-50 px-3 py-2 text-xs text-rose-700"
            >
              <CircleX size={12} className="-mt-0.5 mr-1 inline-block" />
              {e}
            </li>
          ))}
          {job.warnings.map((w) => (
            <li
              key={`w-${w}`}
              className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800"
            >
              <AlertTriangle size={12} className="-mt-0.5 mr-1 inline-block" />
              {w}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function OutputsCard({ job }: { job: Job }) {
  const open = useMutation({ mutationFn: (path: string) => api.openPath(path) });
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Output
      </h2>
      {job.output_files.length === 0 ? (
        <p className="text-sm text-slate-500">
          Nessun file prodotto (ancora). Compaiono qui non appena il
          packaging termina.
        </p>
      ) : (
        <ul className="space-y-1">
          {job.output_files.map((path) => (
            <li
              key={path}
              className="flex items-center justify-between gap-2 rounded-md bg-slate-50 px-3 py-2 text-xs"
            >
              <span className="flex items-center gap-2 font-mono text-slate-700">
                <FileText size={14} className="text-slate-400" />
                {pathBasename(path)}
              </span>
              <button
                type="button"
                onClick={() => open.mutate(path)}
                className="inline-flex items-center gap-1 text-sky-600 hover:underline"
              >
                <ExternalLink size={12} />
                apri
              </button>
            </li>
          ))}
        </ul>
      )}
      {job.manifest_paths.length > 0 && (
        <ul className="mt-3 space-y-1 text-[11px] text-slate-400">
          {job.manifest_paths.map((path) => (
            <li key={path} className="truncate font-mono" title={path}>
              {path}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function LogFeed({ events }: { events: JobEvent[] }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Log live ({events.length})
      </h2>
      {events.length === 0 ? (
        <p className="text-sm text-slate-500">In attesa di eventi…</p>
      ) : (
        <ol className="max-h-80 space-y-1 overflow-y-auto rounded-md bg-slate-900 p-3 font-mono text-[11px] text-slate-100">
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
      <span className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </span>
      <span
        className={`truncate text-right text-sm text-slate-900 ${mono ? "font-mono" : ""}`}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

function statusTone(status: JobStatus) {
  if (status === "succeeded") return "ok";
  if (status === "failed") return "fail";
  if (status === "cancelled") return "warn";
  if (status === "running") return "info";
  return "muted";
}

function statusIcon(status: JobStatus) {
  if (status === "succeeded") return <CheckCircle2 size={12} />;
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
  if (event.type === "job_started" || event.type === "job_finished")
    return "text-slate-300";
  return "text-slate-400";
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
