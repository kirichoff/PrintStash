"use client";

/**
 * Client-side app shell: decides whether to show the persistent chrome
 * (sidebar, top bar, auth banner) or render the page edge-to-edge.
 *
 * Edge-to-edge routes:
 *   - /setup  (first-run wizard — clean, focused experience)
 *   - /login  (centered sign-in card)
 *
 * Desktop: sidebar + topbar layout (left sidebar, right content area).
 * Mobile:  topbar + bottom nav bar + mobile sidebar drawer.
 */

import { usePathname } from "next/navigation";

import { AuthBanner } from "@/components/auth-banner";
import { BottomNavBar } from "@/components/bottom-nav-bar";
import { SidebarNav } from "@/components/sidebar-nav";
import { Toaster } from "@/components/toaster";
import { TopBar } from "@/components/top-bar";
import { MobileFilterProvider } from "@/lib/mobile-filter-context";

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
        <MobileFilterProvider>
          <div className="flex flex-col min-h-screen">
            <div className="flex flex-1">
              <SidebarNav />
              <div className="md:ml-64 flex flex-col flex-1 min-h-screen max-h-screen w-full">
                <TopBar />
                <AuthBanner />
                <main className="flex-1 min-h-0 overflow-hidden pb-[72px] md:pb-0">
                  {children}
                </main>
              </div>
            </div>
            <BottomNavBar />
          </div>
        </MobileFilterProvider>
      )}
    </>
  );
}
