/**
 * Language toggle (it/en) for the entire UI.
 *
 * The ``settings`` prop is read for backwards-compat with the
 * orchestrator; the live language comes from the ``LanguageProvider``
 * context, which keeps the UI updated without a route change.
 */

import { Globe2 } from "lucide-react";

import { useT, type Language } from "../../../lib/i18n";
import { useToast } from "../../../components/Toast";

const LANGUAGE_CHOICES = [
  { code: "it", labelKey: "settings.language.italian" },
  { code: "en", labelKey: "settings.language.english" },
] as const satisfies ReadonlyArray<{
  code: Language;
  labelKey: "settings.language.italian" | "settings.language.english";
}>;

export function LanguageCard() {
  const { language, setLanguage, t } = useT();
  const toast = useToast();

  const switchLanguage = async (next: Language) => {
    if (next === language) return;
    try {
      await setLanguage(next);
      toast.success(t("settings.language.saved"));
    } catch (err) {
      toast.error(
        t("settings.language.saveError"),
        err instanceof Error ? err.message : undefined,
      );
    }
  };

  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <header className="mb-3">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
          <Globe2 size={16} className="text-zinc-500" aria-hidden="true" />
          {t("settings.language.title")}
        </h2>
        <p className="mt-1 text-xs text-zinc-500">
          {t("settings.language.description")}
        </p>
      </header>
      <div className="flex gap-2">
        {LANGUAGE_CHOICES.map(({ code, labelKey }) => {
          const isActive = code === language;
          return (
            <button
              key={code}
              type="button"
              onClick={() => switchLanguage(code)}
              aria-pressed={isActive}
              className={`inline-flex min-h-9 items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 ${
                isActive
                  ? "bg-zinc-100 text-zinc-950"
                  : "bg-white/10 text-zinc-200 hover:bg-white/15"
              }`}
            >
              {t(labelKey)}
            </button>
          );
        })}
      </div>
    </section>
  );
}
