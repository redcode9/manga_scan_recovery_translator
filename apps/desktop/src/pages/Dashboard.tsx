/**
 * Dashboard — colpo d'occhio dello stato dell'ambiente più
 * scorciatoie alle azioni principali.
 *
 * Fonti dati:
 *   GET /api/health     liveness / version
 *   GET /api/doctor     checklist strutturata
 *   GET /api/server     stato LiteLLM
 *   GET /api/settings   provider, model, MITR path, has_*_key
 */

import { CheckCircle2, ChevronRight, CircleAlert, CircleX } from "lucide-react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { DoctorCheckView } from "../lib/api";
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
  server: import("../lib/api").ServerActionResponse | undefined;
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
        <StatusPill
          tone={server?.healthy ? "ok" : server?.running ? "warn" : "fail"}
        >
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
          className="inline-flex items-center rounded-md bg-emerald-500/90 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Avvia
        </button>
        <button
          type="button"
          onClick={() => downMutation.mutate()}
          disabled={busy}
          className="inline-flex items-center rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-zinc-200 transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-50"
        >
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
  const items: { to: string; title: string; description: string }[] = [
    {
      to: "/new-job",
      title: "Nuovo Job",
      description: "Cartella locale o URL singolo capitolo.",
    },
    {
      to: "/batch",
      title: "Batch dry-run",
      description: "Lista capitoli di una serie e selezione range/limite.",
    },
    {
      to: "/library",
      title: "Apri Libreria",
      description: "PDF/CBZ già prodotti, manifest, errori.",
    },
  ];
  return (
    <Card title="Azioni rapide">
      <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
        {items.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="group flex items-center justify-between rounded-lg border border-white/5 bg-white/5 px-4 py-3 text-left transition hover:bg-white/10 hover:ring-1 hover:ring-sky-400/30"
          >
            <div>
              <div className="text-sm font-medium text-zinc-100">{item.title}</div>
              <div className="text-xs text-zinc-500">{item.description}</div>
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
