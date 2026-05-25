"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, X } from "lucide-react";
import { hasStoredApiKey, onAuthChange, onUnauthorized } from "@/lib/auth";

export function AuthBanner() {
  const [show, setShow] = useState(false);
  const [reason, setReason] = useState<"missing" | "rejected">("missing");

  useEffect(() => {
    function update() {
      // Only surface the missing-key banner if a previous 401 / explicit action
      // flagged it. We don't want to nag on first visit before any write.
    }
    const offAuth = onAuthChange(update);
    const offUnauth = onUnauthorized(() => {
      setReason(hasStoredApiKey() ? "rejected" : "missing");
      setShow(true);
    });
    return () => {
      offAuth();
      offUnauth();
    };
  }, []);

  if (!show) return null;

  return (
    <div className="bg-amber-500/10 border-b border-amber-500/30 px-6 py-2 flex items-center gap-3 text-xs font-mono text-amber-800 dark:text-amber-200">
      <AlertTriangle className="h-4 w-4 flex-shrink-0" />
      <span className="flex-1">
        {reason === "rejected"
          ? "Server rejected the stored API key. Update it in Settings."
          : "An action requires the vault API key. Add it in Settings to continue."}
      </span>
      <Link
        href="/settings"
        className="uppercase tracking-wider underline hover:no-underline"
        onClick={() => setShow(false)}
      >
        Open settings
      </Link>
      <button
        type="button"
        onClick={() => setShow(false)}
        className="p-1 rounded hover:bg-amber-500/20 transition-colors"
        aria-label="Dismiss"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
