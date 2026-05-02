/**
 * SetupWizard — onboarding interattivo per le chiavi API e il
 * modello di default. Tre card per Anthropic / OpenAI / Google
 * (salva, rimuovi, paid-smoke test) + card per il default model.
 *
 * Le chiavi viaggiano in chiaro solo nel POST verso il backend
 * locale; dopo il salvataggio la UI svuota il campo e mostra solo
 * presence flag + backend usato (keychain o dotenv).
 */

import { useMemo, useState, type FormEvent } from "react";
import {
  CheckCircle2,
  KeyRound,
  Loader2,
  PlayCircle,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import type {
  SecretName,
  SecretReportResponse,
  SetupTestResult,
  SettingsView,
} from "../lib/api";
import { StatusPill } from "../components/StatusPill";

interface ProviderConfig {
  id: "anthropic" | "openai" | "google";
  label: string;
  keyName: SecretName;
  testModel: string;
  helpUrl: string;
  helpLabel: string;
  hint: string;
  placeholder: string;
}

const PROVIDERS: ProviderConfig[] = [
  {
    id: "anthropic",
    label: "Anthropic",
    keyName: "ANTHROPIC_API_KEY",
    testModel: "sonnet",
    helpUrl: "https://console.anthropic.com/settings/keys",
    helpLabel: "console.anthropic.com",
    hint: "Per i modelli Claude (sonnet, opus).",
    placeholder: "sk-ant-…",
  },
  {
    id: "openai",
    label: "OpenAI",
    keyName: "OPENAI_API_KEY",
    testModel: "gpt-mini",
    helpUrl: "https://platform.openai.com/api-keys",
    helpLabel: "platform.openai.com",
    hint: "Per i modelli GPT (gpt, gpt-mini).",
    placeholder: "sk-…",
  },
  {
    id: "google",
    label: "Google Gemini",
    keyName: "GEMINI_API_KEY",
    testModel: "gemini-flash",
    helpUrl: "https://aistudio.google.com/apikey",
    helpLabel: "aistudio.google.com",
    hint: "Per i modelli Gemini (gemini-pro, gemini-flash).",
    placeholder: "AIza…",
  },
];

const MODEL_OPTIONS = [
  { value: "sonnet", label: "sonnet — Anthropic Claude (default)" },
  { value: "opus", label: "opus — Anthropic Claude max quality" },
  { value: "gpt", label: "gpt — OpenAI flagship" },
  { value: "gpt-mini", label: "gpt-mini — OpenAI cheap/draft" },
  { value: "gemini-pro", label: "gemini-pro — Google flagship" },
  { value: "gemini-flash", label: "gemini-flash — Google cheap/fast" },
];

export function SetupWizardPage() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["settings"] });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Setup</h1>
        <p className="text-sm text-slate-500">
          Configura le chiavi API e il modello di default. Le chiavi
          vengono salvate nel portachiavi di sistema quando disponibile,
          altrimenti nel file <code>.env</code>.
        </p>
      </header>

      {settings.isLoading && <p className="text-sm text-slate-500">Caricamento…</p>}
      {settings.error && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {settings.error.message}
        </div>
      )}

      {settings.data && (
        <div className="space-y-4">
          <DefaultModelCard settings={settings.data} onSaved={invalidate} />
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            {PROVIDERS.map((provider) => (
              <ProviderKeyCard
                key={provider.keyName}
                provider={provider}
                settings={settings.data}
                onChange={invalidate}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function isKeyPresent(provider: ProviderConfig, settings: SettingsView): boolean {
  switch (provider.id) {
    case "anthropic":
      return settings.has_anthropic_key;
    case "openai":
      return settings.has_openai_key;
    case "google":
      return settings.has_gemini_key;
  }
}

function ProviderKeyCard({
  provider,
  settings,
  onChange,
}: {
  provider: ProviderConfig;
  settings: SettingsView;
  onChange: () => void;
}) {
  const [value, setValue] = useState("");
  const present = isKeyPresent(provider, settings);

  const save = useMutation({
    mutationFn: () => api.saveKey(provider.keyName, value),
    onSuccess: (_data: SecretReportResponse) => {
      setValue("");
      onChange();
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteKey(provider.keyName),
    onSuccess: onChange,
  });
  const smoke = useMutation({
    mutationFn: () => api.testModel(provider.testModel),
  });

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (value.trim()) save.mutate();
  };

  const busy = save.isPending || remove.isPending || smoke.isPending;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{provider.label}</h2>
          <p className="font-mono text-xs text-slate-500">{provider.keyName}</p>
          <p className="mt-1 text-[11px] text-slate-400">{provider.hint}</p>
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
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={provider.placeholder}
            className="w-full rounded-md border border-slate-200 px-3 py-2 font-mono text-sm focus:border-sky-400 focus:outline-none"
          />
          <p className="mt-1 text-[11px] text-slate-400">
            Dove la trovo:{" "}
            <a
              href={provider.helpUrl}
              target="_blank"
              rel="noreferrer"
              className="text-sky-600 hover:underline"
            >
              {provider.helpLabel}
            </a>
          </p>
        </label>

        <div className="flex flex-wrap gap-2">
          <button
            type="submit"
            disabled={busy || !value.trim()}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <KeyRound size={14} />
            Salva
          </button>
          <button
            type="button"
            disabled={busy || !present}
            onClick={() => remove.mutate()}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-md bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Trash2 size={14} />
            Rimuovi
          </button>
          <button
            type="button"
            disabled={busy || !present}
            onClick={() => smoke.mutate()}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            title={`Mini-chiamata reale a ${provider.testModel} (~ < 0,001 €)`}
          >
            {smoke.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <PlayCircle size={14} />
            )}
            Paid smoke
          </button>
        </div>
      </form>

      {save.data && (
        <Feedback tone={save.data.backend === "keychain" ? "ok" : "warn"}>
          {save.data.message} Backend: <span className="font-mono">{save.data.backend}</span>.
        </Feedback>
      )}
      {remove.data && <Feedback tone="ok">{remove.data.message}</Feedback>}
      {smoke.data && <SmokeBox result={smoke.data} />}
      {(save.error || remove.error || smoke.error) && (
        <Feedback tone="fail">
          {(save.error ?? remove.error ?? smoke.error)?.message}
        </Feedback>
      )}
    </section>
  );
}

function DefaultModelCard({
  settings,
  onSaved,
}: {
  settings: SettingsView;
  onSaved: () => void;
}) {
  const [selected, setSelected] = useState(settings.default_model);
  const dirty = selected !== settings.default_model;

  const mutation = useMutation({
    mutationFn: () => api.setDefaultModel(selected),
    onSuccess: onSaved,
  });

  const options = useMemo(() => {
    const known = new Set(MODEL_OPTIONS.map((o) => o.value));
    if (known.has(settings.default_model)) return MODEL_OPTIONS;
    return [
      ...MODEL_OPTIONS,
      { value: settings.default_model, label: `${settings.default_model} (custom)` },
    ];
  }, [settings.default_model]);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <header className="mb-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          <ShieldCheck size={16} className="text-slate-400" />
          Modello di default
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Usato quando non passi <code>--model</code>. Persistito in
          <code> MSRT_MODEL</code> nel file <code>.env</code>.
        </p>
      </header>

      <div className="flex flex-col gap-3 md:flex-row md:items-end">
        <label className="flex-1">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
            Alias modello
          </span>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none"
          >
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={!dirty || mutation.isPending}
          onClick={() => mutation.mutate()}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <CheckCircle2 size={16} />
          Salva default
        </button>
      </div>

      {mutation.data && (
        <Feedback tone="ok">Default aggiornato a {mutation.data.default_model}.</Feedback>
      )}
      {mutation.error && <Feedback tone="fail">{mutation.error.message}</Feedback>}
    </section>
  );
}

function SmokeBox({ result }: { result: SetupTestResult }) {
  return (
    <Feedback tone={result.ok ? "ok" : "fail"}>
      {result.message}
      {result.latency_ms !== null && ` (${result.latency_ms} ms)`}
    </Feedback>
  );
}

function Feedback({
  tone,
  children,
}: {
  tone: "ok" | "warn" | "fail";
  children: React.ReactNode;
}) {
  const palette = {
    ok: "border-emerald-200 bg-emerald-50 text-emerald-800",
    warn: "border-amber-200 bg-amber-50 text-amber-800",
    fail: "border-rose-200 bg-rose-50 text-rose-700",
  } as const;
  return (
    <p className={`mt-3 rounded-md border px-3 py-2 text-xs ${palette[tone]}`}>
      {children}
    </p>
  );
}
