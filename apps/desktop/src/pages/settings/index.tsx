/**
 * Settings page — thin orchestrator.
 *
 * Every card is its own file under ``cards/``; this module just wires
 * them up, hands each one a fresh ``settings`` snapshot, and provides
 * a single ``invalidate`` callback so any save triggers a refetch of
 * ``/api/settings``. No state lives here.
 */

import { KeyRound, ShieldCheck } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";
import { useT } from "../../lib/i18n";
import { MODEL_PROVIDERS } from "../../lib/models-catalog";
import { StatusPill } from "../../components/StatusPill";

import { AutoCoverCard } from "./cards/AutoCoverCard";
import { DiagnosticsCard } from "./cards/DiagnosticsCard";
import { LanguageCard } from "./cards/LanguageCard";
import { LiteLLMProxyCard } from "./cards/LiteLLMProxyCard";
import { ModelsCard } from "./cards/ModelsCard";
import { ProviderKeyCard } from "./cards/ProviderKeyCard";
import { InfoCard, KeyValue, SectionTitle } from "./shared";

export function SettingsPage() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const invalidateSettings = () =>
    queryClient.invalidateQueries({ queryKey: ["settings"] });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          {t("settings.title")}
        </h1>
        <p className="text-sm text-zinc-500">{t("settings.subtitle")}</p>
      </header>

      {settings.isLoading && (
        <p className="text-sm text-zinc-500">{t("common.loading")}</p>
      )}
      {settings.error && (
        <div className="rounded-md border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
          {settings.error.message}
        </div>
      )}

      {settings.data && (
        <div className="space-y-6">
          <ModelsCard settings={settings.data} onSaved={invalidateSettings} />
          <LanguageCard />
          <AutoCoverCard settings={settings.data} onSaved={invalidateSettings} />

          <section className="space-y-3">
            <SectionTitle>{t("settings.sectionKeys")}</SectionTitle>
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
              {MODEL_PROVIDERS.map((provider) => (
                <ProviderKeyCard
                  key={provider.keyName}
                  provider={provider}
                  settings={settings.data}
                  onChange={invalidateSettings}
                />
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <SectionTitle>{t("settings.sectionRuntime")}</SectionTitle>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <LiteLLMProxyCard settings={settings.data} />
              <InfoCard
                title={t("settings.info.mitr")}
                icon={<ShieldCheck size={18} />}
              >
                <KeyValue label={t("settings.info.binPath")}>
                  {settings.data.mitr_bin_path ? (
                    <span className="font-mono text-sm">
                      {settings.data.mitr_bin_path}
                    </span>
                  ) : (
                    <StatusPill tone="warn">
                      {t("settings.info.notConfigured")}
                    </StatusPill>
                  )}
                </KeyValue>
              </InfoCard>
              <InfoCard
                title={t("settings.info.cache")}
                icon={<KeyRound size={18} />}
              >
                <KeyValue label={t("settings.info.directory")}>
                  <span className="font-mono text-sm">
                    {settings.data.cache_dir}
                  </span>
                </KeyValue>
              </InfoCard>
            </div>
          </section>

          <DiagnosticsCard />
        </div>
      )}
    </div>
  );
}
