/* eslint-disable react-refresh/only-export-components */
import { createBrowserRouter } from "react-router-dom";
import { Suspense, lazy } from "react";

import RootLayout from "@/root-layout";

const HomePage = lazy(() => import("@/pages/home"));
const ModelDetailPage = lazy(() => import("@/pages/model-detail"));
const LoginPage = lazy(() => import("@/pages/login"));
const SetupPage = lazy(() => import("@/pages/setup"));
const OrganizePage = lazy(() => import("@/pages/organize"));
const ProfilesPage = lazy(() => import("@/pages/profiles"));
const StatisticsPage = lazy(() => import("@/pages/statistics"));
const SettingsPage = lazy(() => import("@/pages/settings"));
const PrintersRoute = lazy(() => import("@/pages/printers"));
const PrinterDetailRoute = lazy(() => import("@/pages/printer-detail"));
const SharePage = lazy(() => import("@/pages/share"));
const NotFound = lazy(() => import("@/pages/not-found"));

function RouteChunk({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen w-full bg-background" aria-busy="true" />
      }
    >
      {children}
    </Suspense>
  );
}

export const router = createBrowserRouter([
  // Public, unauthenticated share viewer — deliberately mounted OUTSIDE
  // RootLayout so it bypasses auth/setup gating and the app chrome.
  { path: "share/:token", element: <RouteChunk><SharePage /></RouteChunk> },
  {
    element: <RootLayout />,
    children: [
      { index: true, element: <RouteChunk><HomePage /></RouteChunk> },
      { path: "models/:id", element: <RouteChunk><ModelDetailPage /></RouteChunk> },
      { path: "login", element: <RouteChunk><LoginPage /></RouteChunk> },
      { path: "setup", element: <RouteChunk><SetupPage /></RouteChunk> },
      { path: "organize", element: <RouteChunk><OrganizePage /></RouteChunk> },
      { path: "profiles", element: <RouteChunk><ProfilesPage /></RouteChunk> },
      { path: "statistics", element: <RouteChunk><StatisticsPage /></RouteChunk> },
      { path: "settings", element: <RouteChunk><SettingsPage /></RouteChunk> },
      { path: "printers", element: <RouteChunk><PrintersRoute /></RouteChunk> },
      { path: "printers/:id", element: <RouteChunk><PrinterDetailRoute /></RouteChunk> },
      { path: "*", element: <RouteChunk><NotFound /></RouteChunk> },
    ],
  },
]);
