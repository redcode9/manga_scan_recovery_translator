import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { AddPage } from "../pages/Add";
import { Dashboard } from "../pages/Dashboard";
import { JobProgressPage } from "../pages/JobProgress";
import { LibraryPage } from "../pages/Library";
import { LogsPage } from "../pages/Logs";
import { SettingsPage } from "../pages/Settings";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "library", element: <LibraryPage /> },
      { path: "add", element: <AddPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "logs", element: <LogsPage /> },
      { path: "jobs/:id", element: <JobProgressPage /> },
      // Legacy redirects: keep deep links / bookmarks working after
      // the v0.6 page consolidation.
      { path: "new-job", element: <Navigate to="/add" replace /> },
      { path: "batch", element: <Navigate to="/add" replace /> },
      { path: "setup", element: <Navigate to="/settings" replace /> },
    ],
  },
]);
