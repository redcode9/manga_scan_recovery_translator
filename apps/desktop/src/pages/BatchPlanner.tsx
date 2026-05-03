/**
 * Batch Planner — UI interattiva sopra ``/api/chapters/dry-run`` +
 * ``/api/chapters/coverage`` + ``/api/jobs`` (kind ``url_batch``).
 *
 * L'utente incolla l'URL della serie, lancia un dry-run, vede la
 * tabella capitoli, sceglie selettori (range / explicit / limit). Se
 * il range esclude capitoli che non sono ancora su disco, la pagina
 * lo segnala e chiede esplicitamente se includerli — la classica
 * domanda "vuoi recuperare i mancanti prima/dopo il range?" che
 * altrimenti l'utente si dimentica e produce manga con buchi.
 */

import {
  AlertTriangle,
  ChevronRight,
  Filter,
  Layers,
  RefreshCcw,
  ShieldAlert,
} from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import type {
  CoverageChapter,
  CoverageResponse,
  DryRunChapter,
  DryRunResponse,
  JobCreate,
} from "../lib/api";
import { StatusPill } from "../components/StatusPill";
import { useToast } from "../components/Toast";

interface PlannerState {
  url: string;
  site: string;
  range: string;
  chapters: string;
  limit: string;
  iOwnRights: boolean;
  outDir: string;
  fillBefore: boolean;
  fillAfter: boolean;
}

const INITIAL: PlannerState = {
  url: "",
  site: "auto",
  range: "",
  chapters: "",
  limit: "",
  iOwnRights: false,
  outDir: "out",
  fillBefore: false,
  fillAfter: false,
};

export function BatchPlannerPage() {
  const navigate = useNavigate();
  const toast = useToast();
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
    onError: (err: Error) => toast.error("Dry-run fallito", err.message),
  });

  // Coverage runs alongside the dry-run so the gap panel updates
  // automatically when the user changes the range filter.
  const coverage = useQuery({
    queryKey: ["coverage-planner", form.url, form.range, form.outDir],
    enabled: Boolean(result && form.url.trim()),
    queryFn: () =>
      api.coverage({
        url: form.url.trim(),
        site: form.site || "auto",
        out_dir: form.outDir.trim() || "out",
        range_filter: form.range.trim() || null,
        fmt: "pdf",
        lang_target: "it",
      }),
    staleTime: 30_000,
  });

  // Reset the "fill" toggles every time the gaps recompute, so the
  // user has to consciously opt in (instead of carrying state from a
  // previous URL).
  useEffect(() => {
    setForm((prev) => ({ ...prev, fillBefore: false, fillAfter: false }));
  }, [coverage.data?.missing_before_range.length, coverage.data?.missing_after_range.length]);

  const submit = useMutation({
    mutationFn: (request: JobCreate) => api.createJob(request),
    onSuccess: (job) => {
      toast.success(
        "Batch avviato",
        `Job ${job.id} in coda. Verrai reindirizzato alla pagina di avanzamento.`,
      );
      navigate(`/jobs/${job.id}`);
    },
    onError: (err: Error) => toast.error("Avvio batch fallito", err.message),
  });

  const update = <K extends keyof PlannerState>(key: K, value: PlannerState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const onPreview = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.url.trim()) return;
    dryRun.mutate();
  };

  const plannedChapters = computePlannedChapters(result, coverage.data, form);

  const onLaunch = () => {
    if (!result || !form.iOwnRights) return;
    // When the user opted to fill gaps, switch from range_filter to an
    // explicit chapters_filter built from the combined list. Otherwise
    // honour the range as-is.
    const useExplicit = form.fillBefore || form.fillAfter;
    const request: JobCreate = {
      kind: "url_batch",
      input_url: form.url.trim(),
      i_own_rights: true,
      out_dir: form.outDir.trim() || "out",
      options: {
        site: form.site || "auto",
        range_filter: useExplicit ? null : form.range.trim() || null,
        chapters_filter: useExplicit
          ? plannedChapters.map((ch) => ch.chapter_number).join(",")
          : form.chapters.trim() || null,
        limit: form.limit.trim() ? Number(form.limit) : null,
      },
    };
    submit.mutate(request);
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Batch</h1>
        <p className="text-sm text-zinc-500">
          Dry-run su URL di una serie supportata, scelta capitoli, recupero
          dei mancanti prima/dopo il range, lancio del batch.
        </p>
      </header>

      <form
        onSubmit={onPreview}
        className="space-y-4 rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]"
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_140px_140px]">
          <Field label="URL serie/capitolo">
            <input
              value={form.url}
              onChange={(e) => update("url", e.target.value)}
              className={INPUT_CLASS}
              placeholder="https://mangadex.org/title/<UUID> o /chapter/<UUID>"
              required
            />
          </Field>
          <Field label="Site">
            <input
              value={form.site}
              onChange={(e) => update("site", e.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          <button
            type="submit"
            disabled={dryRun.isPending || !form.url.trim()}
            className="inline-flex h-9 items-center justify-center gap-1.5 self-end rounded-md bg-sky-500/90 px-4 py-2 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCcw size={14} />
            {dryRun.isPending ? "Dry-run…" : "Esegui dry-run"}
          </button>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <Field label="Range" hint="50-51">
            <input
              value={form.range}
              onChange={(e) => update("range", e.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          <Field label="Capitoli espliciti" hint="50,51,51.1">
            <input
              value={form.chapters}
              onChange={(e) => update("chapters", e.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          <Field label="Limit" hint="primi N dopo i filtri">
            <input
              inputMode="numeric"
              value={form.limit}
              onChange={(e) => update("limit", e.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          <Field label="Output dir" hint="dove sono i PDF già fatti">
            <input
              value={form.outDir}
              onChange={(e) => update("outDir", e.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
        </div>

        {dryRun.error && (
          <div className="rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300">
            {dryRun.error.message}
          </div>
        )}
      </form>

      {coverage.data && (
        <CoverageOverview
          coverage={coverage.data}
          fillBefore={form.fillBefore}
          fillAfter={form.fillAfter}
          onToggleBefore={(v) => update("fillBefore", v)}
          onToggleAfter={(v) => update("fillAfter", v)}
        />
      )}

      {result && (
        <ResultCard
          result={result}
          coverage={coverage.data}
          plannedCount={plannedChapters.length}
        />
      )}

      {result && (
        <RightsAndLaunch
          chapters={plannedChapters.length || result.selected}
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

const INPUT_CLASS =
  "w-full rounded-md border border-white/10 bg-zinc-950/60 px-3 py-2 font-mono text-sm text-zinc-100 shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 focus:ring-offset-1 focus:ring-offset-zinc-950";

/**
 * Build the actual list of chapters that the launch button will
 * submit, given the dry-run selection and which gap-fills the user
 * asked for. Used both by the preview ("avvierai N capitoli") and by
 * the request body construction.
 */
function computePlannedChapters(
  result: DryRunResponse | null,
  coverage: CoverageResponse | undefined,
  form: PlannerState,
): CoverageChapter[] {
  if (!result) return [];
  const baseNumbers = new Set(result.chapters.map((c) => c.chapter_number));
  const planned: CoverageChapter[] = [];
  if (coverage) {
    for (const ch of coverage.available) {
      const chosen =
        baseNumbers.has(ch.chapter_number) ||
        (form.fillBefore && coverage.missing_before_range.some((m) => m.chapter_number === ch.chapter_number)) ||
        (form.fillAfter && coverage.missing_after_range.some((m) => m.chapter_number === ch.chapter_number));
      if (chosen) planned.push(ch);
    }
  } else {
    for (const ch of result.chapters) {
      planned.push({
        chapter_number: ch.chapter_number,
        url: ch.url,
        title: ch.title,
        series: ch.series,
        on_disk: false,
        in_range: true,
      });
    }
  }
  return planned;
}

function CoverageOverview({
  coverage,
  fillBefore,
  fillAfter,
  onToggleBefore,
  onToggleAfter,
}: {
  coverage: CoverageResponse;
  fillBefore: boolean;
  fillAfter: boolean;
  onToggleBefore: (v: boolean) => void;
  onToggleAfter: (v: boolean) => void;
}) {
  const beforeCount = coverage.missing_before_range.length;
  const afterCount = coverage.missing_after_range.length;
  const onDiskPct = coverage.available_count
    ? Math.round((coverage.on_disk_count / coverage.available_count) * 100)
    : 0;

  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <header className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
          Copertura manga
        </h2>
        <span className="text-xs text-zinc-500">
          Su disco: <span className="font-mono text-zinc-200">{coverage.on_disk_count}</span>
          {" / "}
          <span className="font-mono">{coverage.available_count}</span>
          {" "}({onDiskPct}%) — sorgente <StatusPill tone="info">{coverage.site}</StatusPill>
        </span>
      </header>
      <div className="mb-4 h-2 overflow-hidden rounded-full bg-white/5">
        <div
          className="h-full rounded-full bg-emerald-400 transition-[width] duration-500 ease-out"
          style={{ width: `${onDiskPct}%` }}
        />
      </div>

      {beforeCount > 0 && (
        <GapPanel
          tone="amber"
          icon={<AlertTriangle size={14} />}
          title={`${beforeCount} capitol${beforeCount === 1 ? "o" : "i"} manca${beforeCount === 1 ? "" : "no"} PRIMA del range`}
          description="Capitoli antecedenti al range richiesto che non hai ancora su disco. Senza un fill esplicito il batch li lascia indietro e produrrai un manga con buchi."
          missing={coverage.missing_before_range}
          checked={fillBefore}
          onToggle={onToggleBefore}
        />
      )}

      {afterCount > 0 && (
        <GapPanel
          tone="info"
          icon={<AlertTriangle size={14} />}
          title={`${afterCount} capitol${afterCount === 1 ? "o" : "i"} successiv${afterCount === 1 ? "o" : "i"} al range`}
          description="Capitoli pubblicati dopo il range richiesto e non ancora su disco."
          missing={coverage.missing_after_range}
          checked={fillAfter}
          onToggle={onToggleAfter}
        />
      )}

      {beforeCount === 0 && afterCount === 0 && (
        <p className="text-xs text-zinc-500">
          Nessun capitolo mancante fuori dal range corrente. ✨
        </p>
      )}
    </section>
  );
}

function GapPanel({
  tone,
  icon,
  title,
  description,
  missing,
  checked,
  onToggle,
}: {
  tone: "amber" | "info";
  icon: React.ReactNode;
  title: string;
  description: string;
  missing: CoverageChapter[];
  checked: boolean;
  onToggle: (v: boolean) => void;
}) {
  const palette =
    tone === "amber"
      ? "border-amber-500/30 bg-amber-500/10 text-amber-100"
      : "border-sky-500/30 bg-sky-500/10 text-sky-100";
  return (
    <div className={`mt-3 rounded-xl border p-4 ${palette}`}>
      <div className="flex items-start gap-3">
        <span className="mt-0.5 text-current">{icon}</span>
        <div className="flex-1 space-y-2">
          <div>
            <p className="text-sm font-semibold">{title}</p>
            <p className="mt-0.5 text-xs opacity-80">{description}</p>
          </div>
          <div className="flex flex-wrap gap-1">
            {missing.slice(0, 30).map((ch) => (
              <span
                key={ch.chapter_number}
                className="rounded-md bg-white/10 px-1.5 py-0.5 font-mono text-[11px]"
                title={ch.url}
              >
                {ch.chapter_number}
              </span>
            ))}
            {missing.length > 30 && (
              <span className="rounded-md bg-white/10 px-1.5 py-0.5 font-mono text-[11px]">
                +{missing.length - 30}
              </span>
            )}
          </div>
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => onToggle(e.target.checked)}
              className="h-4 w-4 rounded border-white/20 bg-zinc-950 text-sky-500 focus:ring-sky-400"
            />
            Includere anche questi capitoli nel batch
          </label>
        </div>
      </div>
    </div>
  );
}

function ResultCard({
  result,
  coverage,
  plannedCount,
}: {
  result: DryRunResponse;
  coverage: CoverageResponse | undefined;
  plannedCount: number;
}) {
  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
          Capitoli pianificati
        </h2>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <StatusPill tone="info">{result.site}</StatusPill>
          <span>
            <Filter size={12} className="-mt-0.5 mr-1 inline-block" />
            {plannedCount || result.selected} di {result.total}
          </span>
        </div>
      </header>
      <div className="overflow-hidden rounded-md border border-white/5">
        <table className="w-full text-sm">
          <thead className="bg-white/5 text-left text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-3 py-2">#</th>
              <th className="px-3 py-2">Capitolo</th>
              <th className="px-3 py-2">Stato disco</th>
              <th className="px-3 py-2">Titolo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {result.chapters.map((ch, i) => {
              const onDisk = coverage?.available.find(
                (c) => c.chapter_number === ch.chapter_number,
              )?.on_disk;
              return (
                <ChapterRow
                  key={ch.url}
                  index={i + 1}
                  chapter={ch}
                  onDisk={onDisk}
                />
              );
            })}
            {result.chapters.length === 0 && (
              <tr>
                <td
                  colSpan={4}
                  className="px-3 py-6 text-center text-xs text-zinc-500"
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
  onDisk,
}: {
  index: number;
  chapter: DryRunChapter;
  onDisk: boolean | undefined;
}) {
  return (
    <tr className="hover:bg-white/5">
      <td className="px-3 py-2 font-mono text-xs text-zinc-500">{index}</td>
      <td className="px-3 py-2 font-medium text-zinc-100">
        ch. {chapter.chapter_number}
      </td>
      <td className="px-3 py-2">
        {onDisk === undefined ? (
          <StatusPill tone="muted">—</StatusPill>
        ) : onDisk ? (
          <StatusPill tone="ok">su disco</StatusPill>
        ) : (
          <StatusPill tone="warn">da fare</StatusPill>
        )}
      </td>
      <td className="px-3 py-2 text-zinc-400">{chapter.title ?? "—"}</td>
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
    <section className="space-y-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-5">
      <div className="flex items-start gap-3">
        <ShieldAlert className="mt-0.5 text-amber-300" size={18} />
        <div className="flex-1 space-y-2">
          <p className="text-sm text-amber-100">
            Stai per scaricare e tradurre {chapters} capitoli. Conferma di
            avere il diritto di scaricare il contenuto. Guardrail UX, non
            tutela legale.
          </p>
          <label className="inline-flex items-center gap-2 text-sm text-amber-100">
            <input
              type="checkbox"
              checked={iOwnRights}
              onChange={(e) => onToggleRights(e.target.checked)}
              className="h-4 w-4 rounded border-white/20 bg-zinc-950 text-sky-500 focus:ring-sky-400"
            />
            Confermo di avere i diritti (--i-own-rights)
          </label>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs text-amber-200/80">
          Il batch parte sequenziale (worker FIFO single-instance).
        </span>
        <button
          type="button"
          disabled={!iOwnRights || submitting || chapters === 0}
          onClick={onLaunch}
          className="inline-flex items-center gap-2 rounded-md bg-sky-500/90 px-4 py-2 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Layers size={14} />
          {submitting ? "Invio…" : "Avvia batch"}
          <ChevronRight size={14} />
        </button>
      </div>
      {submitError && (
        <p className="text-xs text-rose-300">{submitError}</p>
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
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
        {label}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-zinc-500">{hint}</span>}
    </label>
  );
}
