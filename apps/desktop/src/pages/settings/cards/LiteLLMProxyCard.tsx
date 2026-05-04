/**
 * LiteLLM proxy lifecycle card: status, start, stop, restart.
 *
 * Restart = stop + start. Useful when the user has just changed an
 * API key while the proxy was already up: the proxy is a separate
 * subprocess and only sees the new env after a restart. The backend
 * already auto-restarts on save-key, but exposing the button is
 * helpful for cases like "I edited .env by hand" or "the proxy was
 * started before the keys were configured".
 */

import { Globe2, Loader2, PlayCircle, RefreshCcw } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../../lib/api";
import type { SettingsView } from "../../../lib/api";
import { useT } from "../../../lib/i18n";
import { StatusPill } from "../../../components/StatusPill";
import { useToast } from "../../../components/Toast";
import { KeyValue } from "../shared";

const STATUS_REFETCH_MS = 5000;

export function LiteLLMProxyCard({ settings }: { settings: SettingsView }) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const toast = useToast();
  const status = useQuery({
    queryKey: ["server-status"],
    queryFn: api.serverStatus,
    refetchInterval: STATUS_REFETCH_MS,
  });

  const invalidateStatus = () =>
    queryClient.invalidateQueries({ queryKey: ["server-status"] });

  const restart = useMutation({
    mutationFn: async () => {
      await api.serverDown();
      return api.serverUp();
    },
    onSuccess: (data) => {
      invalidateStatus();
      if (data.healthy) toast.success(t("proxy.restartedSuccess"), data.message);
      else toast.error(t("proxy.restartedHealthcheckFailed"), data.message);
    },
    onError: (err: Error) => toast.error(t("proxy.restartFailed"), err.message),
  });
  const start = useMutation({
    mutationFn: () => api.serverUp(),
    onSuccess: (data) => {
      invalidateStatus();
      toast.success(t("proxy.started"), data.message);
    },
    onError: (err: Error) => toast.error(t("proxy.startFailed"), err.message),
  });
  const stop = useMutation({
    mutationFn: () => api.serverDown(),
    onSuccess: () => {
      invalidateStatus();
      toast.info(t("proxy.stopped_toast"));
    },
    onError: (err: Error) => toast.error(t("proxy.stopFailed"), err.message),
  });

  const isRunning = status.data?.running ?? false;
  const isHealthy = status.data?.healthy ?? false;
  const tone: "ok" | "warn" | "muted" = isRunning
    ? isHealthy
      ? "ok"
      : "warn"
    : "muted";
  const statusLabel = isRunning
    ? isHealthy
      ? t("proxy.statusUp")
      : t("proxy.statusUnhealthy")
    : t("proxy.statusDown");
  const isBusy = restart.isPending || start.isPending || stop.isPending;

  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <header className="mb-3 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
          <span className="text-zinc-500" aria-hidden="true">
            <Globe2 size={18} />
          </span>
          {t("proxy.title")}
        </h3>
        <StatusPill tone={tone}>{statusLabel}</StatusPill>
      </header>
      <dl className="space-y-2">
        <KeyValue label={t("proxy.portLabel")}>
          {String(settings.litellm_port)}
        </KeyValue>
        <KeyValue label={t("proxy.baseUrlLabel")}>
          <span className="font-mono text-sm">{settings.litellm_base_url}</span>
        </KeyValue>
      </dl>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={isBusy || !isRunning}
          onClick={() => restart.mutate()}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-md bg-sky-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
          title={t("proxy.restartHint")}
        >
          {restart.isPending ? (
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          ) : (
            <RefreshCcw size={14} aria-hidden="true" />
          )}
          {t("proxy.restart")}
        </button>
        {isRunning ? (
          <button
            type="button"
            disabled={isBusy}
            onClick={() => stop.mutate()}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-zinc-200 shadow-sm transition hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("proxy.stop")}
          </button>
        ) : (
          <button
            type="button"
            disabled={isBusy}
            onClick={() => start.mutate()}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-md bg-emerald-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {start.isPending ? (
              <Loader2 size={14} className="animate-spin" aria-hidden="true" />
            ) : (
              <PlayCircle size={14} aria-hidden="true" />
            )}
            {t("proxy.start")}
          </button>
        )}
      </div>
      {status.data?.message && (
        <p className="mt-2 text-[11px] text-zinc-500">{status.data.message}</p>
      )}
    </section>
  );
}
