/**
 * Settings — primo setup self-service della UI.
 *
 * La UI può salvare/rimuovere API key senza mai rileggerne il valore:
 * dopo il submit il campo viene svuotato, e l'API restituisce solo
 * backend usato (Keychain o .env) + messaggio. La pagina mostra sempre
 * presence flags, mai secret in chiaro.
 */

import {
  CheckCircle2,
  Globe2,
  KeyRound,
  PlayCircle,
  Settings as SettingsIcon,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { SecretName, SettingsView } from "../lib/api";
import { StatusPill } from "../components/StatusPill";

type ProviderCard = {
  label: string;
  keyName: SecretName;
  defaultModel: string;
  present: (settings: SettingsView) => boolean;
};

const PROVIDERS: ProviderCard[] = [
  {
    label: "OpenAI",
    keyName: "OPENAI_API_KEY",
    defaultModel: "gpt",
    present: (s) => s.has_openai_key,
  },
  {
    label: "Anthropic",
    keyName: "ANTHROPIC_API_KEY",
    defaultModel: "sonnet",
    present: (s) => s.has_anthropic_key,
  },
  {
    label: "Google Gemini",
    keyName: "GEMINI_API_KEY",
    defaultModel: "gemini-pro",
    present: (s) => s.has_gemini_key,
  },
];

export function SettingsPage() {
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Impostazioni</h1>
        <p className="text-sm text-slate-500">
          Configura provider LLM, modello default, LiteLLM, MITR e cache locale.
        </p>
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
    <div className="space-y-4">
      <DefaultModelCard settings={settings} />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {PROVIDERS.map((provider) => (
          <ProviderKeyCard
            key={provider.keyName}
            provider={provider}
            settings={settings}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
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
    </div>
  );
}

function DefaultModelCard({ settings }: { settings: SettingsView }) {
  const queryClient = useQueryClient();
  const [model, setModel] = useState(settings.default_model);
  const mutation = useMutation({
    mutationFn: () => api.setDefaultModel(model.trim()),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (model.trim()) mutation.mutate();
  };

  return (
    <Card title="Provider & modello default" icon={<SettingsIcon size={18} />}>
      <form onSubmit={onSubmit} className="flex flex-col gap-3 md:flex-row md:items-end">
        <label className="flex-1">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
            Alias modello
          </span>
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full rounded-md border border-slate-200 px-3 py-2 font-mono text-sm focus:border-sky-400 focus:outline-none"
            placeholder="gpt | sonnet | gemini-pro"
          />
        </label>
        <button
          type="submit"
          disabled={mutation.isPending || !model.trim()}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <CheckCircle2 size={16} />
          Salva default
        </button>
      </form>
      <p className="mt-2 text-xs text-slate-500">
        Attuale: <span className="font-mono">{settings.default_model}</span>
      </p>
      {mutation.error && <Feedback tone="fail">{mutation.error.message}</Feedback>}
      {mutation.data && (
        <Feedback tone="ok">Default aggiornato a {mutation.data.default_model}.</Feedback>
      )}
    </Card>
  );
}

function ProviderKeyCard({
  provider,
  settings,
}: {
  provider: ProviderCard;
  settings: SettingsView;
}) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState("");
  const present = provider.present(settings);

  const invalidateSettings = () => queryClient.invalidateQueries({ queryKey: ["settings"] });
  const save = useMutation({
    mutationFn: () => api.saveKey(provider.keyName, value),
    onSuccess: () => {
      setValue("");
      invalidateSettings();
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteKey(provider.keyName),
    onSuccess: invalidateSettings,
  });
  const smoke = useMutation({
    mutationFn: () => api.testModel(provider.defaultModel),
  });

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (value.trim()) save.mutate();
  };

  const busy = save.isPending || remove.isPending || smoke.isPending;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <header className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{provider.label}</h2>
          <p className="font-mono text-xs text-slate-500">{provider.keyName}</p>
        </div>
        <StatusPill tone={present ? "ok" : "muted"}>
          {present ? "presente" : "assente"}
        </StatusPill>
      </header>

      <form onSubmit={onSubmit} className="space-y-3">
        <label>
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
            Nuova API key
          </span>
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            type="password"
            autoComplete="off"
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none"
            placeholder="Incolla la chiave; non verrà mai mostrata dopo il salvataggio"
          />
        </label>

        <div className="flex flex-wrap gap-2">
          <button
            type="submit"
            disabled={busy || !value.trim()}
            className="inline-flex min-h-10 items-center gap-2 rounded-md bg-sky-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <KeyRound size={15} />
            Salva
          </button>
          <button
            type="button"
            disabled={busy || !present}
            onClick={() => remove.mutate()}
            className="inline-flex min-h-10 items-center gap-2 rounded-md bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Trash2 size={15} />
            Rimuovi
          </button>
          <button
            type="button"
            disabled={busy || !present}
            onClick={() => smoke.mutate()}
            className="inline-flex min-h-10 items-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <PlayCircle size={15} />
            Paid smoke
          </button>
        </div>
      </form>

      {save.data && (
        <Feedback tone="ok">
          {save.data.message} Backend: {save.data.backend}.
        </Feedback>
      )}
      {remove.data && <Feedback tone="ok">{remove.data.message}</Feedback>}
      {smoke.data && (
        <Feedback tone={smoke.data.ok ? "ok" : "fail"}>
          {smoke.data.message}
          {smoke.data.latency_ms ? ` (${smoke.data.latency_ms}ms)` : ""}
        </Feedback>
      )}
      {(save.error || remove.error || smoke.error) && (
        <Feedback tone="fail">
          {(save.error ?? remove.error ?? smoke.error)?.message}
        </Feedback>
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
      <div>{children}</div>
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
    <dl className="flex items-center justify-between gap-3 py-1">
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="truncate text-right">{children}</dd>
    </dl>
  );
}

function Feedback({
  tone,
  children,
}: {
  tone: "ok" | "fail";
  children: React.ReactNode;
}) {
  const classes =
    tone === "ok"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : "border-rose-200 bg-rose-50 text-rose-700";
  return (
    <p className={`mt-3 rounded-md border px-3 py-2 text-xs ${classes}`}>
      {children}
    </p>
  );
}
