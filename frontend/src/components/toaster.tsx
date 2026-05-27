"use client";

import { Toaster as SonnerToaster } from "sonner";

export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      className="!bottom-20 md:!bottom-4 group toast"
      toastOptions={{
        style: {
          fontFamily: "var(--font-mono), monospace",
          fontSize: "13px",
          border: "1px solid var(--outline-variant)",
          background: "var(--surface-container-lowest)",
          color: "var(--on-surface)",
        },
      }}
    />
  );
}
