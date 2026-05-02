/**
 * AppShell is the only place that knows about the navigation chrome.
 * Pages render via ``<Outlet />``; the shell paints the sidebar and a
 * header that surfaces backend status (LiteLLM up?, MITR ok?) so the
 * user can see at a glance whether they need to fix something before
 * starting a job.
 */

import {
  BookOpenText,
  FileSearch,
  Gauge,
  Layers,
  Library,
  ScrollText,
  Settings,
} from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, Outlet, useNavigation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "../lib/api";
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
  { to: "/settings", label: "Impostazioni", icon: <Settings size={18} /> },
  { to: "/logs", label: "Log", icon: <ScrollText size={18} /> },
];

export function AppShell() {
  const navigation = useNavigation();

  return (
    <div className="flex w-full">
      <aside className="w-56 shrink-0 border-r border-slate-200 bg-white">
        <div className="flex items-center gap-2 px-5 py-5">
          <BookOpenText className="text-sky-600" size={22} />
          <div>
            <div className="text-base font-semibold tracking-tight">msrt</div>
            <div className="text-[11px] text-slate-500">
              manga translator UI
            </div>
          </div>
        </div>
        <nav className="flex flex-col gap-0.5 px-2">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-sky-50 text-sky-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
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
        <Header navigating={navigation.state !== "idle"} />
        <div className="flex-1 overflow-y-auto px-8 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

function Header({ navigating }: { navigating: boolean }) {
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const server = useQuery({
    queryKey: ["server-status"],
    queryFn: api.serverStatus,
    refetchInterval: 5_000,
  });

  const litellmTone = server.data?.healthy
    ? "ok"
    : server.data?.running
      ? "warn"
      : "fail";

  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-8 py-3">
      <div className="text-sm text-slate-500">
        {navigating ? "Caricamento…" : "Pronto"}
      </div>
      <div className="flex items-center gap-2">
        <StatusPill tone={litellmTone}>
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
    </header>
  );
}
