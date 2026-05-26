"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, X } from "lucide-react";
import {
  hasStoredApiKey,
  isLoggedIn,
  onAuthChange,
  onUnauthorized,
} from "@/lib/auth";

export function AuthBanner() {
  const [show, setShow] = useState(false);
  const [reason, setReason] = useState<"missing" | "rejected" | "expired">(
    "missing",
  );

  useEffect(() => {
    function update() {
      if (show && isLoggedIn()) {
        setShow(false);
      }
    }
    const offAuth = onAuthChange(update);
    const offUnauth = onUnauthorized(() => {
      if (isLoggedIn()) {
        setReason("expired");
      } else if (hasStoredApiKey()) {
        setReason("rejected");
      } else {
        setReason("missing");
      }
      setShow(true);
    });
    return () => {
      offAuth();
      offUnauth();
    };
  }, [show]);

  if (!show) return null;

  const messages: Record<string, string> = {
    missing:
      "An action requires authentication. Sign in or add an API key in Settings.",
    rejected:
      "Server rejected the stored credentials. Sign in or update your API key in Settings.",
    expired:
      "Your session has expired. Please sign in again.",
  };

  return (
    <div className="bg-amber-500/10 border-b border-amber-500/30 px-6 py-2 flex items-center gap-3 text-xs font-mono text-amber-800 dark:text-amber-200">
      <AlertTriangle className="h-4 w-4 flex-shrink-0" />
      <span className="flex-1">{messages[reason]}</span>
      {!isLoggedIn() && (
        <Link
          href="/login"
          className="uppercase tracking-wider underline hover:no-underline"
          onClick={() => setShow(false)}
        >
          Sign in
        </Link>
      )}
      <Link
        href="/settings"
        className="uppercase tracking-wider underline hover:no-underline"
        onClick={() => setShow(false)}
      >
        Settings
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
