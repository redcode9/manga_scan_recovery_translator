/**
 * Primary model + per-provider fallback in one card.
 *
 * Two layers of choice:
 *   1. **Primary**: the model used when a job doesn't specify an
 *      override. Pulled from every alias across providers — the user
 *      can pick e.g. ``opus`` even if their preferred Anthropic model
 *      below is ``haiku``.
 *   2. **Fallback per provider**: when the primary's quota runs out
 *      mid-batch the runner walks every provider with a configured
 *      key, using that provider's preferred alias here. So this is
 *      *also* what the "Test" button on each ProviderKeyCard hits.
 */

import { CheckCircle2, Loader2, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { api } from "../../../lib/api";
import type { ProviderModelsResponse, SettingsView } from "../../../lib/api";
import { useT } from "../../../lib/i18n";
import {
  MODEL_PROVIDERS,
  findAliasInCatalog,
} from "../../../lib/models-catalog";
import { useToast } from "../../../components/Toast";
import { AliasMeta } from "../shared";

interface ModelDraft {
  primary: string;
  openai: string;
  anthropic: string;
  google: string;
}

function readDraftFromSettings(settings: SettingsView): ModelDraft {
  return {
    primary: settings.default_model,
    openai: settings.model_openai,
    anthropic: settings.model_anthropic,
    google: settings.model_google,
  };
}

export function ModelsCard({
  settings,
  onSaved,
}: {
  settings: SettingsView;
  onSaved: () => void;
}) {
  const { t } = useT();
  const toast = useToast();
  const [draft, setDraft] = useState<ModelDraft>(() => readDraftFromSettings(settings));

  // Keep local state in sync when /api/settings refetches with new
  // values (e.g. another tab saved them, or the backend just hydrated).
  useEffect(() => {
    setDraft(readDraftFromSettings(settings));
  }, [
    settings.default_model,
    settings.model_openai,
    settings.model_anthropic,
    settings.model_google,
  ]);

  const isPrimaryDirty = draft.primary !== settings.default_model;
  const areProvidersDirty =
    draft.openai !== settings.model_openai ||
    draft.anthropic !== settings.model_anthropic ||
    draft.google !== settings.model_google;
  const isDirty = isPrimaryDirty || areProvidersDirty;

  const persist = useMutation({
    mutationFn: async () => {
      // Save provider preferences first so the fallback chain is
      // already coherent when the new primary is persisted.
      let providerResponse: ProviderModelsResponse | null = null;
      if (areProvidersDirty) {
        providerResponse = await api.setProviderModels({
          openai: draft.openai,
          anthropic: draft.anthropic,
          google: draft.google,
        });
      }
      if (isPrimaryDirty) await api.setDefaultModel(draft.primary);
      return providerResponse;
    },
    onSuccess: () => {
      toast.success(t("settings.modelsCard.saveSuccess"));
      onSaved();
    },
    onError: (err: Error) =>
      toast.error(t("settings.modelsCard.saveError"), err.message),
  });

  const primaryMeta = findAliasInCatalog(draft.primary);
  const isPrimaryCustom = primaryMeta === null;

  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <header className="mb-4">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
          <ShieldCheck size={16} className="text-zinc-500" aria-hidden="true" />
          {t("settings.modelsCard.title")}
        </h2>
        <p className="mt-1 text-xs text-zinc-500">
          {t("settings.modelsCard.description")}
        </p>
      </header>

      <div className="space-y-4">
        <div>
          <label className="text-sm">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
              {t("settings.modelsCard.primaryLabel")}
            </span>
            <select
              value={draft.primary}
              onChange={(event) =>
                setDraft((prev) => ({ ...prev, primary: event.target.value }))
              }
              className="w-full rounded-md border border-white/10 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100 shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 focus:ring-offset-1 focus:ring-offset-zinc-950"
            >
              {MODEL_PROVIDERS.map((provider) => (
                <optgroup key={provider.id} label={provider.label}>
                  {provider.aliases.map((alias) => (
                    <option key={alias.value} value={alias.value}>
                      {alias.label} · {alias.price}
                      {t("settings.modelsCard.perMTokSuffix")}
                    </option>
                  ))}
                </optgroup>
              ))}
              {isPrimaryCustom && (
                <option value={draft.primary}>
                  {draft.primary} {t("settings.modelsCard.customSuffix")}
                </option>
              )}
            </select>
          </label>
          {primaryMeta && <AliasMeta alias={primaryMeta.alias} />}
        </div>

        <div>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
            {t("settings.modelsCard.fallbackTitle")}
          </h3>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {MODEL_PROVIDERS.map((provider) => {
              const selectedValue = draft[provider.id];
              const selectedAlias = provider.aliases.find(
                (alias) => alias.value === selectedValue,
              );
              return (
                <div key={provider.id}>
                  <label className="text-sm">
                    <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                      {provider.label}
                    </span>
                    <select
                      value={selectedValue}
                      onChange={(event) =>
                        setDraft((prev) => ({
                          ...prev,
                          [provider.id]: event.target.value,
                        }))
                      }
                      className="w-full rounded-md border border-white/10 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100 shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 focus:ring-offset-1 focus:ring-offset-zinc-950"
                    >
                      {provider.aliases.map((alias) => (
                        <option key={alias.value} value={alias.value}>
                          {alias.label} · {alias.price}
                          {t("settings.modelsCard.perMTokSuffix")}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selectedAlias && <AliasMeta alias={selectedAlias} />}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="mt-5 flex items-center justify-end gap-3">
        {isDirty && (
          <span className="text-xs text-amber-300">
            {t("common.unsavedChanges")}
          </span>
        )}
        <button
          type="button"
          disabled={!isDirty || persist.isPending}
          onClick={() => persist.mutate()}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {persist.isPending ? (
            <Loader2 size={16} className="animate-spin" aria-hidden="true" />
          ) : (
            <CheckCircle2 size={16} aria-hidden="true" />
          )}
          {t("common.save")}
        </button>
      </div>
    </section>
  );
}
