/**
 * Logs — lista jobs e stream live degli eventi del job selezionato.
 *
 * Riusa ``useJobEvents`` di JobProgress: la differenza è solo il
 * focus (qui mostriamo solo il feed, niente progress bar). Utile per
 * tail-and-debug a distanza.
 */

import { Loader2, RefreshCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { Job, JobStatus } from "../lib/api";
import { useJobEvents } from "../lib/events";
import { formatTimestamp } from "../lib/format";
import { useT } from "../lib/i18n";
import { StatusPill } from "../components/StatusPill";

const STATUS_ORDER: JobStatus[] = ["running", "queued", "succeeded", "failed", "cancelled"];

export function LogsPage() {
  const { t } = useT();
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: api.jobs,
    refetchInterval: 5_000,
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const orderedJobs = useMemo(() => {
    const list = jobs.data?.jobs ?? [];
    return [...list].sort((a, b) => {
      const aIdx = STATUS_ORDER.indexOf(a.status);
      const bIdx = STATUS_ORDER.indexOf(b.status);
      if (aIdx !== bIdx) return aIdx - bIdx;
      return b.created_at.localeCompare(a.created_at);
    });
  }, [jobs.data]);

  const activeId = selectedId ?? orderedJobs[0]?.id ?? null;
  const events = useJobEvents(activeId);

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("logs.title")}
          </h1>
          <p className="text-sm text-zinc-500">{t("logs.subtitle")}</p>
        </div>
        <button
          type="button"
          onClick={() => jobs.refetch()}
          className="inline-flex items-center gap-1 rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-zinc-300 transition hover:bg-white/15"
        >
          <RefreshCcw size={14} />
          {t("common.retry")}
        </button>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px_1fr]">
        <aside className="max-h-[600px] overflow-y-auto rounded-xl border border-white/5 bg-zinc-900/60 p-2 shadow-sm">
          {jobs.isLoading && (
            <p className="flex items-center gap-2 px-2 py-3 text-sm text-zinc-500">
              <Loader2 size={14} className="animate-spin" />
              Carico…
            </p>
          )}
          {!jobs.isLoading && orderedJobs.length === 0 && (
            <p className="px-2 py-3 text-sm text-zinc-500">
              Nessun job. Lancia un job da “Nuovo Job” o “Batch”.
            </p>
          )}
          <ul className="space-y-1">
            {orderedJobs.map((job) => (
              <li key={job.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(job.id)}
                  className={`flex w-full items-start justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition ${
                    activeId === job.id
                      ? "bg-sky-50 ring-1 ring-sky-200"
                      : "hover:bg-white/5"
                  }`}
                >
                  <div className="min-w-0">
                    <div className="font-mono text-xs text-zinc-300">
                      {job.id}
                    </div>
                    <div className="truncate text-xs text-zinc-500">
                      {jobLabel(job)}
                    </div>
                    <div className="text-[11px] text-zinc-500">
                      {formatTimestamp(job.created_at)}
                    </div>
                  </div>
                  <StatusPill tone={statusTone(job.status)}>
                    {job.status}
                  </StatusPill>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="rounded-xl border border-white/5 bg-zinc-900/60 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
          <header className="border-b border-white/5 px-5 py-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
              {activeId ? `Eventi: ${activeId}` : "Seleziona un job"}
            </h2>
          </header>
          <div className="p-3">
            {!activeId ? (
              <p className="text-sm text-zinc-500">
                Nessun job selezionato.
              </p>
            ) : events.events.length === 0 ? (
              <p className="text-sm text-zinc-500">In attesa di eventi…</p>
            ) : (
              <ol className="max-h-[520px] space-y-1 overflow-y-auto rounded-md bg-zinc-100 text-zinc-950 p-3 font-mono text-[11px] text-zinc-100">
                {events.events.map((event, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="shrink-0 text-zinc-500">
                      {event.type}
                    </span>
                    <span className="truncate">
                      {event.message ?? event.path ?? event.phase ?? ""}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function jobLabel(job: Job) {
  if (job.kind === "local") return job.request.input_dir ?? "—";
  return job.request.input_url ?? "—";
}

function statusTone(status: JobStatus) {
  if (status === "succeeded") return "ok";
  if (status === "failed") return "fail";
  if (status === "cancelled") return "warn";
  if (status === "running") return "info";
  return "muted";
}
