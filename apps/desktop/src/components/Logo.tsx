/**
 * Logo — marchio msrt.
 *
 * Identità visiva:
 *  - quadrato a bordi morbidi (rx=22%) come una "panel" da manga
 *  - dentro, una speech-bubble bianca leggermente trasparente
 *  - sopra la bubble, un check-mark stilizzato con tratto sky-500
 *  - sfondo gradiente sky-500 → violet-500 (lo stesso accento usato
 *    in tutta la UI: dashboard hero, cta primario, banner attivo)
 *
 * Il marchio è SVG inline così rimane crisp a qualsiasi DPI e segue
 * via ``currentColor`` lo stato di hover/focus del contenitore quando
 * serve.
 */

interface LogoProps {
  size?: number;
  className?: string;
  /** Accessible label. Default: "msrt — Manga Scan Recovery Translator". */
  title?: string;
  decorative?: boolean;
}

export function Logo({ size = 36, className, title, decorative }: LogoProps) {
  const labelId = "msrt-logo-title";
  const accessibleTitle = title ?? "msrt — Manga Scan Recovery Translator";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role={decorative ? "presentation" : "img"}
      aria-hidden={decorative ? "true" : undefined}
      aria-labelledby={decorative ? undefined : labelId}
      className={className}
    >
      {!decorative && <title id={labelId}>{accessibleTitle}</title>}
      <defs>
        <linearGradient id="msrt-logo-bg" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#0ea5e9" />
          <stop offset="100%" stopColor="#7c3aed" />
        </linearGradient>
        <linearGradient id="msrt-logo-bg-soft" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#7c3aed" stopOpacity="0.25" />
        </linearGradient>
      </defs>
      {/* Outer panel */}
      <rect
        x="0.5"
        y="0.5"
        width="31"
        height="31"
        rx="7"
        fill="url(#msrt-logo-bg)"
      />
      {/* Subtle inner highlight for depth */}
      <rect
        x="2"
        y="2"
        width="28"
        height="28"
        rx="6"
        fill="url(#msrt-logo-bg-soft)"
      />
      {/* Speech bubble */}
      <path
        d="M9.2 9.5h13.6c1.4 0 2.5 1.1 2.5 2.5v6.6c0 1.4-1.1 2.5-2.5 2.5h-6.4l-3.7 3.4v-3.4h-3.5c-1.4 0-2.5-1.1-2.5-2.5V12c0-1.4 1.1-2.5 2.5-2.5z"
        fill="#ffffff"
        fillOpacity="0.94"
      />
      {/* Translated checkmark inside */}
      <path
        d="M11.8 15.4l3 3 5.4-5.4"
        stroke="#0ea5e9"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Wordmark version: logo + label, used in AppShell. */
export function LogoMark({ size = 36 }: { size?: number }) {
  return (
    <span className="flex items-center gap-2.5">
      <Logo size={size} />
      <span className="leading-tight">
        <span className="block text-base font-semibold tracking-tight text-zinc-100">
          msrt
        </span>
        <span className="block text-[11px] text-zinc-500">manga translator</span>
      </span>
    </span>
  );
}
