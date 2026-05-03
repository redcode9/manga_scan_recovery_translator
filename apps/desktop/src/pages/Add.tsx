/**
 * Aggiungi — pagina unificata che sostituisce "Nuovo Job" + "Batch".
 *
 * Due flussi:
 *  - **Cartella locale** (file system): form snello con path, serie,
 *    capitolo. Chiama ``createJob`` con ``kind: "local"``.
 *  - **URL** (MangaDex / MangaFire): input URL + checkbox diritti.
 *    Click su "Analizza" → ``dryRun`` per scoprire quanti capitoli ci
 *    sono dietro l'URL. Se ``selected === 1`` mostriamo il flusso
 *    capitolo singolo. Se ``selected > 1`` mostriamo coverage + gap
 *    fill prima del batch.
 *
 * Niente più ridondanza fra "Nuovo Job" e "Batch": un solo posto per
 * lanciare qualsiasi traduzione.
 */

import {
  ArrowRight,
  ChevronDown,
  Filter,
  FolderOpen,
  Globe,
  Layers,
  Loader2,
  RefreshCcw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";
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

type Mode = "local" | "url";

interface UrlState {
  url: string;
  site: string;
  range: string;
  iOwnRights: boolean;
  fillBefore: boolean;
  fillAfter: boolean;
  outDir: string;
}

interface LocalState {
  inputDir: string;
  series: string;
  chapter: string;
  title: string;
  outDir: string;
  format: "pdf" | "cbz" | "both";
}

const URL_INITIAL: UrlState = {
  url: "",
  site: "auto",
  range: "",
  iOwnRights: false,
  fillBefore: false,
  fillAfter: false,
  outDir: "out",
};

const LOCAL_INITIAL: LocalState = {
  inputDir: "",
  series: "",
  chapter: "",
  title: "",
  outDir: "out",
  format: "pdf",
};

export function AddPage() {
  const [mode, setMode] = useState<Mode>("url");

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          Aggiungi un manga
        </h1>
        <p className="text-sm text-zinc-500">
          Punta a un URL della serie o a una cartella di immagini. Se l'URL
          è una serie completa la pagina ti farà vedere quanti capitoli
          mancano e ti aiuterà a recuperarli.
        </p>
      </header>

      <ModeSwitch mode={mode} onChange={setMode} />

      {mode === "url" ? <UrlFlow /> : <LocalFlow />}
    </div>
  );
}

function ModeSwitch({
  mode,
  onChange,
}: {
  mode: Mode;
  onChange: (m: Mode) => void;
}) {
  const items: {
    value: Mode;
    label: string;
    description: string;
    icon: React.ReactNode;
  }[] = [
    {
      value: "url",
      label: "Da URL (consigliato)",
      description: "Una serie da MangaDex o MangaFire — singolo capitolo o intera collana.",
      icon: <Globe size={16} />,
    },
    {
      value: "local",
      label: "Cartella locale",
      description: "Hai già le immagini su disco e vuoi solo tradurle.",
      icon: <FolderOpen size={16} />,
    },
  ];
  return (
    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
      {items.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 ${
            mode === opt.value
              ? "border-sky-400/40 bg-sky-500/10"
              : "border-white/5 bg-white/5 hover:bg-white/10"
          }`}
          aria-pressed={mode === opt.value}
        >
          <span
            className={`mt-0.5 grid h-7 w-7 place-items-center rounded-md ring-1 ${
              mode === opt.value
                ? "bg-sky-500/15 text-sky-200 ring-sky-400/30"
                : "bg-zinc-950/60 text-zinc-400 ring-white/10"
            }`}
            aria-hidden="true"
          >
            {opt.icon}
          </span>
          <span>
            <span className="block text-sm font-medium text-zinc-100">
              {opt.label}
            </span>
            <span className="mt-0.5 block text-xs text-zinc-500">
              {opt.description}
            </span>
          </span>
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// URL flow
// ---------------------------------------------------------------------------

function UrlFlow() {
  const toast = useToast();
  const navigate = useNavigate();
  const [form, setForm] = useState<UrlState>(URL_INITIAL);
  const [dryRunResult, setDryRunResult] = useState<DryRunResponse | null>(null);

  const update = <K extends keyof UrlState>(key: K, value: UrlState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const dryRun = useMutation({
    mutationFn: () =>
      api.dryRun({
        url: form.url.trim(),
        site: form.site || "auto",
        range_filter: form.range.trim() || undefined,
      }),
    onSuccess: (data) => setDryRunResult(data),
    onError: (err: Error) => toast.error("Analisi URL fallita", err.message),
  });

  const coverage = useQuery({
    queryKey: ["coverage", form.url, form.range, form.outDir],
    enabled: Boolean(dryRunResult && form.url.trim() && dryRunResult.selected > 1),
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

  // When the gap shape changes, reset the user's fill-toggles so they
  // have to consciously opt in (instead of carrying state forward).
  useEffect(() => {
    setForm((prev) => ({ ...prev, fillBefore: false, fillAfter: false }));
  }, [
    coverage.data?.missing_before_range.length,
    coverage.data?.missing_after_range.length,
  ]);

  const submit = useMutation({
    mutationFn: (request: JobCreate) => api.createJob(request),
    onSuccess: (job) => {
      toast.success(
        "Job avviato",
        `Job ${job.id} in coda. Verrai reindirizzato.`,
      );
      navigate(`/jobs/${job.id}`);
    },
    onError: (err: Error) => toast.error("Avvio fallito", err.message),
  });

  const onAnalyze = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.url.trim()) return;
    setDryRunResult(null);
    dryRun.mutate();
  };

  const planned = useMemo(
    () => computePlanned(dryRunResult, coverage.data, form),
    [dryRunResult, coverage.data, form],
  );

  const onLaunchSingle = () => {
    if (!form.iOwnRights || !dryRunResult || dryRunResult.chapters.length !== 1)
      return;
    const single = dryRunResult.chapters[0];
    submit.mutate({
      kind: "url",
      input_url: single.url,
      i_own_rights: true,
      out_dir: form.outDir.trim() || "out",
      options: { site: form.site || "auto" },
    });
  };

  const onLaunchBatch = () => {
    if (!form.iOwnRights || !dryRunResult) return;
    const useExplicit = form.fillBefore || form.fillAfter;
    submit.mutate({
      kind: "url_batch",
      input_url: form.url.trim(),
      i_own_rights: true,
      out_dir: form.outDir.trim() || "out",
      options: {
        site: form.site || "auto",
        range_filter: useExplicit ? null : form.range.trim() || null,
        chapters_filter: useExplicit
          ? planned.map((c) => c.chapter_number).join(",")
          : null,
      },
    });
  };

  return (
    <div className="space-y-5">
      <form
        onSubmit={onAnalyze}
        className="space-y-4 rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]"
      >
        <Field
          label="URL della serie o del capitolo"
          hint="Esempio: https://mangadex.org/title/<UUID> oppure https://mangafire.to/read/<slug>/en/chapter-N"
        >
          <input
            value={form.url}
            onChange={(e) => update("url", e.target.value)}
            placeholder="https://mangadex.org/title/<UUID>"
            className={INPUT_CLASS}
            required
          />
        </Field>
        <details className="rounded-md border border-white/5 [&_summary]:cursor-pointer">
          <summary className="flex items-center gap-1.5 px-3 py-2 text-xs uppercase tracking-wide text-zinc-500">
            <ChevronDown
              size={12}
              className="transition-transform [details[open]_&]:rotate-180"
              aria-hidden="true"
            />
            Opzioni avanzate
          </summary>
          <div className="grid grid-cols-1 gap-3 px-3 pb-3 pt-1 md:grid-cols-3">
            <Field
              label="Range capitoli"
              hint="Es. 50-51. Lascia vuoto per tutti."
            >
              <input
                value={form.range}
                onChange={(e) => update("range", e.target.value)}
                className={INPUT_CLASS}
                placeholder="50-51"
              />
            </Field>
            <Field
              label="Site adapter"
              hint="auto = riconosci dall'URL"
            >
              <input
                value={form.site}
                onChange={(e) => update("site", e.target.value)}
                className={INPUT_CLASS}
              />
            </Field>
            <Field
              label="Output dir"
              hint="Dove finiscono i PDF"
            >
              <input
                value={form.outDir}
                onChange={(e) => update("outDir", e.target.value)}
                className={INPUT_CLASS}
              />
            </Field>
          </div>
        </details>

        <button
          type="submit"
          disabled={dryRun.isPending || !form.url.trim()}
          className="inline-flex min-h-11 items-center gap-2 rounded-md bg-sky-500/90 px-4 py-2 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {dryRun.isPending ? (
            <Loader2 size={16} className="animate-spin" aria-hidden="true" />
          ) : (
            <Sparkles size={16} aria-hidden="true" />
          )}
          {dryRun.isPending ? "Analizzo…" : "Analizza URL"}
        </button>
      </form>

      {dryRunResult && dryRunResult.selected === 1 && (
        <SingleChapterCard
          dryRun={dryRunResult}
          form={form}
          update={update}
          onLaunch={onLaunchSingle}
          submitting={submit.isPending}
        />
      )}

      {dryRunResult && dryRunResult.selected > 1 && (
        <SeriesBatchCard
          dryRun={dryRunResult}
          coverage={coverage.data}
          coverageLoading={coverage.isFetching}
          form={form}
          update={update}
          plannedCount={planned.length}
          onLaunch={onLaunchBatch}
          submitting={submit.isPending}
        />
      )}
    </div>
  );
}

function SingleChapterCard({
  dryRun,
  form,
  update,
  onLaunch,
  submitting,
}: {
  dryRun: DryRunResponse;
  form: UrlState;
  update: <K extends keyof UrlState>(key: K, value: UrlState[K]) => void;
  onLaunch: () => void;
  submitting: boolean;
}) {
  const single = dryRun.chapters[0];
  return (
    <section className="space-y-3 rounded-2xl border border-sky-500/20 bg-sky-500/5 p-5">
      <header className="flex items-center gap-2">
        <Sparkles size={16} className="text-sky-300" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-zinc-100">
          Capitolo singolo individuato
        </h2>
        <StatusPill tone="info">{dryRun.site}</StatusPill>
      </header>
      <p className="text-sm text-zinc-300">
        ch. <strong>{single.chapter_number}</strong>
        {single.title && <> — {single.title}</>}
      </p>
      <RightsCheckbox
        checked={form.iOwnRights}
        onChange={(v) => update("iOwnRights", v)}
      />
      <button
        type="button"
        onClick={onLaunch}
        disabled={!form.iOwnRights || submitting}
        className="inline-flex min-h-11 items-center gap-2 rounded-md bg-sky-500/90 px-4 py-2 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-hidden="true" />
        ) : (
          <ArrowRight size={16} aria-hidden="true" />
        )}
        {submitting ? "Avvio…" : `Traduci ch. ${single.chapter_number}`}
      </button>
    </section>
  );
}

function SeriesBatchCard({
  dryRun,
  coverage,
  coverageLoading,
  form,
  update,
  plannedCount,
  onLaunch,
  submitting,
}: {
  dryRun: DryRunResponse;
  coverage: CoverageResponse | undefined;
  coverageLoading: boolean;
  form: UrlState;
  update: <K extends keyof UrlState>(key: K, value: UrlState[K]) => void;
  plannedCount: number;
  onLaunch: () => void;
  submitting: boolean;
}) {
  return (
    <div className="space-y-4">
      {coverageLoading && !coverage && (
        <p className="text-sm text-zinc-500">
          <Loader2
            size={14}
            className="mr-1.5 inline-block animate-spin align-text-bottom"
            aria-hidden="true"
          />
          Calcolo copertura su disco…
        </p>
      )}

      {coverage && (
        <CoverageSummary
          coverage={coverage}
          fillBefore={form.fillBefore}
          fillAfter={form.fillAfter}
          onToggleBefore={(v) => update("fillBefore", v)}
          onToggleAfter={(v) => update("fillAfter", v)}
        />
      )}

      <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
        <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
            Capitoli pianificati
          </h2>
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <StatusPill tone="info">{dryRun.site}</StatusPill>
            <span>
              <Filter
                size={12}
                className="-mt-0.5 mr-1 inline-block"
                aria-hidden="true"
              />
              {plannedCount || dryRun.selected} di {dryRun.total}
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
              {dryRun.chapters.map((ch, i) => (
                <ChapterRow
                  key={ch.url}
                  index={i + 1}
                  chapter={ch}
                  onDisk={
                    coverage?.available.find(
                      (c) => c.chapter_number === ch.chapter_number,
                    )?.on_disk
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <RightsAndLaunch
        chapters={plannedCount || dryRun.selected}
        iOwnRights={form.iOwnRights}
        onToggleRights={(v) => update("iOwnRights", v)}
        submitting={submitting}
        onLaunch={onLaunch}
      />
    </div>
  );
}

function CoverageSummary({
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
          Copertura serie
        </h2>
        <span className="text-xs text-zinc-500">
          Su disco:{" "}
          <span className="font-mono text-zinc-200">{coverage.on_disk_count}</span>
          {" / "}
          <span className="font-mono">{coverage.available_count}</span>{" "}
          ({onDiskPct}%)
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
          title={`${beforeCount} capitol${beforeCount === 1 ? "o" : "i"} manca${beforeCount === 1 ? "" : "no"} PRIMA del range`}
          description="Capitoli antecedenti che non hai su disco. Senza fill esplicito il batch li lascia indietro."
          missing={coverage.missing_before_range}
          checked={fillBefore}
          onToggle={onToggleBefore}
        />
      )}
      {afterCount > 0 && (
        <GapPanel
          tone="info"
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
  title,
  description,
  missing,
  checked,
  onToggle,
}: {
  tone: "amber" | "info";
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
      <div className="space-y-2">
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

function RightsCheckbox({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded border-white/20 bg-zinc-950 text-sky-500 focus:ring-sky-400"
      />
      <span>
        <ShieldAlert
          size={14}
          className="-mt-0.5 mr-1 inline-block text-amber-300"
          aria-hidden="true"
        />
        <strong className="font-medium">Confermo di avere i diritti</strong>{" "}
        per scaricare e tradurre questo contenuto. Guardrail UX, non tutela
        legale.
      </span>
    </label>
  );
}

function RightsAndLaunch({
  chapters,
  iOwnRights,
  onToggleRights,
  submitting,
  onLaunch,
}: {
  chapters: number;
  iOwnRights: boolean;
  onToggleRights: (v: boolean) => void;
  submitting: boolean;
  onLaunch: () => void;
}) {
  return (
    <section className="space-y-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-5">
      <p className="text-sm text-amber-100">
        Stai per scaricare e tradurre <strong>{chapters} capitoli</strong>.
        Conferma di avere il diritto di scaricare il contenuto.
      </p>
      <RightsCheckbox checked={iOwnRights} onChange={onToggleRights} />
      <div className="flex items-center justify-between">
        <span className="text-xs text-amber-200/80">
          Il batch parte sequenziale.
        </span>
        <button
          type="button"
          disabled={!iOwnRights || submitting || chapters === 0}
          onClick={onLaunch}
          className="inline-flex min-h-11 items-center gap-2 rounded-md bg-sky-500/90 px-4 py-2 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? (
            <Loader2 size={16} className="animate-spin" aria-hidden="true" />
          ) : (
            <Layers size={16} aria-hidden="true" />
          )}
          {submitting ? "Avvio…" : "Avvia batch"}
        </button>
      </div>
    </section>
  );
}

function computePlanned(
  result: DryRunResponse | null,
  coverage: CoverageResponse | undefined,
  form: UrlState,
): CoverageChapter[] {
  if (!result) return [];
  const baseNumbers = new Set(result.chapters.map((c) => c.chapter_number));
  if (!coverage) {
    return result.chapters.map((c) => ({
      chapter_number: c.chapter_number,
      url: c.url,
      title: c.title,
      series: c.series,
      on_disk: false,
      in_range: true,
    }));
  }
  const planned: CoverageChapter[] = [];
  for (const ch of coverage.available) {
    const inBase = baseNumbers.has(ch.chapter_number);
    const inBefore =
      form.fillBefore &&
      coverage.missing_before_range.some(
        (m) => m.chapter_number === ch.chapter_number,
      );
    const inAfter =
      form.fillAfter &&
      coverage.missing_after_range.some(
        (m) => m.chapter_number === ch.chapter_number,
      );
    if (inBase || inBefore || inAfter) planned.push(ch);
  }
  return planned;
}

// ---------------------------------------------------------------------------
// Local flow
// ---------------------------------------------------------------------------

function LocalFlow() {
  const toast = useToast();
  const navigate = useNavigate();
  const [form, setForm] = useState<LocalState>(LOCAL_INITIAL);
  const update = <K extends keyof LocalState>(key: K, value: LocalState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const submit = useMutation({
    mutationFn: (request: JobCreate) => api.createJob(request),
    onSuccess: (job) => {
      toast.success("Job avviato", `Job ${job.id} in coda.`);
      navigate(`/jobs/${job.id}`);
    },
    onError: (err: Error) => toast.error("Avvio fallito", err.message),
  });

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.inputDir.trim()) return;
    submit.mutate({
      kind: "local",
      input_dir: form.inputDir.trim(),
      out_dir: form.outDir.trim() || "out",
      series: form.series.trim() || null,
      chapter_number: form.chapter.trim() || null,
      chapter_title: form.title.trim() || null,
      options: { format: form.format },
    });
  };

  return (
    <form
      onSubmit={onSubmit}
      className="space-y-4 rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]"
    >
      <Field
        label="Cartella sorgente"
        hint="Path assoluto. Una directory di immagini PNG/JPG/WebP."
      >
        <input
          value={form.inputDir}
          onChange={(e) => update("inputDir", e.target.value)}
          className={INPUT_CLASS}
          placeholder="/Users/me/Desktop/Wistoria/Capitolo_50"
          required
        />
      </Field>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <Field label="Serie" hint="Per metadata CBZ + auto-glossary">
          <input
            value={form.series}
            onChange={(e) => update("series", e.target.value)}
            className={INPUT_CLASS}
            placeholder="Wistoria"
          />
        </Field>
        <Field label="Numero capitolo">
          <input
            value={form.chapter}
            onChange={(e) => update("chapter", e.target.value)}
            className={INPUT_CLASS}
            placeholder="50"
          />
        </Field>
        <Field label="Titolo (opzionale)">
          <input
            value={form.title}
            onChange={(e) => update("title", e.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <Field label="Formato output">
          <select
            value={form.format}
            onChange={(e) => update("format", e.target.value as LocalState["format"])}
            className={INPUT_CLASS}
          >
            <option value="pdf">PDF</option>
            <option value="cbz">CBZ</option>
            <option value="both">PDF + CBZ</option>
          </select>
        </Field>
        <Field label="Output dir">
          <input
            value={form.outDir}
            onChange={(e) => update("outDir", e.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
      </div>
      <button
        type="submit"
        disabled={!form.inputDir.trim() || submit.isPending}
        className="inline-flex min-h-11 items-center gap-2 rounded-md bg-sky-500/90 px-4 py-2 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submit.isPending ? (
          <Loader2 size={16} className="animate-spin" aria-hidden="true" />
        ) : (
          <RefreshCcw size={16} aria-hidden="true" />
        )}
        {submit.isPending ? "Avvio…" : "Avvia traduzione"}
      </button>
    </form>
  );
}

const INPUT_CLASS =
  "w-full rounded-md border border-white/10 bg-zinc-950/60 px-3 py-2 font-mono text-sm text-zinc-100 shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 focus:ring-offset-1 focus:ring-offset-zinc-950";

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
