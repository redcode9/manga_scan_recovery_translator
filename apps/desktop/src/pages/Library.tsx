/**
 * Library — elenca i manifest di run salvati in ``out/``.
 *
 * Per v0.4b mostra solo le entry "live"; il filtro per serie e la
 * vista dettaglio del manifest arrivano in v0.4e insieme al
 * "retry failed chapter".
 */

import { ExternalLink, FileText, FolderOpen, Inbox, RefreshCcw } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { LibraryEntry } from "../lib/api";
import { formatDuration, formatTimestamp, pathBasename } from "../lib/format";
import { StatusPill } from "../components/StatusPill";

const DEFAULT_OUT = "out";

export function LibraryPage() {
  const [outDir, setOutDir] = useState(DEFAULT_OUT);
  const library = useQuery({
    queryKey: ["library", outDir],
    queryFn: () => api.library(outDir),
  });

  const entries = library.data?.entries ?? [];

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Libreria</h1>
          <p className="text-sm text-zinc-500">
            Manifest delle run completate.{" "}
            {library.isLoading
              ? "Caricamento…"
              : `${entries.length} entry trovate.`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-zinc-500" htmlFor="out-dir">
            Output dir:
          </label>
          <input
            id="out-dir"
            value={outDir}
            onChange={(e) => setOutDir(e.target.value)}
            className="w-44 rounded-md border border-white/10 bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-200 shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 focus:ring-offset-1 focus:ring-offset-zinc-950"
          />
          <button
            type="button"
            onClick={() => library.refetch()}
            className="inline-flex items-center gap-1 rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-zinc-200 transition hover:bg-white/15"
          >
            <RefreshCcw size={14} />
            Aggiorna
          </button>
        </div>
      </header>

      {library.error && (
        <div className="rounded-md border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
          {library.error.message}
        </div>
      )}

      {!library.error && entries.length === 0 && !library.isLoading && (
        <EmptyState outDir={outDir} />
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {entries.map((entry) => (
          <EntryCard key={entry.manifest_id} entry={entry} />
        ))}
      </div>
    </div>
  );
}

function EmptyState({ outDir }: { outDir: string }) {
  return (
    <section className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-white/10 bg-zinc-900/40 p-12 text-center">
      <Inbox className="text-zinc-600" size={32} />
      <div>
        <h2 className="text-base font-semibold text-zinc-100">
          Nessun manifest trovato
        </h2>
        <p className="mt-1 text-sm text-zinc-500">
          Nessun <code className="font-mono text-xs">msrt-run.json</code> in{" "}
          <code className="font-mono text-xs">{outDir}/</code>. Lancia un
          job da "Nuovo Job" o "Batch" per popolare la libreria.
        </p>
      </div>
    </section>
  );
}

function EntryCard({ entry }: { entry: LibraryEntry }) {
  const open = useMutation({ mutationFn: (path: string) => api.openPath(path) });

  return (
    <article className="rounded-2xl border border-white/5 bg-zinc-900/60 p-4 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-zinc-100">
            {entry.series ?? "Untitled"}{" "}
            {entry.chapter_number && (
              <span className="text-zinc-500">— ch. {entry.chapter_number}</span>
            )}
          </h2>
          {entry.chapter_title && (
            <p className="text-xs text-zinc-500">{entry.chapter_title}</p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1">
          {entry.strategy && <StatusPill tone="info">{entry.strategy}</StatusPill>}
          {entry.model_alias && (
            <StatusPill tone="muted">{entry.model_alias}</StatusPill>
          )}
          {entry.errors.length > 0 && (
            <StatusPill tone="fail">{entry.errors.length} errori</StatusPill>
          )}
          {entry.errors.length === 0 && entry.warnings.length > 0 && (
            <StatusPill tone="warn">{entry.warnings.length} warning</StatusPill>
          )}
        </div>
      </header>
      <dl className="mt-3 grid grid-cols-2 gap-1 text-xs text-zinc-400">
        <div>
          <dt className="uppercase tracking-wide text-zinc-500">Iniziato</dt>
          <dd>{formatTimestamp(entry.started_at)}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide text-zinc-500">Durata</dt>
          <dd>{formatDuration(entry.started_at, entry.finished_at)}</dd>
        </div>
      </dl>
      {entry.output_files.length > 0 && (
        <ul className="mt-3 space-y-1">
          {entry.output_files.map((file) => (
            <li
              key={file}
              className="flex items-center justify-between gap-2 rounded-md bg-white/5 px-3 py-2 text-xs"
            >
              <span className="flex items-center gap-2 font-mono text-zinc-300">
                <FileText size={14} className="text-zinc-500" />
                {pathBasename(file)}
              </span>
              <button
                type="button"
                onClick={() => open.mutate(file)}
                className="inline-flex items-center gap-1 text-sky-300 hover:text-sky-200 hover:underline"
              >
                <ExternalLink size={12} />
                apri
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex items-center gap-2 text-[11px] text-zinc-600">
        <FolderOpen size={12} />
        <span className="truncate font-mono" title={entry.manifest_path}>
          {entry.manifest_path}
        </span>
      </div>
    </article>
  );
}
