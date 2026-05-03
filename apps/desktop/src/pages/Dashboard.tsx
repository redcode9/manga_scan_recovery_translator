/**
 * Dashboard / Home — la libreria a colpo d'occhio.
 *
 * Composto in tre fasce:
 *  - Setup hero compatto (visibile solo se mancano prerequisiti),
 *  - Libreria: griglia poster delle serie, con scorciatoie per
 *    recuperare i mancanti / continuare con i nuovi.
 *  - Footer "Aggiungi un manga" sempre presente.
 */

import {
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  CircleX,
  KeyRound,
  Plus,
  PlusCircle,
  Power,
  Rocket,
} from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { ServerActionResponse, SettingsView } from "../lib/api";
import { groupBySeries } from "../lib/library-grouping";
import { StatusPill } from "../components/StatusPill";
import { SeriesCard } from "./Library";

const DEFAULT_OUT = "out";

export function Dashboard() {
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const server = useQuery({
    queryKey: ["server-status"],
    queryFn: api.serverStatus,
    refetchInterval: 5_000,
  });
  const library = useQuery({
    queryKey: ["library", DEFAULT_OUT],
    queryFn: () => api.library(DEFAULT_OUT),
  });

  const groups = useMemo(
    () => (library.data ? groupBySeries(library.data.entries) : []),
    [library.data],
  );

  const recent = groups.slice(0, 6);
  const hasLibrary = groups.length > 0;
  const hasMore = groups.length > recent.length;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">La mia libreria</h1>
          <p className="text-sm text-zinc-500">
            {hasLibrary
              ? `${groups.length} ${groups.length === 1 ? "serie" : "serie"} · ${library.data?.entries.length ?? 0} capitoli su disco`
              : "Inizia aggiungendo la tua prima serie."}
          </p>
        </div>
        <Link
          to="/add"
          className="inline-flex min-h-11 items-center gap-2 rounded-md bg-sky-500/90 px-4 py-2 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
        >
          <Plus size={16} aria-hidden="true" />
          Aggiungi manga
        </Link>
      </header>

      {settings.data && (
        <SetupStatusCompact settings={settings.data} server={server.data} />
      )}

      {!hasLibrary && !library.isLoading && <EmptyHero />}

      {hasLibrary && (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {recent.map((group) => (
              <SeriesCard
                key={group.id}
                group={group}
                outDir={DEFAULT_OUT}
                defaultExpanded={false}
              />
            ))}
          </div>
          {hasMore && (
            <div className="flex justify-center">
              <Link
                to="/library"
                className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-zinc-200 transition hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
              >
                Vedi tutte le {groups.length} serie
                <ArrowRight size={14} aria-hidden="true" />
              </Link>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function EmptyHero() {
  return (
    <section className="overflow-hidden rounded-2xl border border-sky-500/20 bg-gradient-to-r from-sky-500/10 via-violet-500/10 to-transparent p-8 text-center">
      <div className="mx-auto max-w-xl space-y-3">
        <Rocket
          className="mx-auto text-sky-300"
          size={32}
          aria-hidden="true"
        />
        <h2 className="text-lg font-semibold text-zinc-100">
          Pronto a tradurre il primo manga?
        </h2>
        <p className="text-sm text-zinc-400">
          Incolla l'URL della serie su MangaDex o MangaFire — ti dirò
          quanti capitoli sono pubblicati e quanti ne hai già su disco,
          e ti aiuterò a recuperare quelli mancanti con un click.
        </p>
        <Link
          to="/add"
          className="mt-2 inline-flex min-h-11 items-center gap-2 rounded-md bg-sky-500/90 px-5 py-2.5 text-sm font-medium text-zinc-950 shadow-sm transition hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
        >
          <PlusCircle size={16} aria-hidden="true" />
          Aggiungi il primo manga
        </Link>
      </div>
    </section>
  );
}

interface SetupStep {
  id: string;
  label: string;
  description: string;
  status: "ok" | "warn" | "fail";
  cta?: { to: string; label: string } | { onClick: () => void; label: string };
}

function SetupStatusCompact({
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
      label: "Chiavi API",
      description: hasAnyKey
        ? "Almeno una chiave configurata."
        : "Serve almeno una chiave per tradurre.",
      status: hasAnyKey ? "ok" : "fail",
      cta: hasAnyKey
        ? undefined
        : { to: "/settings", label: "Configura" },
    },
    {
      id: "litellm",
      label: "Proxy LiteLLM",
      description: server?.healthy
        ? "Attivo."
        : server?.running
          ? "Avviato ma non risponde."
          : "Non in esecuzione.",
      status: server?.healthy ? "ok" : server?.running ? "warn" : "fail",
      cta: server?.healthy
        ? undefined
        : {
            onClick: () => upMutation.mutate(),
            label: upMutation.isPending ? "Avvio…" : "Avvia",
          },
    },
    {
      id: "mitr",
      label: "Motore MITR",
      description: settings.mitr_bin_path
        ? "Configurato."
        : "Non configurato — aggiungi MITR_BIN_PATH al .env.",
      status: settings.mitr_bin_path ? "ok" : "warn",
      cta: settings.mitr_bin_path
        ? undefined
        : { to: "/settings", label: "Verifica" },
    },
  ];
  const allGreen = steps.every((s) => s.status === "ok");
  if (allGreen) return null;

  return (
    <section className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4">
      <header className="mb-3 flex items-center gap-2">
        <KeyRound size={14} className="text-amber-300" aria-hidden="true" />
        <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-amber-200">
          Completa il setup per iniziare
        </h2>
      </header>
      <ol className="grid grid-cols-1 gap-2 md:grid-cols-3">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className="flex items-start gap-2 rounded-xl border border-white/5 bg-white/5 p-3"
          >
            <div className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-zinc-950/60 text-[11px] font-mono text-zinc-400 ring-1 ring-white/10">
              {index + 1}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-medium text-zinc-100">
                  {step.label}
                </span>
                <SetupStepIcon status={step.status} />
              </div>
              <p className="mt-0.5 text-[11px] text-zinc-500">{step.description}</p>
              {step.cta && (
                <div className="mt-2">
                  {"to" in step.cta ? (
                    <Link
                      to={step.cta.to}
                      className="inline-flex items-center gap-1 rounded-md bg-sky-500/90 px-2.5 py-1 text-xs font-medium text-zinc-950 transition hover:bg-sky-400"
                    >
                      {step.cta.label}
                      <ArrowRight size={12} aria-hidden="true" />
                    </Link>
                  ) : (
                    <button
                      type="button"
                      onClick={step.cta.onClick}
                      className="inline-flex items-center gap-1 rounded-md bg-sky-500/90 px-2.5 py-1 text-xs font-medium text-zinc-950 transition hover:bg-sky-400"
                    >
                      <Power size={12} aria-hidden="true" />
                      {step.cta.label}
                    </button>
                  )}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
      {upMutation.error && (
        <p className="mt-2 text-xs text-rose-300">{upMutation.error.message}</p>
      )}
    </section>
  );
}

function SetupStepIcon({ status }: { status: "ok" | "warn" | "fail" }) {
  if (status === "ok")
    return <CheckCircle2 size={12} className="text-emerald-300" aria-hidden="true" />;
  if (status === "warn")
    return <CircleAlert size={12} className="text-amber-300" aria-hidden="true" />;
  return <CircleX size={12} className="text-rose-300" aria-hidden="true" />;
}

// Re-export so the symbol is referenced (kept to maintain a stable
// public surface of this module across refactors).
export const StatusPillRef = StatusPill;
