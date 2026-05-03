/**
 * Libreria — la collezione manga vista come una series-grid.
 *
 * I manifest ``msrt-run-*.json`` vengono raggruppati per serie e
 * disegnati come "poster card". Per le serie con un ``source_url``
 * note la card può scaricare la coverage in un clic e quindi
 * proporre due azioni dirette:
 *
 *   - **Recupera mancanti** → batch sui ``chapters_filter`` dei
 *     capitoli pubblicati che non sono su disco.
 *   - **Continua dal prossimo** → batch sui capitoli successivi
 *     all'ultimo già su disco (i nuovi pubblicati).
 *
 * La pagina è anche il punto principale di ingresso: c'è un CTA
 * "Aggiungi manga" prominente in alto.
 */

import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  FileText,
  Inbox,
  Loader2,
  Plus,
  PlusCircle,
  RefreshCcw,
  Search,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { JobCreate, LibraryEntry, SettingsView } from "../lib/api";
import {
  type SeriesGroup,
  compareChapterNumbers,
  computeCompleteness,
  groupBySeries,
  posterGradient,
} from "../lib/library-grouping";
import { formatTimestamp, pathBasename } from "../lib/format";
import { StatusPill } from "../components/StatusPill";
import { useToast } from "../components/Toast";

const DEFAULT_OUT = "out";

export function LibraryPage() {
  const [outDir, setOutDir] = useState(DEFAULT_OUT);
  const [search, setSearch] = useState("");
  const library = useQuery({
    queryKey: ["library", outDir],
    queryFn: () => api.library(outDir),
  });

  const groups = useMemo(
    () => (library.data ? groupBySeries(library.data.entries) : []),
    [library.data],
  );

  const filtered = useMemo(() => {
    if (!search.trim()) return groups;
    const q = search.toLowerCase();
    return groups.filter((g) => g.series.toLowerCase().includes(q));
  }, [groups, search]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">La mia libreria</h1>
          <p className="text-sm text-zinc-500">
            {library.isLoading
              ? "Caricamento…"
              : `${groups.length} ${groups.length === 1 ? "serie" : "serie"} · ${library.data?.entries.length ?? 0} capitoli su disco`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search
              size={14}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500"
              aria-hidden="true"
            />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Cerca serie…"
              aria-label="Cerca serie"
              className="w-56 rounded-md border border-white/10 bg-zinc-900 py-1.5 pl-9 pr-3 text-sm text-zinc-200 shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 focus:ring-offset-1 focus:ring-offset-zinc-950"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-zinc-500">
            Output dir:
            <input
              value={outDir}
              onChange={(e) => setOutDir(e.target.value)}
              className="w-44 rounded-md border border-white/10 bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-200 shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 focus:ring-offset-1 focus:ring-offset-zinc-950"
            />
          </label>
          <button
            type="button"
            onClick={() => library.refetch()}
            className="inline-flex min-h-9 items-center gap-1 rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-zinc-200 transition hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
            aria-label="Ricarica libreria"
          >
            <RefreshCcw size={14} aria-hidden="true" />
            Aggiorna
          </button>
          <Link
            to="/add"
            className="inline-flex min-h-9 items-center gap-1.5 rounded-md bg-sky-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
          >
            <Plus size={14} aria-hidden="true" />
            Aggiungi manga
          </Link>
        </div>
      </header>

      {library.error && (
        <div className="rounded-md border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
          {library.error.message}
        </div>
      )}

      {!library.error && groups.length === 0 && !library.isLoading && (
        <EmptyState outDir={outDir} />
      )}

      {filtered.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((group) => (
            <SeriesCard
              key={group.id}
              group={group}
              outDir={outDir}
              defaultExpanded={false}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/** Reusable poster card. Used by both Library page and Dashboard. */
export function SeriesCard({
  group,
  outDir,
  defaultExpanded = false,
}: {
  group: SeriesGroup;
  outDir: string;
  defaultExpanded?: boolean;
}) {
  const navigate = useNavigate();
  const toast = useToast();
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: api.settings,
  });
  const autoCover =
    (settings.data as SettingsView | undefined)?.auto_cover_enabled ?? true;
  const [coverageEnabled, setCoverageEnabled] = useState(defaultExpanded);
  const [expanded, setExpanded] = useState(defaultExpanded);

  const sourceUrl = group.sourceUrls[0];
  const coverage = useQuery({
    queryKey: ["coverage-series", sourceUrl ?? "", outDir],
    enabled: Boolean(coverageEnabled && sourceUrl),
    queryFn: () =>
      api.coverage({
        url: sourceUrl!,
        out_dir: outDir,
        fmt: "pdf",
        lang_target: "it",
      }),
    staleTime: 60_000,
  });
  const completeness = computeCompleteness(group, coverage.data);

  const submit = useMutation({
    mutationFn: (request: JobCreate) => api.createJob(request),
    onSuccess: (job) => {
      toast.success(`Batch avviato: ${group.series}`);
      navigate(`/jobs/${job.id}`);
    },
    onError: (err: Error) => toast.error("Avvio fallito", err.message),
  });

  const launchBatch = (chapters: string[], description: string) => {
    if (!sourceUrl) return;
    const ok = window.confirm(
      `Avviare un batch su ${chapters.length} capitoli per "${group.series}"?\n\n${description}\n\nConfermo di avere i diritti per scaricarli.`,
    );
    if (!ok) return;
    submit.mutate({
      kind: "url_batch",
      input_url: sourceUrl,
      i_own_rights: true,
      out_dir: outDir || "out",
      options: {
        chapters_filter: chapters.join(","),
      },
    });
  };

  const recoverMissing = () => {
    const missing = (coverage.data?.available ?? [])
      .filter((c) => !c.on_disk)
      .map((c) => c.chapter_number);
    if (missing.length === 0) return;
    launchBatch(
      missing,
      `Capitoli mancanti: ${missing.slice(0, 12).join(", ")}${missing.length > 12 ? "…" : ""}`,
    );
  };

  const continueFromLast = () => {
    if (!coverage.data) return;
    const last = group.lastChapterNumber;
    const next = coverage.data.available
      .filter((c) => !c.on_disk)
      .filter((c) =>
        last == null ? true : compareChapterNumbers(c.chapter_number, last) > 0,
      )
      .map((c) => c.chapter_number);
    if (next.length === 0) {
      toast.info("Nessun capitolo nuovo da scaricare");
      return;
    }
    launchBatch(
      next,
      `Continuo dopo ch.${last ?? "0"} con ${next.length} nuovi capitoli.`,
    );
  };

  const { from, to } = posterGradient(group.series);
  const initials = group.series
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "?";

  return (
    <article className="overflow-hidden rounded-2xl border border-white/5 bg-zinc-900/60 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-stretch gap-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
        aria-expanded={expanded}
      >
        <Poster
          series={group.series}
          sourceUrl={sourceUrl}
          outDir={outDir}
          gradient={{ from, to }}
          initials={initials}
          autoCoverEnabled={autoCover}
        />
        <div className="flex flex-1 flex-col justify-between p-4">
          <div>
            <h2 className="text-base font-semibold text-zinc-100">
              {group.series}
            </h2>
            <p className="mt-0.5 text-xs text-zinc-500">
              Ultimo: {group.lastFinishedAt ? formatTimestamp(group.lastFinishedAt) : "—"}
              {group.lastChapterNumber && (
                <> · ch. {group.lastChapterNumber}</>
              )}
            </p>
          </div>
          <ProgressLabel group={group} completeness={completeness} />
        </div>
      </button>

      <div className="border-t border-white/5 p-4">
        {sourceUrl ? (
          <div className="space-y-3">
            {!coverageEnabled && (
              <button
                type="button"
                onClick={() => setCoverageEnabled(true)}
                className="inline-flex min-h-9 items-center gap-1.5 rounded-md bg-white/5 px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
              >
                <Search size={12} aria-hidden="true" />
                Verifica completezza sul source
              </button>
            )}
            {coverageEnabled && coverage.isFetching && (
              <p className="flex items-center gap-2 text-xs text-zinc-500">
                <Loader2 size={12} className="animate-spin" aria-hidden="true" />
                Verifica capitoli pubblicati…
              </p>
            )}
            {coverageEnabled && coverage.error && (
              <p className="text-xs text-rose-300">{coverage.error.message}</p>
            )}
            {coverage.data && (
              <RecoveryActions
                completeness={completeness}
                lastNumber={group.lastChapterNumber}
                onRecover={recoverMissing}
                onContinue={continueFromLast}
                submitting={submit.isPending}
              />
            )}
          </div>
        ) : (
          <p className="text-xs text-zinc-500">
            Nessuna sorgente nota: questa serie è stata aggiunta da
            cartella locale, quindi non posso verificarne la completezza.
          </p>
        )}
      </div>

      {expanded && <ChapterList chapters={group.chapters} />}
    </article>
  );
}

/**
 * Poster — overlays the cover image (when available) on top of the
 * deterministic gradient + initials fallback. The fallback is what
 * the user sees while the network resolves and forever if the cover
 * lookup 404's. When the user disabled "Recupero automatico
 * copertine" in Impostazioni, the ``<img>`` is never rendered so we
 * don't fire a request that's just going to 404.
 */
function Poster({
  series,
  sourceUrl,
  outDir,
  gradient,
  initials,
  autoCoverEnabled,
}: {
  series: string;
  sourceUrl: string | undefined;
  outDir: string;
  gradient: { from: string; to: string };
  initials: string;
  autoCoverEnabled: boolean;
}) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const showImage = autoCoverEnabled && !failed;
  const src = api.coverUrl(series, { sourceUrl, outDir });
  return (
    <div
      className="relative grid h-32 w-24 shrink-0 place-items-center overflow-hidden font-bold tracking-tight text-white/90"
      style={{
        background: `linear-gradient(135deg, ${gradient.from}, ${gradient.to})`,
      }}
      aria-hidden="true"
    >
      <span
        className={`text-3xl transition-opacity duration-300 ${loaded && showImage ? "opacity-0" : "opacity-100"}`}
      >
        {initials}
      </span>
      {showImage && (
        <img
          src={src}
          alt=""
          loading="lazy"
          decoding="async"
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
          className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-0"}`}
        />
      )}
    </div>
  );
}

function ProgressLabel({
  group,
  completeness,
}: {
  group: SeriesGroup;
  completeness: ReturnType<typeof computeCompleteness>;
}) {
  if (completeness.status === "unknown") {
    return (
      <div className="space-y-1">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-xl font-semibold text-zinc-100">
            {group.onDiskChapterNumbers.size}
          </span>
          <span className="text-xs text-zinc-500">capitoli su disco</span>
        </div>
      </div>
    );
  }
  const pct = completeness.availableCount
    ? Math.round((completeness.doneCount / completeness.availableCount) * 100)
    : 0;
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-xl font-semibold text-zinc-100">
            {completeness.doneCount}
          </span>
          <span className="font-mono text-sm text-zinc-500">
            / {completeness.availableCount}
          </span>
        </div>
        {completeness.status === "complete" ? (
          <StatusPill tone="ok">complet{group.series.endsWith("a") ? "a" : "o"}</StatusPill>
        ) : (
          <StatusPill tone="warn">{completeness.missingNumbers.length} mancanti</StatusPill>
        )}
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
        <div
          className={`h-full rounded-full transition-[width] duration-500 ease-out ${
            completeness.status === "complete" ? "bg-emerald-400" : "bg-sky-400"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function RecoveryActions({
  completeness,
  lastNumber,
  onRecover,
  onContinue,
  submitting,
}: {
  completeness: ReturnType<typeof computeCompleteness>;
  lastNumber: string | null;
  onRecover: () => void;
  onContinue: () => void;
  submitting: boolean;
}) {
  if (completeness.status === "complete") {
    return (
      <p className="flex items-center gap-2 text-xs text-emerald-300">
        <CheckCircle2 size={14} aria-hidden="true" />
        Hai tutti i capitoli pubblicati.
      </p>
    );
  }
  const missing = completeness.missingNumbers;
  // Split missing into "before-last" (gaps in the back catalogue)
  // vs "after-last" (newly published) so the two CTAs are honest.
  const newer = lastNumber
    ? missing.filter((n) => compareChapterNumbers(n, lastNumber) > 0)
    : missing;
  const older = lastNumber
    ? missing.filter((n) => compareChapterNumbers(n, lastNumber) <= 0)
    : [];

  return (
    <div className="space-y-2">
      <p className="flex items-center gap-2 text-xs text-amber-200">
        <AlertTriangle size={14} aria-hidden="true" />
        {missing.length} capitol{missing.length === 1 ? "o manca" : "i mancano"}: ch.
        {missing.slice(0, 10).join(", ch.")}
        {missing.length > 10 && "…"}
      </p>
      <div className="flex flex-wrap gap-2">
        {older.length > 0 && (
          <button
            type="button"
            onClick={onRecover}
            disabled={submitting}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-amber-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-amber-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCcw size={14} aria-hidden="true" />
            Recupera mancanti ({missing.length})
          </button>
        )}
        {newer.length > 0 && (
          <button
            type="button"
            onClick={onContinue}
            disabled={submitting}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-sky-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ArrowRight size={14} aria-hidden="true" />
            Continua dal prossimo ({newer.length} nuovi)
          </button>
        )}
        {older.length === 0 && newer.length === 0 && (
          <button
            type="button"
            onClick={onRecover}
            disabled={submitting}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-amber-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCcw size={14} aria-hidden="true" />
            Recupera mancanti ({missing.length})
          </button>
        )}
      </div>
    </div>
  );
}

function ChapterList({ chapters }: { chapters: LibraryEntry[] }) {
  const open = useMutation({ mutationFn: (path: string) => api.openPath(path) });
  return (
    <ul className="divide-y divide-white/5 border-t border-white/5">
      {chapters.map((entry) => (
        <li
          key={entry.manifest_id}
          className="flex flex-wrap items-center justify-between gap-3 px-4 py-2 text-sm hover:bg-white/5"
        >
          <div className="flex items-center gap-3">
            <FileText size={14} className="text-zinc-500" aria-hidden="true" />
            <div>
              <div className="text-zinc-100">
                ch. {entry.chapter_number ?? "?"}
                {entry.chapter_title && (
                  <span className="ml-2 text-xs text-zinc-500">
                    {entry.chapter_title}
                  </span>
                )}
              </div>
              <div className="text-[11px] text-zinc-500">
                {entry.finished_at ? formatTimestamp(entry.finished_at) : "—"}
                {entry.errors.length > 0 && (
                  <span className="ml-2 text-rose-300">
                    {entry.errors.length} errori
                  </span>
                )}
              </div>
            </div>
          </div>
          {entry.output_files[0] && (
            <button
              type="button"
              onClick={() => open.mutate(entry.output_files[0])}
              className="inline-flex items-center gap-1 text-xs text-sky-300 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
              aria-label={`Apri ${pathBasename(entry.output_files[0])}`}
            >
              <ExternalLink size={12} aria-hidden="true" />
              {pathBasename(entry.output_files[0])}
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

function EmptyState({ outDir }: { outDir: string }) {
  return (
    <section className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-white/10 bg-zinc-900/40 p-12 text-center">
      <Inbox className="text-zinc-600" size={32} aria-hidden="true" />
      <div>
        <h2 className="text-base font-semibold text-zinc-100">
          Nessun manga ancora tradotto
        </h2>
        <p className="mt-1 text-sm text-zinc-500">
          Non ho trovato nessun{" "}
          <code className="font-mono text-xs">msrt-run.json</code> in{" "}
          <code className="font-mono text-xs">{outDir}/</code>. Aggiungi una
          serie da URL o una cartella locale per iniziare.
        </p>
      </div>
      <Link
        to="/add"
        className="mt-2 inline-flex min-h-11 items-center gap-2 rounded-md bg-sky-500/90 px-4 py-2 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
      >
        <PlusCircle size={16} aria-hidden="true" />
        Aggiungi il primo manga
      </Link>
    </section>
  );
}

