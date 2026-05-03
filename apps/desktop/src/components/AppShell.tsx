/**
 * AppShell — chrome of the dark-themed UI.
 *
 * The shell is the only place that knows about navigation and the
 * active job banner: pages render via ``<Outlet />`` and never have
 * to think about whether a batch is in flight, because the banner
 * follows the user across every route.
 */

import {
  Activity,
  BookOpenText,
  FileSearch,
  Gauge,
  KeyRound,
  Layers,
  Library,
  ScrollText,
  Settings,
} from "lucide-react";
import type { ReactNode } from "react";
import { Link, NavLink, Outlet, useNavigation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { Job } from "../lib/api";
import { StatusPill } from "./StatusPill";

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: <Gauge size={18} /> },
  { to: "/new-job", label: "Nuovo Job", icon: <FileSearch size={18} /> },
  { to: "/batch", label: "Batch", icon: <Layers size={18} /> },
  { to: "/library", label: "Libreria", icon: <Library size={18} /> },
  { to: "/setup", label: "Setup", icon: <KeyRound size={18} /> },
  { to: "/settings", label: "Impostazioni", icon: <Settings size={18} /> },
  { to: "/logs", label: "Log", icon: <ScrollText size={18} /> },
];

const ACTIVE_STATUSES = new Set<Job["status"]>(["queued", "running"]);

export function AppShell() {
  const navigation = useNavigation();
  // Poll the jobs list every 4s so the active-batch banner reflects
  // reality without forcing the user to open JobProgress.
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: api.jobs,
    refetchInterval: 4_000,
  });
  const activeJob = jobs.data?.jobs.find((job) => ACTIVE_STATUSES.has(job.status));

  return (
    <div className="flex w-full bg-zinc-950 text-zinc-100">
      <aside className="w-60 shrink-0 border-r border-white/5 bg-zinc-950/60 backdrop-blur-sm">
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-sky-500/15 ring-1 ring-sky-400/30">
            <BookOpenText className="text-sky-300" size={18} />
          </div>
          <div>
            <div className="text-base font-semibold tracking-tight">msrt</div>
            <div className="text-[11px] text-zinc-500">manga translator</div>
          </div>
        </div>
        <nav className="flex flex-col gap-0.5 px-2">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-white/5 text-zinc-100"
                    : "text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
                }`
              }
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="flex flex-1 flex-col">
        <Header navigating={navigation.state !== "idle"} activeJob={activeJob} />
        <div className="flex-1 overflow-y-auto px-8 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

function Header({
  navigating,
  activeJob,
}: {
  navigating: boolean;
  activeJob: Job | undefined;
}) {
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const server = useQuery({
    queryKey: ["server-status"],
    queryFn: api.serverStatus,
    refetchInterval: 5_000,
  });

  const litellmTone: "ok" | "warn" | "fail" = server.data?.healthy
    ? "ok"
    : server.data?.running
      ? "warn"
      : "fail";

  return (
    <header className="border-b border-white/5 bg-zinc-950/80 backdrop-blur">
      <div className="flex items-center justify-between px-8 py-3">
        <div className="text-sm text-zinc-500">
          {navigating ? "Caricamento…" : "Pronto"}
        </div>
        <div className="flex items-center gap-2">
          <StatusPill tone={litellmTone}>
            <span className={`inline-block h-1.5 w-1.5 rounded-full bg-current ${litellmTone === "ok" ? "msrt-pulse" : ""}`} />
            LiteLLM:{" "}
            {server.data
              ? server.data.healthy
                ? "running"
                : server.data.running
                  ? "unhealthy"
                  : "stopped"
              : "?"}
          </StatusPill>
          <StatusPill tone={settings.data?.mitr_bin_path ? "ok" : "warn"}>
            MITR: {settings.data?.mitr_bin_path ? "configurato" : "mancante"}
          </StatusPill>
          <StatusPill tone="info">
            model: {settings.data?.default_model ?? "?"}
          </StatusPill>
        </div>
      </div>
      {activeJob && <ActiveJobBanner job={activeJob} />}
    </header>
  );
}

function ActiveJobBanner({ job }: { job: Job }) {
  const total = job.chapters_total || 1;
  const done = job.chapters_done;
  const failed = job.chapters_failed;
  const pct = Math.min(100, Math.round((done / total) * 100));
  const isBatch = job.kind === "url_batch";
  const label = isBatch
    ? `Batch in corso · ${done}/${total} capitoli`
    : `Job in corso · fase ${job.current_phase}`;

  return (
    <Link
      to={`/jobs/${job.id}`}
      className="block border-t border-white/5 bg-gradient-to-r from-sky-500/10 via-zinc-900/40 to-transparent transition hover:from-sky-500/20"
    >
      <div className="flex items-center gap-4 px-8 py-2.5">
        <span className="flex items-center gap-2 text-xs font-medium text-sky-200">
          <span className="msrt-pulse inline-block h-2 w-2 rounded-full bg-sky-400" />
          <Activity size={14} />
          {label}
        </span>
        <div className="flex-1">
          <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
            <div
              className="h-full rounded-full bg-sky-400 transition-[width] duration-500 ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
        <span className="font-mono text-xs text-zinc-400">
          {pct}% {failed > 0 && <span className="text-rose-300">· {failed} falliti</span>}
        </span>
        <span className="text-xs text-zinc-500">apri →</span>
      </div>
    </Link>
  );
}
