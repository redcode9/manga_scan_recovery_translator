/**
 * Visual primitives shared by every Settings card.
 *
 * Kept tiny on purpose — we don't want a "design system" abstraction
 * here, just the four pieces every card needs (section heading,
 * info-card shell, label/value row, toggle switch). One per file
 * would be over-engineering at this size.
 */

import type { ReactNode } from "react";

import { useT } from "../../lib/i18n";
import type { ModelAlias } from "../../lib/models-catalog";

/** Subtle uppercase heading used between Settings sections. */
export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
      {children}
    </h2>
  );
}

/** Small read-only card with an icon, used for runtime info. */
export function InfoCard({
  title,
  icon,
  children,
}: {
  title: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
        <span className="text-zinc-500" aria-hidden="true">
          {icon}
        </span>
        {title}
      </h3>
      <dl className="space-y-2">{children}</dl>
    </section>
  );
}

/** dl/dt/dd row with the label muted and the value right-aligned. */
export function KeyValue({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-xs uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="truncate text-right">{children}</dd>
    </div>
  );
}

/** Accessible boolean toggle with proper ``role="switch"``. */
export function ToggleSwitch({
  checked,
  disabled,
  onChange,
  ariaLabel,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50 ${
        checked ? "bg-sky-500" : "bg-zinc-700"
      }`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
          checked ? "translate-x-6" : "translate-x-1"
        }`}
        aria-hidden="true"
      />
    </button>
  );
}

/** Subtitle row that shows the catalog metadata for a model alias
 * (resolved id, price, speed tier, optional note). */
export function AliasMeta({ alias }: { alias: ModelAlias }) {
  const { t } = useT();
  // Speed label is the only field we localize at render time — pricing
  // is universal and the optional ``note`` is short technical copy
  // that stays in Italian for now (still readable at a glance for an
  // English user).
  const speedLabel = t(`settings.speed.${alias.speed}` as const);
  return (
    <p className="mt-1 text-[11px] text-zinc-500">
      <span className="font-mono text-zinc-400">{alias.resolvedId}</span>
      <span className="mx-1.5 text-zinc-700">•</span>
      <span>{alias.price}/MTok</span>
      <span className="mx-1.5 text-zinc-700">•</span>
      <span>{speedLabel}</span>
      {alias.note && (
        <>
          <span className="mx-1.5 text-zinc-700">•</span>
          <span>{alias.note}</span>
        </>
      )}
    </p>
  );
}
