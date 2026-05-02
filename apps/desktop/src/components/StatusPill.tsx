import type { ReactNode } from "react";

type Tone = "ok" | "warn" | "fail" | "info" | "muted";

const TONE_CLASSES: Record<Tone, string> = {
  ok: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  warn: "bg-amber-100 text-amber-800 ring-amber-200",
  fail: "bg-rose-100 text-rose-800 ring-rose-200",
  info: "bg-sky-100 text-sky-800 ring-sky-200",
  muted: "bg-slate-100 text-slate-700 ring-slate-200",
};

export function StatusPill({
  tone = "muted",
  children,
}: {
  tone?: Tone;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  );
}
