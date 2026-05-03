/**
 * Dashboard — colpo d'occhio dello stato dell'ambiente più
 * scorciatoie alle azioni principali.
 *
 * La card "Stato setup" è pensata per chi apre l'app la prima volta:
 * fa il check dei prerequisiti (almeno una API key configurata,
 * LiteLLM up, MITR installato) e mostra il prossimo step necessario.
 * Quando tutto è verde, lascia spazio alle azioni rapide.
 */

import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  CircleX,
  KeyRound,
  Layers,
  Library as LibraryIcon,
  PlayCircle,
  Power,
  Rocket,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { DoctorCheckView, ServerActionResponse, SettingsView } from "../lib/api";
import { StatusPill } from "../components/StatusPill";

export function Dashboard() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const doctor = useQuery({
    queryKey: ["doctor"],
    queryFn: () => api.doctor(),
  });
  const server = useQuery({
    queryKey: ["server-status"],
    queryFn: api.serverStatus,
    refetchInterval: 5_000,
  });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-zinc-500">
          msrt {health.data?.version ?? "…"} — backend pronto su 127.0.0.1.
        </p>
      </header>

      {settings.data && (
        <SetupStatusHero settings={settings.data} server={server.data} />
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <DoctorCard checks={doctor.data?.checks ?? []} loading={doctor.isLoading} />
        <ServerCard
          server={server.data}
          loading={server.isLoading}
          provider={settings.data?.default_model ?? "?"}
        />
      </div>

      <QuickActions />
    </div>
  );
}

interface SetupStep {
  id: string;
  label: string;
  description: string;
  status: "ok" | "warn" | "fail";
  cta?: { to: string; label: string } | { onClick: () => void; label: string };
}

function SetupStatusHero({
  settings,
  server,
}: {
  settings: SettingsView;
  server: ServerActionResponse | undefined;
}) {
  const queryClient = useQueryClient();
  const upMutation = useMutation({
    mutationFn: api.serverUp,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["server-status"] }),
  });

  const hasAnyKey =
    settings.has_anthropic_key ||
    settings.has_openai_key ||
    settings.has_gemini_key;

  const steps: SetupStep[] = [
    {
      id: "keys",
      label: "Chiavi API provider",
      description: hasAnyKey
        ? "Almeno una chiave configurata (preferibilmente nel portachiavi macOS)."
        : "Serve almeno una chiave Anthropic, OpenAI o Google per tradurre.",
      status: hasAnyKey ? "ok" : "fail",
      cta: hasAnyKey
        ? undefined
        : { to: "/setup", label: "Vai al Setup" },
    },
    {
      id: "litellm",
      label: "Proxy LiteLLM",
      description: server?.healthy
        ? "Attivo, pronto a smistare richieste verso il provider."
        : server?.running
          ? "Avviato ma non risponde all'healthcheck."
          : "Non in esecuzione: serve per parlare con il provider LLM.",
      status: server?.healthy ? "ok" : server?.running ? "warn" : "fail",
      cta: server?.healthy
        ? undefined
        : {
            onClick: () => upMutation.mutate(),
            label: upMutation.isPending ? "Avvio…" : "Avvia LiteLLM",
          },
    },
    {
      id: "mitr",
      label: "Motore MITR",
      description: settings.mitr_bin_path
        ? "Configurato — il path è in MITR_BIN_PATH."
        : "Non configurato: msrt usa MITR come motore esterno per traduzione e inpainting.",
      status: settings.mitr_bin_path ? "ok" : "warn",
      cta: settings.mitr_bin_path
        ? undefined
        : { to: "/settings", label: "Verifica path" },
    },
  ];

  const allGreen = steps.every((s) => s.status === "ok");

  if (allGreen) {
    return (
      <section className="overflow-hidden rounded-2xl border border-emerald-500/20 bg-gradient-to-r from-emerald-500/10 via-zinc-900/40 to-transparent p-5">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-500/15 ring-1 ring-emerald-400/30">
            <Rocket className="text-emerald-300" size={18} />
          </div>
          <div className="flex-1">
            <h2 className="text-base font-semibold text-zinc-100">Tutto pronto</h2>
            <p className="text-xs text-zinc-400">
              Setup completo. Puoi creare un nuovo job, lanciare un batch o
              ispezionare la libreria.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              to="/new-job"
              className="inline-flex items-center gap-1.5 rounded-md bg-sky-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 transition hover:bg-sky-400"
            >
              Nuovo job
              <ArrowRight size={14} />
            </Link>
            <Link
              to="/batch"
              className="inline-flex items-center gap-1.5 rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-zinc-100 transition hover:bg-white/15"
            >
              <Layers size={14} />
              Batch
            </Link>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <header className="mb-4">
        <h2 className="text-sm font-semibold uppercase tracking-[0.12em] text-zinc-400">
          Stato setup
        </h2>
        <p className="mt-1 text-xs text-zinc-500">
          Completa questi passi per poter tradurre. Sono tutti gratuiti
          (eccetto le chiamate al provider LLM, che paghi a consumo).
        </p>
      </header>
      <ol className="space-y-2">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className="flex items-start gap-3 rounded-xl bg-white/5 p-3"
          >
            <div className="grid h-7 w-7 place-items-center rounded-full bg-zinc-950/60 text-xs font-mono text-zinc-400 ring-1 ring-white/10">
              {index + 1}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-zinc-100">
                  {step.label}
                </span>
                <SetupStepPill status={step.status} />
              </div>
              <p className="mt-0.5 text-xs text-zinc-500">{step.description}</p>
            </div>
            {step.cta &&
              ("to" in step.cta ? (
                <Link
                  to={step.cta.to}
                  className="inline-flex items-center gap-1 rounded-md bg-sky-500/90 px-3 py-1.5 text-xs font-medium text-zinc-950 transition hover:bg-sky-400"
                >
                  {step.cta.label}
                  <ArrowRight size={12} />
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={step.cta.onClick}
                  className="inline-flex items-center gap-1 rounded-md bg-sky-500/90 px-3 py-1.5 text-xs font-medium text-zinc-950 transition hover:bg-sky-400"
                >
                  <Power size={12} />
                  {step.cta.label}
                </button>
              ))}
          </li>
        ))}
      </ol>
      {upMutation.error && (
        <p className="mt-2 text-xs text-rose-300">
          {upMutation.error.message}
        </p>
      )}
    </section>
  );
}

function SetupStepPill({ status }: { status: "ok" | "warn" | "fail" }) {
  const map = {
    ok: { tone: "ok" as const, label: "ok" },
    warn: { tone: "warn" as const, label: "da verificare" },
    fail: { tone: "fail" as const, label: "da configurare" },
  };
  const { tone, label } = map[status];
  return <StatusPill tone={tone}>{label}</StatusPill>;
}

function DoctorCard({
  checks,
  loading,
}: {
  checks: DoctorCheckView[];
  loading: boolean;
}) {
  return (
    <Card title="Diagnostica ambiente" loading={loading}>
      <ul className="divide-y divide-white/5">
        {checks.map((check) => (
          <li
            key={check.name}
            className="flex items-start justify-between gap-3 py-2.5"
          >
            <div className="flex items-start gap-2.5">
              <DoctorIcon status={check.status} />
              <div>
                <div className="text-sm font-medium text-zinc-100">
                  {check.name}
                </div>
                <div className="text-xs text-zinc-500">{check.message}</div>
              </div>
            </div>
            <StatusPill tone={toneForStatus(check.status)}>
              {check.status}
            </StatusPill>
          </li>
        ))}
        {!loading && checks.length === 0 && (
          <li className="py-3 text-sm text-zinc-500">Nessun check disponibile.</li>
        )}
      </ul>
    </Card>
  );
}

function ServerCard({
  server,
  loading,
  provider,
}: {
  server: ServerActionResponse | undefined;
  loading: boolean;
  provider: string;
}) {
  const queryClient = useQueryClient();
  const upMutation = useMutation({
    mutationFn: api.serverUp,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["server-status"] }),
  });
  const downMutation = useMutation({
    mutationFn: api.serverDown,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["server-status"] }),
  });
  const busy = upMutation.isPending || downMutation.isPending || loading;

  return (
    <Card
      title="LiteLLM"
      headerExtra={
        <StatusPill tone={server?.healthy ? "ok" : server?.running ? "warn" : "fail"}>
          {server?.healthy
            ? "running & healthy"
            : server?.running
              ? "running, unhealthy"
              : "stopped"}
        </StatusPill>
      }
    >
      <dl className="space-y-1 text-sm">
        <Row label="PID" value={server?.pid ? String(server.pid) : "—"} />
        <Row label="Model attivo" value={provider} />
        <Row label="Log" value={server?.log_path ?? "—"} mono />
        <Row label="Messaggio" value={server?.message ?? "—"} />
      </dl>
      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={() => upMutation.mutate()}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <PlayCircle size={14} />
          Avvia
        </button>
        <button
          type="button"
          onClick={() => downMutation.mutate()}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-zinc-200 transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Power size={14} />
          Ferma
        </button>
      </div>
      {(upMutation.error || downMutation.error) && (
        <p className="mt-3 text-xs text-rose-300">
          {(upMutation.error ?? downMutation.error)?.message}
        </p>
      )}
    </Card>
  );
}

function QuickActions() {
  const items: {
    to: string;
    title: string;
    description: string;
    icon: React.ReactNode;
  }[] = [
    {
      to: "/new-job",
      title: "Nuovo Job",
      description: "Cartella locale o singolo URL.",
      icon: <Rocket size={16} className="text-sky-300" />,
    },
    {
      to: "/batch",
      title: "Batch",
      description: "Una serie intera, con dry-run e gap-fill.",
      icon: <Layers size={16} className="text-sky-300" />,
    },
    {
      to: "/library",
      title: "Libreria",
      description: "PDF/CBZ già prodotti, manifest, errori.",
      icon: <LibraryIcon size={16} className="text-sky-300" />,
    },
    {
      to: "/setup",
      title: "Setup",
      description: "Chiavi API, modello di default.",
      icon: <KeyRound size={16} className="text-sky-300" />,
    },
  ];
  return (
    <Card title="Azioni rapide">
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
        {items.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="group flex items-center justify-between rounded-lg border border-white/5 bg-white/5 px-4 py-3 text-left transition hover:bg-white/10 hover:ring-1 hover:ring-sky-400/30"
          >
            <div className="flex items-center gap-3">
              {item.icon}
              <div>
                <div className="text-sm font-medium text-zinc-100">
                  {item.title}
                </div>
                <div className="text-xs text-zinc-500">{item.description}</div>
              </div>
            </div>
            <ChevronRight
              size={18}
              className="text-zinc-500 transition group-hover:text-sky-300"
            />
          </Link>
        ))}
      </div>
    </Card>
  );
}

function Card({
  title,
  loading,
  headerExtra,
  children,
}: {
  title: string;
  loading?: boolean;
  headerExtra?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/5 bg-zinc-900/60 p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
          {title}
        </h2>
        {loading ? (
          <span className="text-xs text-zinc-500">caricamento…</span>
        ) : (
          headerExtra
        )}
      </div>
      {children}
    </section>
  );
}

function DoctorIcon({ status }: { status: string }) {
  if (status === "ok")
    return <CheckCircle2 size={16} className="mt-0.5 text-emerald-400" />;
  if (status === "warn")
    return <CircleAlert size={16} className="mt-0.5 text-amber-300" />;
  if (status === "fail")
    return <CircleX size={16} className="mt-0.5 text-rose-400" />;
  return <CheckCircle2 size={16} className="mt-0.5 text-zinc-500" />;
}

function toneForStatus(
  status: string,
): "ok" | "warn" | "fail" | "info" | "muted" {
  if (status === "ok") return "ok";
  if (status === "warn") return "warn";
  if (status === "fail") return "fail";
  if (status === "info") return "info";
  return "muted";
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-xs uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd
        className={`truncate text-sm text-zinc-200 ${mono ? "font-mono" : ""}`}
        title={value}
      >
        {value}
      </dd>
    </div>
  );
}
