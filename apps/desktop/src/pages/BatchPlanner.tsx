/**
 * Batch Planner — UI interattiva sopra ``/api/chapters/dry-run`` +
 * ``/api/jobs`` (kind ``url_batch``).
 *
 * L'utente incolla l'URL della serie, lancia un dry-run, vede la
 * tabella capitoli, applica selettori (range / explicit / limit)
 * verificando in tempo reale quante entry rimangono, e infine fa
 * partire il batch ricevendo subito la redirezione a JobProgress.
 */

import { ChevronRight, Filter, Layers, RefreshCcw, ShieldAlert } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import type { DryRunChapter, DryRunResponse, JobCreate } from "../lib/api";
import { StatusPill } from "../components/StatusPill";

interface PlannerState {
  url: string;
  site: string;
  range: string;
  chapters: string;
  limit: string;
  iOwnRights: boolean;
}

const INITIAL: PlannerState = {
  url: "",
  site: "auto",
  range: "",
  chapters: "",
  limit: "",
  iOwnRights: false,
};

export function BatchPlannerPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<PlannerState>(INITIAL);
  const [result, setResult] = useState<DryRunResponse | null>(null);

  const dryRun = useMutation({
    mutationFn: () =>
      api.dryRun({
        url: form.url.trim(),
        site: form.site || "auto",
        range_filter: form.range.trim() || undefined,
        chapters_filter: form.chapters.trim() || undefined,
        limit: form.limit.trim() ? Number(form.limit) : undefined,
      }),
    onSuccess: (data) => setResult(data),
  });

  const submit = useMutation({
    mutationFn: (request: JobCreate) => api.createJob(request),
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
  });

  const update = <K extends keyof PlannerState>(key: K, value: PlannerState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const onPreview = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.url.trim()) return;
    dryRun.mutate();
  };

  const onLaunch = () => {
    if (!result || !form.iOwnRights) return;
    const request: JobCreate = {
      kind: "url_batch",
      input_url: form.url.trim(),
      i_own_rights: true,
      options: {
        site: form.site || "auto",
        range_filter: form.range.trim() || null,
        chapters_filter: form.chapters.trim() || null,
        limit: form.limit.trim() ? Number(form.limit) : null,
      },
    };
    submit.mutate(request);
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Batch</h1>
        <p className="text-sm text-slate-500">
          Dry-run su URL di una serie supportata, scelta capitoli, lancio
          del batch.
        </p>
      </header>

      <form
        onSubmit={onPreview}
        className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_140px_140px]">
          <Field label="URL serie/capitolo">
            <input
              value={form.url}
              onChange={(e) => update("url", e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1"
              placeholder="https://mangadex.org/title/<UUID> o /chapter/<UUID>"
              required
            />
          </Field>
          <Field label="Site">
            <input
              value={form.site}
              onChange={(e) => update("site", e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1"
            />
          </Field>
          <button
            type="submit"
            disabled={dryRun.isPending || !form.url.trim()}
            className="inline-flex h-9 items-center justify-center gap-1.5 self-end rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCcw size={14} />
            {dryRun.isPending ? "Dry-run…" : "Esegui dry-run"}
          </button>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <Field label="Range" hint="50-51">
            <input
              value={form.range}
              onChange={(e) => update("range", e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1"
            />
          </Field>
          <Field label="Capitoli espliciti" hint="50,51,51.1">
            <input
              value={form.chapters}
              onChange={(e) => update("chapters", e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1"
            />
          </Field>
          <Field label="Limit" hint="primi N dopo i filtri">
            <input
              inputMode="numeric"
              value={form.limit}
              onChange={(e) => update("limit", e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-1"
            />
          </Field>
        </div>

        {dryRun.error && (
          <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
            {dryRun.error.message}
          </div>
        )}
      </form>

      {result && <ResultCard result={result} />}

      {result && (
        <RightsAndLaunch
          chapters={result.selected}
          iOwnRights={form.iOwnRights}
          onToggleRights={(v) => update("iOwnRights", v)}
          submitting={submit.isPending}
          submitError={submit.error?.message}
          onLaunch={onLaunch}
        />
      )}
    </div>
  );
}

function ResultCard({ result }: { result: DryRunResponse }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Capitoli selezionati
        </h2>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <StatusPill tone="info">{result.site}</StatusPill>
          <span>
            <Filter size={12} className="-mt-0.5 mr-1 inline-block" />
            {result.selected} di {result.total}
          </span>
        </div>
      </header>
      <div className="overflow-hidden rounded-md border border-slate-200">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2">#</th>
              <th className="px-3 py-2">Capitolo</th>
              <th className="px-3 py-2">Titolo</th>
              <th className="px-3 py-2">URL</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {result.chapters.map((ch, i) => (
              <ChapterRow key={ch.url} index={i + 1} chapter={ch} />
            ))}
            {result.chapters.length === 0 && (
              <tr>
                <td
                  colSpan={4}
                  className="px-3 py-6 text-center text-xs text-slate-400"
                >
                  Nessun capitolo dopo i filtri.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ChapterRow({
  index,
  chapter,
}: {
  index: number;
  chapter: DryRunChapter;
}) {
  return (
    <tr>
      <td className="px-3 py-2 font-mono text-xs text-slate-400">{index}</td>
      <td className="px-3 py-2 font-medium">ch. {chapter.chapter_number}</td>
      <td className="px-3 py-2 text-slate-600">{chapter.title ?? "—"}</td>
      <td className="px-3 py-2">
        <a
          href={chapter.url}
          target="_blank"
          rel="noreferrer"
          className="truncate font-mono text-xs text-slate-500 hover:text-slate-900"
        >
          {chapter.url}
        </a>
      </td>
    </tr>
  );
}

function RightsAndLaunch({
  chapters,
  iOwnRights,
  onToggleRights,
  submitting,
  submitError,
  onLaunch,
}: {
  chapters: number;
  iOwnRights: boolean;
  onToggleRights: (v: boolean) => void;
  submitting: boolean;
  submitError?: string | null;
  onLaunch: () => void;
}) {
  return (
    <section className="space-y-3 rounded-xl border border-amber-300 bg-amber-50 p-5">
      <div className="flex items-start gap-3">
        <ShieldAlert className="mt-0.5 text-amber-600" size={18} />
        <div className="flex-1 space-y-2">
          <p className="text-sm text-amber-900">
            Stai per scaricare e tradurre {chapters} capitoli. Conferma di
            avere il diritto di scaricare il contenuto. Guardrail UX, non
            tutela legale.
          </p>
          <label className="inline-flex items-center gap-2 text-sm text-amber-900">
            <input
              type="checkbox"
              checked={iOwnRights}
              onChange={(e) => onToggleRights(e.target.checked)}
              className="h-4 w-4 rounded border-amber-400 text-sky-600 focus:ring-sky-400"
            />
            Confermo di avere i diritti (--i-own-rights)
          </label>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs text-amber-800">
          Il batch parte sequenziale (worker FIFO single-instance).
        </span>
        <button
          type="button"
          disabled={!iOwnRights || submitting || chapters === 0}
          onClick={onLaunch}
          className="inline-flex items-center gap-2 rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Layers size={14} />
          {submitting ? "Invio…" : "Avvia batch"}
          <ChevronRight size={14} />
        </button>
      </div>
      {submitError && (
        <p className="text-xs text-rose-700">{submitError}</p>
      )}
    </section>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-slate-400">{hint}</span>}
    </label>
  );
}
