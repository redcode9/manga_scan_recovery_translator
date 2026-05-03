import type { ReactNode } from "react";

type Tone = "ok" | "warn" | "fail" | "info" | "muted" | "live";

const TONE_CLASSES: Record<Tone, string> = {
  ok: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/20",
  warn: "bg-amber-500/10 text-amber-200 ring-amber-500/30",
  fail: "bg-rose-500/10 text-rose-300 ring-rose-500/30",
  info: "bg-sky-500/10 text-sky-300 ring-sky-500/30",
  muted: "bg-zinc-500/10 text-zinc-400 ring-zinc-500/20",
  // ``live`` is rendered with the same hue as ``info`` but a notch
  // brighter; the consumer typically pairs it with a pulsing dot.
  live: "bg-sky-500/15 text-sky-200 ring-sky-400/40",
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
