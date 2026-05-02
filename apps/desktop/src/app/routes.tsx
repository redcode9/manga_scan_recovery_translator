import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { Dashboard } from "../pages/Dashboard";
import { LibraryPage } from "../pages/Library";
import { SettingsPage } from "../pages/Settings";
import { StubPage } from "../pages/StubPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "library", element: <LibraryPage /> },
      { path: "settings", element: <SettingsPage /> },
      {
        path: "new-job",
        element: (
          <StubPage
            title="Nuovo Job"
            description="Form locale/URL con scelta provider, formato, postprocess."
            milestone="v0.4b"
          />
        ),
      },
      {
        path: "batch",
        element: (
          <StubPage
            title="Batch"
            description="Dry-run capitoli da URL serie + planner per --range/--chapters/--limit."
            milestone="v0.4b"
          />
        ),
      },
      {
        path: "logs",
        element: (
          <StubPage
            title="Log"
            description="Tail in tempo reale dei log backend, filtrabili per livello."
            milestone="v0.4e"
          />
        ),
      },
    ],
  },
]);
