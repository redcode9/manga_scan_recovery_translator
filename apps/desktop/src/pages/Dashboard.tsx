/**
 * Dashboard — colpo d'occhio dello stato dell'ambiente più
 * scorciatoie alle azioni principali.
 *
 * Fonti dati:
 *   GET /api/health     liveness / version
 *   GET /api/doctor     checklist strutturata
 *   GET /api/server     stato LiteLLM
 *   GET /api/settings   provider, model, MITR path, has_*_key
 *
 * Tutto via TanStack Query con cache breve (10 sec) per evitare di
 * martellare il backend ad ogni focus tab.
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
        <p className="text-sm text-slate-500">
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
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Diagnostica ambiente
        </h2>
        {loading && <span className="text-xs text-slate-400">caricamento…</span>}
      </div>
      <ul className="divide-y divide-slate-100">
        {checks.map((check) => (
          <li
            key={check.name}
            className="flex items-start justify-between gap-3 py-2.5"
          >
            <div className="flex items-start gap-2.5">
              <DoctorIcon status={check.status} />
              <div>
                <div className="text-sm font-medium text-slate-900">
                  {check.name}
                </div>
                <div className="text-xs text-slate-500">{check.message}</div>
              </div>
            </div>
            <StatusPill tone={toneForStatus(check.status)}>
              {check.status}
            </StatusPill>
          </li>
        ))}
        {!loading && checks.length === 0 && (
          <li className="py-3 text-sm text-slate-500">
            Nessun check disponibile.
          </li>
        )}
      </ul>
    </section>
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
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          LiteLLM
        </h2>
        <StatusPill
          tone={
            server?.healthy ? "ok" : server?.running ? "warn" : "fail"
          }
        >
          {server?.healthy
            ? "running & healthy"
            : server?.running
              ? "running, unhealthy"
              : "stopped"}
        </StatusPill>
      </div>
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
          className="inline-flex items-center rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Avvia
        </button>
        <button
          type="button"
          onClick={() => downMutation.mutate()}
          disabled={busy}
          className="inline-flex items-center rounded-md bg-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-300 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Ferma
        </button>
      </div>
      {(upMutation.error || downMutation.error) && (
        <p className="mt-3 text-xs text-rose-600">
          {(upMutation.error ?? downMutation.error)?.message}
        </p>
      )}
    </section>
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
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Azioni rapide
      </h2>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
        {items.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="group flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-left transition hover:bg-white"
          >
            <div>
              <div className="text-sm font-medium text-slate-900">
                {item.title}
              </div>
              <div className="text-xs text-slate-500">{item.description}</div>
            </div>
            <ChevronRight
              size={18}
              className="text-slate-400 transition group-hover:text-slate-600"
            />
          </Link>
        ))}
      </div>
    </section>
  );
}

function DoctorIcon({ status }: { status: string }) {
  if (status === "ok")
    return <CheckCircle2 size={16} className="mt-0.5 text-emerald-600" />;
  if (status === "warn")
    return <CircleAlert size={16} className="mt-0.5 text-amber-600" />;
  if (status === "fail")
    return <CircleX size={16} className="mt-0.5 text-rose-600" />;
  return <CheckCircle2 size={16} className="mt-0.5 text-slate-400" />;
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
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd
        className={`truncate text-sm text-slate-900 ${mono ? "font-mono" : ""}`}
        title={value}
      >
        {value}
      </dd>
    </div>
  );
}
