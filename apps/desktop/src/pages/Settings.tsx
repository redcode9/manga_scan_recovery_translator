/**
 * Impostazioni — un solo posto per tutto.
 *
 * Riunisce in un'unica pagina ciò che prima era diviso in
 * "Setup" + "Impostazioni": configurazione provider e modello
 * default in alto, info read-only sotto, diagnostica in fondo.
 */

import { useMemo, useState, type FormEvent } from "react";
import {
  CheckCircle2,
  Download,
  Globe2,
  ImageIcon,
  KeyRound,
  LifeBuoy,
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
import { useToast } from "../components/Toast";

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
  { value: "sonnet", label: "sonnet — Anthropic Claude" },
  { value: "opus", label: "opus — Anthropic Claude max quality" },
  { value: "gpt", label: "gpt — OpenAI flagship" },
  { value: "gpt-mini", label: "gpt-mini — OpenAI cheap/draft" },
  { value: "gemini-pro", label: "gemini-pro — Google flagship" },
  { value: "gemini-flash", label: "gemini-flash — Google cheap/fast" },
];

export function SettingsPage() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["settings"] });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Impostazioni</h1>
        <p className="text-sm text-zinc-500">
          Provider, modello di default, runtime e diagnostica. Tutto qui.
        </p>
      </header>

      {settings.isLoading && (
        <p className="text-sm text-zinc-500">Caricamento…</p>
      )}
      {settings.error && (
        <div className="rounded-md border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
          {settings.error.message}
        </div>
      )}

      {settings.data && (
        <div className="space-y-6">
          <DefaultModelCard settings={settings.data} onSaved={invalidate} />
          <AutoCoverCard settings={settings.data} onSaved={invalidate} />

          <section className="space-y-3">
            <SectionTitle>Chiavi API provider</SectionTitle>
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
          </section>

          <section className="space-y-3">
            <SectionTitle>Runtime</SectionTitle>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <InfoCard title="LiteLLM proxy" icon={<Globe2 size={18} />}>
                <KeyValue label="Porta">
                  {String(settings.data.litellm_port)}
                </KeyValue>
                <KeyValue label="Base URL">
                  <span className="font-mono text-sm">
                    {settings.data.litellm_base_url}
                  </span>
                </KeyValue>
              </InfoCard>
              <InfoCard title="MITR" icon={<ShieldCheck size={18} />}>
                <KeyValue label="Bin path">
                  {settings.data.mitr_bin_path ? (
                    <span className="font-mono text-sm">
                      {settings.data.mitr_bin_path}
                    </span>
                  ) : (
                    <StatusPill tone="warn">non configurato</StatusPill>
                  )}
                </KeyValue>
              </InfoCard>
              <InfoCard title="Cache" icon={<KeyRound size={18} />}>
                <KeyValue label="Directory">
                  <span className="font-mono text-sm">{settings.data.cache_dir}</span>
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
  const toast = useToast();

  const save = useMutation({
    mutationFn: () => api.saveKey(provider.keyName, value),
    onSuccess: (data: SecretReportResponse) => {
      setValue("");
      toast.success(
        `Chiave ${provider.label} salvata`,
        data.backend === "keychain"
          ? "Conservata nel portachiavi macOS."
          : "Conservata in .env (portachiavi non disponibile).",
      );
      onChange();
    },
    onError: (err: Error) => toast.error("Salvataggio fallito", err.message),
  });
  const remove = useMutation({
    mutationFn: () => api.deleteKey(provider.keyName),
    onSuccess: () => {
      toast.info(`Chiave ${provider.label} rimossa`);
      onChange();
    },
    onError: (err: Error) => toast.error("Rimozione fallita", err.message),
  });
  const smoke = useMutation({
    mutationFn: () => api.testModel(provider.testModel),
    onSuccess: (data: SetupTestResult) => {
      if (data.ok) {
        toast.success(
          `Test ${provider.label} OK`,
          data.latency_ms ? `Latenza ${data.latency_ms} ms.` : undefined,
        );
      } else {
        toast.error(`Test ${provider.label} fallito`, data.message);
      }
    },
    onError: (err: Error) =>
      toast.error(`Test ${provider.label} fallito`, err.message),
  });

  const onRemove = () => {
    const ok = window.confirm(
      `Rimuovere la chiave ${provider.keyName}? L'azione cancella la voce dal portachiavi e dal file .env.`,
    );
    if (ok) remove.mutate();
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (value.trim()) save.mutate();
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
        <StatusPill tone={present ? "ok" : "muted"}>
          {present ? "presente" : "assente"}
        </StatusPill>
      </header>

      <form onSubmit={onSubmit} className="space-y-3">
        <label>
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
            Nuova API key
          </span>
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={provider.placeholder}
            className="w-full rounded-md border border-white/10 bg-zinc-950/60 px-3 py-2 font-mono text-sm shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 focus:ring-offset-1 focus:ring-offset-zinc-950"
          />
          <p className="mt-1 text-[11px] text-zinc-500">
            Dove la trovo:{" "}
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
            disabled={busy || !value.trim()}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-sky-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <KeyRound size={14} aria-hidden="true" />
            Salva
          </button>
          <button
            type="button"
            disabled={busy || !present}
            onClick={onRemove}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-zinc-200 shadow-sm transition hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label={`Rimuovi chiave ${provider.label}`}
          >
            <Trash2 size={14} aria-hidden="true" />
            Rimuovi
          </button>
          <button
            type="button"
            disabled={busy || !present}
            onClick={() => smoke.mutate()}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-emerald-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
            title={`Mini-chiamata reale a ${provider.testModel} (~ < 0,001 €)`}
            aria-label={`Test della chiave ${provider.label}`}
          >
            {smoke.isPending ? (
              <Loader2 size={14} className="animate-spin" aria-hidden="true" />
            ) : (
              <PlayCircle size={14} aria-hidden="true" />
            )}
            Test
          </button>
        </div>
      </form>
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
  const toast = useToast();

  const mutation = useMutation({
    mutationFn: () => api.setDefaultModel(selected),
    onSuccess: (data) => {
      toast.success(`Modello di default → ${data.default_model}`);
      onSaved();
    },
    onError: (err: Error) => toast.error("Salvataggio fallito", err.message),
  });

  const options = useMemo(() => {
    const known = new Set(MODEL_OPTIONS.map((o) => o.value));
    const current = settings.default_model;
    const decorate = (entry: { value: string; label: string }) =>
      entry.value === current
        ? { ...entry, label: `${entry.label} — corrente` }
        : entry;
    if (known.has(current)) return MODEL_OPTIONS.map(decorate);
    return [
      ...MODEL_OPTIONS.map(decorate),
      { value: current, label: `${current} (custom) — corrente` },
    ];
  }, [settings.default_model]);

  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <header className="mb-3">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
          <ShieldCheck size={16} className="text-zinc-500" aria-hidden="true" />
          Modello di default
        </h2>
        <p className="mt-1 text-xs text-zinc-500">
          Usato quando non passi un modello esplicito. Persistito in
          <code> MSRT_MODEL</code> nel file <code>.env</code>.
        </p>
      </header>

      <div className="flex flex-col gap-3 md:flex-row md:items-end">
        <label className="flex-1">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
            Alias modello
          </span>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="w-full rounded-md border border-white/10 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100 shadow-sm transition focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 focus:ring-offset-1 focus:ring-offset-zinc-950"
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
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <CheckCircle2 size={16} aria-hidden="true" />
          Salva default
        </button>
      </div>
    </section>
  );
}

function AutoCoverCard({
  settings,
  onSaved,
}: {
  settings: SettingsView;
  onSaved: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const mutation = useMutation({
    mutationFn: (enabled: boolean) => api.setAutoCover(enabled),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["library"] });
      toast.success(
        data.auto_cover_enabled
          ? "Recupero copertine attivato"
          : "Recupero copertine disattivato",
      );
      onSaved();
    },
    onError: (err: Error) => toast.error("Salvataggio fallito", err.message),
  });

  const enabled = settings.auto_cover_enabled;

  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <header className="mb-3">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
          <ImageIcon size={16} className="text-zinc-500" aria-hidden="true" />
          Recupero automatico copertine
        </h2>
        <p className="mt-1 text-xs text-zinc-500">
          Ogni serie nella libreria riceve automaticamente la migliore
          copertina disponibile, in quest'ordine: <strong>MangaDex</strong>{" "}
          (per le serie con UUID titolo) → <strong>AniList</strong>{" "}
          (catalogo globale per nome) → <strong>composito locale</strong>{" "}
          dalle scan già su disco → <strong>generata da AI</strong>{" "}
          (richiede una chiave OpenAI). Disattiva il toggle se preferisci
          il poster a gradiente per tutte le serie.
        </p>
      </header>
      <div className="flex items-center justify-between gap-4 rounded-lg border border-white/5 bg-zinc-950/40 p-3">
        <div className="text-sm">
          <p className="font-medium text-zinc-100">
            {enabled ? "Attivo" : "Disattivato"}
          </p>
          <p className="text-xs text-zinc-500">
            {enabled
              ? "Le card della libreria mostrano la copertina ufficiale o generata."
              : "Tutte le card mostrano il poster a gradiente con le iniziali."}
          </p>
        </div>
        <ToggleSwitch
          checked={enabled}
          disabled={mutation.isPending}
          onChange={(value) => mutation.mutate(value)}
          ariaLabel="Recupero automatico copertine"
        />
      </div>
    </section>
  );
}

function ToggleSwitch({
  checked,
  disabled,
  onChange,
  ariaLabel,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50 ${
        checked ? "bg-sky-500" : "bg-zinc-700"
      }`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
          checked ? "translate-x-6" : "translate-x-1"
        }`}
        aria-hidden="true"
      />
    </button>
  );
}

function DiagnosticsCard() {
  const toast = useToast();
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
    onSuccess: () => toast.success("Diagnostica scaricata"),
    onError: (err: Error) =>
      toast.error("Scaricamento diagnostica fallito", err.message),
  });

  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
        <LifeBuoy size={16} className="text-zinc-500" aria-hidden="true" />
        Diagnostica
      </h2>
      <p className="mb-3 text-xs text-zinc-500">
        Snapshot redatto: chiavi solo come flag presente/assente, doctor
        report e ultimi 20 job. Da allegare alle issue.
      </p>
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-zinc-100 px-3 py-1.5 text-sm font-medium text-zinc-950 transition hover:bg-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Download size={14} aria-hidden="true" />
        {mutation.isPending ? "Genero…" : "Scarica diagnostica"}
      </button>
    </section>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
      {children}
    </h2>
  );
}

function InfoCard({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
        <span className="text-zinc-500" aria-hidden="true">
          {icon}
        </span>
        {title}
      </h3>
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
      <dt className="text-xs uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="truncate text-right">{children}</dd>
    </div>
  );
}
