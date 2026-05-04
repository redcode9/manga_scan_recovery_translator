/**
 * Toggle for the automatic cover-art resolver chain
 * (MangaDex → AniList → on-disk composite → AI generation).
 */

import { ImageIcon } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../../../lib/api";
import type { SettingsView } from "../../../lib/api";
import { useT } from "../../../lib/i18n";
import { useToast } from "../../../components/Toast";
import { ToggleSwitch } from "../shared";

export function AutoCoverCard({
  settings,
  onSaved,
}: {
  settings: SettingsView;
  onSaved: () => void;
}) {
  const { t } = useT();
  const queryClient = useQueryClient();
  const toast = useToast();
  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api.setAutoCover(enabled),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["library"] });
      toast.success(
        data.auto_cover_enabled
          ? t("settings.autoCover.enabledSuccess")
          : t("settings.autoCover.disabledSuccess"),
      );
      onSaved();
    },
    onError: (err: Error) =>
      toast.error(t("settings.modelsCard.saveError"), err.message),
  });

  const isEnabled = settings.auto_cover_enabled;

  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <header className="mb-3">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
          <ImageIcon size={16} className="text-zinc-500" aria-hidden="true" />
          {t("settings.autoCover.title")}
        </h2>
        <p className="mt-1 text-xs text-zinc-500">
          {t("settings.autoCover.description")}
        </p>
      </header>
      <div className="flex items-center justify-between gap-4 rounded-lg border border-white/5 bg-zinc-950/40 p-3">
        <div className="text-sm">
          <p className="font-medium text-zinc-100">
            {isEnabled
              ? t("settings.autoCover.enabled")
              : t("settings.autoCover.disabled")}
          </p>
          <p className="text-xs text-zinc-500">
            {isEnabled
              ? t("settings.autoCover.enabledHint")
              : t("settings.autoCover.disabledHint")}
          </p>
        </div>
        <ToggleSwitch
          checked={isEnabled}
          disabled={toggle.isPending}
          onChange={(value) => toggle.mutate(value)}
          ariaLabel={t("settings.autoCover.toggleAria")}
        />
      </div>
    </section>
  );
}
