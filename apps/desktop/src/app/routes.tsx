import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { BatchPlannerPage } from "../pages/BatchPlanner";
import { Dashboard } from "../pages/Dashboard";
import { JobProgressPage } from "../pages/JobProgress";
import { LibraryPage } from "../pages/Library";
import { LogsPage } from "../pages/Logs";
import { NewJobPage } from "../pages/NewJob";
import { SettingsPage } from "../pages/Settings";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "library", element: <LibraryPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "new-job", element: <NewJobPage /> },
      { path: "batch", element: <BatchPlannerPage /> },
      { path: "logs", element: <LogsPage /> },
      { path: "jobs/:id", element: <JobProgressPage /> },
    ],
  },
]);
