/**
 * Settings — vista diagnostica/read-only.
 *
 * Le API key si modificano nel percorso guidato ``/setup``. Qui
 * mostriamo solo presence flag e dettagli operativi, senza mai
 * riportare valori segreti al frontend.
 */

import {
  ArrowRight,
  Download,
  Globe2,
  KeyRound,
  LifeBuoy,
  Settings as SettingsIcon,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { SettingsView } from "../lib/api";
import { StatusPill } from "../components/StatusPill";

export function SettingsPage() {
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });

  return (
    <div className="space-y-6">
      <header className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Impostazioni</h1>
          <p className="text-sm text-slate-500">
            Stato runtime, provider, MITR, LiteLLM e cache locale.
          </p>
        </div>
        <Link
          to="/setup"
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700"
        >
          Apri Setup
          <ArrowRight size={16} />
        </Link>
      </header>

      {settings.isLoading && <p className="text-sm text-slate-500">Caricamento...</p>}
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

      <DiagnosticsCard />
    </div>
  );
}

function DiagnosticsCard() {
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: async () => {
      const payload = await api.diagnostics();
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
    },
    onSuccess: () => setError(null),
    onError: (err: Error) => setError(err.message),
  });

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        <span className="text-slate-400">
          <LifeBuoy size={18} />
        </span>
        Diagnostica
      </h2>
      <p className="mb-3 text-xs text-slate-500">
        Snapshot redatto: chiavi solo come flag presente/assente, doctor
        report e ultimi 20 job. Da allegare alle issue.
      </p>
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className="inline-flex min-h-9 items-center gap-1.5 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Download size={14} />
        {mutation.isPending ? "Genero…" : "Scarica diagnostica"}
      </button>
      {error && (
        <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </p>
      )}
    </section>
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
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
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
