"use client";

/**
 * Client-side app shell: decides whether to show the persistent chrome
 * (sidebar, top bar, auth banner) or render the page edge-to-edge.
 *
 * Edge-to-edge routes:
 *   - /setup  (first-run wizard — clean, focused experience)
 *   - /login  (centered sign-in card)
 *
 * Everything else gets the sidebar + topbar layout.
 */

import { usePathname } from "next/navigation";

import { AuthBanner } from "@/components/auth-banner";
import { SidebarNav } from "@/components/sidebar-nav";
import { Toaster } from "@/components/toaster";
import { TopBar } from "@/components/top-bar";

const CHROMELESS_PREFIXES = ["/setup", "/login"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const chromeless = CHROMELESS_PREFIXES.some((p) => pathname.startsWith(p));

  return (
    <>
      <Toaster />
      {chromeless ? (
        children
      ) : (
        <div className="flex">
          <SidebarNav />
          <div className="ml-64 flex flex-col flex-1 min-h-screen max-h-screen">
            <TopBar />
            <AuthBanner />
            <main className="flex-1 min-h-0 overflow-hidden">{children}</main>
          </div>
        </div>
      )}
    </>
  );
}
