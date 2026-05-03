/**
 * Group library entries by series so the UI can render a manga
 * collection (poster grid) instead of a flat list of chapters.
 *
 * The grouping is purely client-side: the backend exposes one entry
 * per chapter manifest, and we aggregate them here so the same data
 * source can drive both the per-chapter view and the per-series
 * dashboard view without a parallel endpoint.
 */

import type { CoverageResponse, LibraryEntry } from "./api";

export interface SeriesGroup {
  /** Display name of the series (or "Senza titolo" when unknown). */
  series: string;
  /** Stable id for routing/keys, derived from the slugified series name. */
  id: string;
  /** All chapter entries that belong to this series, newest first. */
  chapters: LibraryEntry[];
  /** Distinct source URLs seen across the chapters (for coverage lookup). */
  sourceUrls: string[];
  /** Latest finished_at timestamp across the chapters, or null. */
  lastFinishedAt: string | null;
  /** Latest chapter number successfully translated (string, may be "1.1"). */
  lastChapterNumber: string | null;
  /** Set of chapter numbers already on disk. */
  onDiskChapterNumbers: Set<string>;
  /** Total errors across all chapters in this series. */
  errors: number;
  /** Total warnings across all chapters in this series. */
  warnings: number;
}

const UNKNOWN_LABEL = "Senza titolo";

export function groupBySeries(entries: LibraryEntry[]): SeriesGroup[] {
  const map = new Map<string, SeriesGroup>();
  for (const entry of entries) {
    const series = entry.series?.trim() || UNKNOWN_LABEL;
    const id = slugify(series);
    let group = map.get(id);
    if (!group) {
      group = {
        series,
        id,
        chapters: [],
        sourceUrls: [],
        lastFinishedAt: null,
        lastChapterNumber: null,
        onDiskChapterNumbers: new Set<string>(),
        errors: 0,
        warnings: 0,
      };
      map.set(id, group);
    }
    group.chapters.push(entry);
    if (entry.chapter_number) group.onDiskChapterNumbers.add(entry.chapter_number);
    if (entry.source_url && !group.sourceUrls.includes(entry.source_url)) {
      group.sourceUrls.push(entry.source_url);
    }
    if (
      entry.finished_at &&
      (!group.lastFinishedAt || entry.finished_at > group.lastFinishedAt)
    ) {
      group.lastFinishedAt = entry.finished_at;
    }
    group.errors += entry.errors.length;
    group.warnings += entry.warnings.length;
  }

  for (const group of map.values()) {
    group.chapters.sort((a, b) =>
      compareChapterNumbers(b.chapter_number, a.chapter_number),
    );
    group.lastChapterNumber =
      [...group.onDiskChapterNumbers].sort(compareChapterNumbers).at(-1) ?? null;
  }

  return [...map.values()].sort((a, b) => {
    const aT = a.lastFinishedAt ?? "";
    const bT = b.lastFinishedAt ?? "";
    return bT.localeCompare(aT);
  });
}

/** Build a coverage hint label from a series group + its (optional)
 *  coverage response. Used by both Library and Dashboard cards. */
export interface SeriesCompleteness {
  /** "complete" / "partial" / "unknown" classification. */
  status: "complete" | "partial" | "unknown";
  /** Chapters present locally. */
  doneCount: number;
  /** Chapters available on the source (0 when unknown). */
  availableCount: number;
  /** Chapter numbers that the source exposes but aren't on disk. */
  missingNumbers: string[];
}

export function computeCompleteness(
  group: SeriesGroup,
  coverage: CoverageResponse | undefined,
): SeriesCompleteness {
  if (!coverage) {
    return {
      status: "unknown",
      doneCount: group.onDiskChapterNumbers.size,
      availableCount: 0,
      missingNumbers: [],
    };
  }
  const missing = coverage.available
    .filter((c) => !c.on_disk)
    .map((c) => c.chapter_number);
  const status: SeriesCompleteness["status"] =
    missing.length === 0 ? "complete" : "partial";
  return {
    status,
    doneCount: coverage.on_disk_count,
    availableCount: coverage.available_count,
    missingNumbers: missing,
  };
}

/** Compare chapter strings respecting decimal sub-chapter ordering
 *  (so "8.5" sorts after "8" and before "9"). */
export function compareChapterNumbers(a: string | null, b: string | null): number {
  const an = a ? Number(a) : NaN;
  const bn = b ? Number(b) : NaN;
  if (!Number.isNaN(an) && !Number.isNaN(bn)) return an - bn;
  if (Number.isNaN(an) && Number.isNaN(bn)) return (a ?? "").localeCompare(b ?? "");
  return Number.isNaN(an) ? 1 : -1;
}

export function slugify(value: string): string {
  return (
    value
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "series"
  );
}

/** Stable, deterministic gradient pair for a poster placeholder.
 *  Using a hash of the series name keeps the same series consistent
 *  across reloads — feels less random than relying on row index. */
export function posterGradient(series: string): { from: string; to: string } {
  const hash = [...series].reduce((acc, ch) => (acc * 31 + ch.charCodeAt(0)) | 0, 0);
  const palette = [
    ["#0ea5e9", "#1e293b"], // sky → slate
    ["#a855f7", "#1e1b4b"], // violet → indigo
    ["#10b981", "#0f172a"], // emerald → slate
    ["#f97316", "#3f1d1d"], // orange → wine
    ["#f43f5e", "#1e1b4b"], // rose → indigo
    ["#eab308", "#1f1d1b"], // yellow → near-black
    ["#06b6d4", "#0c4a6e"], // cyan → deep sky
    ["#8b5cf6", "#1f0e2a"], // purple → near-black
  ];
  const [from, to] = palette[Math.abs(hash) % palette.length];
  return { from, to };
}
