/**
 * Settings — vista read-only delle impostazioni del backend (v0.4b).
 *
 * Le chiavi API non vengono mai mostrate: solo ``has_*_key`` come
 * pillola di stato. La modifica delle chiavi e l'integrazione con
 * Keychain arriverà in v0.4d insieme al setup wizard completo.
 */

import { Globe2, KeyRound, Settings as SettingsIcon, ShieldCheck } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { SettingsView } from "../lib/api";
import { StatusPill } from "../components/StatusPill";

export function SettingsPage() {
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Impostazioni</h1>
        <p className="text-sm text-slate-500">
          Vista read-only. La modifica delle chiavi e il setup guidato
          arrivano in v0.4d.
        </p>
      </header>

      {settings.isLoading && (
        <p className="text-sm text-slate-500">Caricamento…</p>
      )}
      {settings.error && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {settings.error.message}
        </div>
      )}
      {settings.data && <SettingsBody settings={settings.data} />}
    </div>
  );
}

function SettingsBody({ settings }: { settings: SettingsView }) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card title="Provider & modello" icon={<SettingsIcon size={18} />}>
        <KeyValue label="Modello di default">
          <span className="font-mono text-sm">{settings.default_model}</span>
        </KeyValue>
        <KeyValue label="Anthropic API key">
          <KeyPill present={settings.has_anthropic_key} />
        </KeyValue>
        <KeyValue label="OpenAI API key">
          <KeyPill present={settings.has_openai_key} />
        </KeyValue>
        <KeyValue label="Gemini API key">
          <KeyPill present={settings.has_gemini_key} />
        </KeyValue>
      </Card>

      <Card title="LiteLLM proxy" icon={<Globe2 size={18} />}>
        <KeyValue label="Porta">{String(settings.litellm_port)}</KeyValue>
        <KeyValue label="Base URL">
          <span className="font-mono text-sm">{settings.litellm_base_url}</span>
        </KeyValue>
      </Card>

      <Card title="MITR" icon={<ShieldCheck size={18} />}>
        <KeyValue label="Bin path">
          {settings.mitr_bin_path ? (
            <span className="font-mono text-sm">{settings.mitr_bin_path}</span>
          ) : (
            <StatusPill tone="warn">non configurato</StatusPill>
          )}
        </KeyValue>
      </Card>

      <Card title="Cache" icon={<KeyRound size={18} />}>
        <KeyValue label="Directory">
          <span className="font-mono text-sm">{settings.cache_dir}</span>
        </KeyValue>
      </Card>
    </div>
  );
}

function Card({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        <span className="text-slate-400">{icon}</span>
        {title}
      </h2>
      <dl className="space-y-2">{children}</dl>
    </section>
  );
}

function KeyValue({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="truncate text-right">{children}</dd>
    </div>
  );
}

function KeyPill({ present }: { present: boolean }) {
  return (
    <StatusPill tone={present ? "ok" : "muted"}>
      {present ? "presente" : "assente"}
    </StatusPill>
  );
}
