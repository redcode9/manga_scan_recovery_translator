/**
 * Single provider's API-key card: save, delete, test.
 *
 * The "Test" button always exercises the user's *preferred* alias for
 * this provider — so changing the per-provider preference in the
 * Models card immediately reflects in which model gets the smoke
 * call. That matches what the fallback chain will use at job time.
 */

import { KeyRound, Loader2, PlayCircle, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";

import { api } from "../../../lib/api";
import type {
  SecretReportResponse,
  SettingsView,
  SetupTestResult,
} from "../../../lib/api";
import { useT } from "../../../lib/i18n";
import {
  isProviderKeyPresent,
  preferredModelForProvider,
  type ProviderConfig,
} from "../../../lib/models-catalog";
import { StatusPill } from "../../../components/StatusPill";
import { useToast } from "../../../components/Toast";

export function ProviderKeyCard({
  provider,
  settings,
  onChange,
}: {
  provider: ProviderConfig;
  settings: SettingsView;
  onChange: () => void;
}) {
  const { t } = useT();
  const toast = useToast();
  const [draftKey, setDraftKey] = useState("");
  const isKeyPresent = isProviderKeyPresent(provider.id, settings);
  const testModel = preferredModelForProvider(settings, provider.id);

  const save = useMutation({
    mutationFn: () => api.saveKey(provider.keyName, draftKey),
    onSuccess: (data: SecretReportResponse) => {
      setDraftKey("");
      toast.success(
        t("settings.apiKey.saved", { provider: provider.label }),
        data.message ||
          t(
            data.backend === "keychain"
              ? "settings.apiKey.savedKeychain"
              : "settings.apiKey.savedDotenv",
          ),
      );
      onChange();
    },
    onError: (err: Error) =>
      toast.error(t("settings.apiKey.saveFailed"), err.message),
  });
  const remove = useMutation({
    mutationFn: () => api.deleteKey(provider.keyName),
    onSuccess: (data: SecretReportResponse) => {
      toast.info(
        t("settings.apiKey.removed", { provider: provider.label }),
        data.message,
      );
      onChange();
    },
    onError: (err: Error) =>
      toast.error(t("settings.apiKey.removeFailed"), err.message),
  });
  const smoke = useMutation({
    mutationFn: () => api.testModel(testModel),
    onSuccess: (data: SetupTestResult) => {
      if (data.ok) {
        toast.success(
          t("settings.apiKey.testOk", {
            provider: provider.label,
            model: testModel,
          }),
          data.latency_ms
            ? t("settings.apiKey.latency", { ms: data.latency_ms })
            : undefined,
        );
      } else {
        toast.error(
          t("settings.apiKey.testFailed", { provider: provider.label }),
          data.message,
        );
      }
    },
    onError: (err: Error) =>
      toast.error(
        t("settings.apiKey.testFailed", { provider: provider.label }),
        err.message,
      ),
  });

  const onConfirmRemove = () => {
    const ok = window.confirm(
      t("settings.apiKey.removeConfirm", { key: provider.keyName }),
    );
    if (ok) remove.mutate();
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (draftKey.trim()) save.mutate();
  };

  const busy = save.isPending || remove.isPending || smoke.isPending;

  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-4 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-zinc-100">
            {provider.label}
          </h3>
          <p className="font-mono text-xs text-zinc-500">{provider.keyName}</p>
          <p className="mt-1 text-[11px] text-zinc-500">{provider.hint}</p>
        </div>
        <StatusPill tone={isKeyPresent ? "ok" : "muted"}>
          {isKeyPresent ? t("common.presentBadge") : t("common.absentBadge")}
        </StatusPill>
      </header>

      <form onSubmit={onSubmit} className="space-y-3">
        <label>
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
            {t("settings.apiKey.newLabel")}
          </span>
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={draftKey}
            onChange={(event) => setDraftKey(event.target.value)}
            placeholder={provider.placeholder}
            className="w-full rounded-md border border-white/10 bg-zinc-950/60 px-3 py-2 font-mono text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 focus:ring-offset-1 focus:ring-offset-zinc-950"
          />
          <p className="mt-1 text-[11px] text-zinc-500">
            {t("settings.apiKey.whereToFind")}{" "}
            <a
              href={provider.helpUrl}
              target="_blank"
              rel="noreferrer"
              className="text-sky-300 hover:underline"
            >
              {provider.helpLabel}
            </a>
          </p>
        </label>

        <div className="flex flex-wrap gap-2">
          <button
            type="submit"
            disabled={busy || !draftKey.trim()}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-sky-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <KeyRound size={14} aria-hidden="true" />
            {t("settings.apiKey.saveButton")}
          </button>
          <button
            type="button"
            disabled={busy || !isKeyPresent}
            onClick={onConfirmRemove}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-zinc-200 shadow-sm transition hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label={t("settings.apiKey.removeAriaLabel", {
              provider: provider.label,
            })}
          >
            <Trash2 size={14} aria-hidden="true" />
            {t("settings.apiKey.removeButton")}
          </button>
          <button
            type="button"
            disabled={busy || !isKeyPresent}
            onClick={() => smoke.mutate()}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-emerald-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
            title={t("settings.apiKey.testHint", { model: testModel })}
            aria-label={t("settings.apiKey.testAriaLabel", {
              provider: provider.label,
              model: testModel,
            })}
          >
            {smoke.isPending ? (
              <Loader2 size={14} className="animate-spin" aria-hidden="true" />
            ) : (
              <PlayCircle size={14} aria-hidden="true" />
            )}
            {t("settings.apiKey.testButton", { model: testModel })}
          </button>
        </div>
      </form>
    </section>
  );
}
