"use client";

import { Suspense } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Bell, HelpCircle, Search } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";

function TopBarSearch() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const q = searchParams.get("q") ?? "";

  function setSearch(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value.trim()) {
      params.set("q", value.trim());
    } else {
      params.delete("q");
    }
    router.replace(`/?${params.toString()}`, { scroll: false });
  }

  if (pathname !== "/") return <span className="flex-1" />;

  return (
    <div className="flex-1 flex justify-center">
      <div className="relative w-full max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--on-surface-variant)]" />
        <input
          className="w-full h-9 bg-[var(--surface-container-lowest)] text-[var(--on-surface)] font-mono text-sm border border-[var(--outline-variant)] rounded pl-10 pr-4 focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent transition-shadow placeholder:text-[var(--on-surface-variant)]/50"
          placeholder="Search models..."
          type="text"
          value={q}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
    </div>
  );
}

export function TopBar() {
  return (
    <header className="bg-[var(--surface-container-lowest)] h-16 sticky top-0 z-40 border-b border-[var(--outline-variant)] flex items-center px-4 md:px-6 w-full gap-2 md:gap-4">
      <span className="md:hidden font-headline-sm text-[18px] font-bold text-[var(--primary)] tracking-tight">
        PrintStash
      </span>

      <Suspense fallback={<span className="flex-1" />}>
        <TopBarSearch />
      </Suspense>

      <div className="flex items-center gap-2 md:gap-3">
        <ThemeToggle />
        <button className="text-[var(--on-surface-variant)] hover:text-[var(--primary)] transition-colors rounded p-1 hidden sm:block">
          <Bell className="h-5 w-5" />
        </button>
        <button className="text-[var(--on-surface-variant)] hover:text-[var(--primary)] transition-colors rounded p-1 hidden sm:block">
          <HelpCircle className="h-5 w-5" />
        </button>
      </div>
    </header>
  );
}
