/**
 * Download a redacted diagnostics bundle (settings flags, doctor
 * report, last 20 jobs). Safe to attach to GitHub issues — keys are
 * exposed only as boolean ``has_*_key`` flags.
 */

import { Download, LifeBuoy } from "lucide-react";
import { useMutation } from "@tanstack/react-query";

import { api } from "../../../lib/api";
import { useT } from "../../../lib/i18n";
import { useToast } from "../../../components/Toast";

function downloadJsonBundle(payload: unknown): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  link.download = `msrt-diagnostics-${stamp}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function DiagnosticsCard() {
  const { t } = useT();
  const toast = useToast();
  const downloadDiagnostics = useMutation({
    mutationFn: async () => downloadJsonBundle(await api.diagnostics()),
    onSuccess: () => toast.success(t("settings.diagnostics.success")),
    onError: (err: Error) =>
      toast.error(t("settings.diagnostics.error"), err.message),
  });

  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
        <LifeBuoy size={16} className="text-zinc-500" aria-hidden="true" />
        {t("settings.diagnostics.title")}
      </h2>
      <p className="mb-3 text-xs text-zinc-500">
        {t("settings.diagnostics.description")}
      </p>
      <button
        type="button"
        onClick={() => downloadDiagnostics.mutate()}
        disabled={downloadDiagnostics.isPending}
        className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-zinc-100 px-3 py-1.5 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Download size={14} aria-hidden="true" />
        {downloadDiagnostics.isPending
          ? t("settings.diagnostics.generating")
          : t("settings.diagnostics.download")}
      </button>
    </section>
  );
}
