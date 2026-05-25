"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Box, Printer, Settings, Upload } from "lucide-react";

const mainItems = [
  { href: "/", label: "Vault", icon: Box },
  { href: "/?upload=1", label: "Upload", icon: Upload, match: "/upload" },
  { href: "/printers", label: "Printers", icon: Printer },
];

const bottomItems = [
  { href: "/settings", label: "Settings", icon: Settings },
];

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <nav className="bg-[var(--surface-container-low)] border-r border-[var(--outline-variant)] h-screen w-64 fixed left-0 top-0 flex flex-col py-6 px-4 z-50">
      <div className="flex items-center gap-4 mb-10 px-1">
        <div className="w-10 h-10 rounded bg-[var(--primary-container)] flex items-center justify-center text-[var(--on-primary-container)] flex-shrink-0">
          <Box className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-[var(--primary)] leading-tight">
            Nexus3D
          </h1>
          <p className="text-[11px] text-[var(--on-surface-variant)] font-mono">
            Precision 3D Storage
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-1 flex-1">
        {mainItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/" && !item.match
              : pathname.startsWith(item.match ?? item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-4 px-3 py-2 rounded text-sm font-medium transition-all active:scale-95 ${
                isActive
                  ? "text-[var(--primary)] border-r-[3px] border-[var(--primary)] bg-[var(--secondary-container)]"
                  : "text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-high)]"
              }`}
            >
              <item.icon className="h-5 w-5" />
              <span className="font-mono text-xs tracking-wider uppercase">
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>

      {/* Bottom section */}
      <div className="flex flex-col gap-1">
        {bottomItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-4 px-3 py-2 rounded text-sm font-medium transition-all active:scale-95 ${
                isActive
                  ? "text-[var(--primary)] border-r-[3px] border-[var(--primary)] bg-[var(--secondary-container)]"
                  : "text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-high)]"
              }`}
            >
              <item.icon className="h-5 w-5" />
              <span className="font-mono text-xs tracking-wider uppercase">
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
