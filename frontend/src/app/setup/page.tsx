"use client";

/**
 * First-run setup wizard.
 *
 * Two steps:
 *   1. Create the admin account (username, password + confirm, optional email).
 *   2. Confirm storage paths (pre-filled from the backend's current defaults).
 *
 * On submit we POST /api/v1/setup, store the returned JWT, and redirect to `/`.
 * If the install is already configured we redirect to `/login` instead — the
 * wizard is a one-shot endpoint and re-running it is intentionally blocked
 * server-side.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Box,
  ChevronLeft,
  ChevronRight,
  HardDrive,
  Loader2,
  ShieldCheck,
  UserPlus,
} from "lucide-react";

import { completeSetup, getSetupStatus } from "@/lib/api";
import { storeLogin, type StoredUser } from "@/lib/auth";
import type { SetupStatus } from "@/types";

type Step = 1 | 2;

const SETUP_ERROR_MESSAGES: Record<string, string> = {
  already_configured: "This vault has already been set up. Redirecting to sign in.",
  users_already_exist:
    "A user already exists in this vault. Sign in with an existing account instead.",
  invalid_data_dir_path: "The data directory path is not valid.",
  data_dir_not_creatable:
    "The backend could not create the data directory. Check the path and container permissions.",
  data_dir_not_writable:
    "The backend cannot write to the data directory. Check filesystem permissions.",
  invalid_thumb_dir_path: "The thumbnail directory path is not valid.",
  thumb_dir_not_creatable:
    "The backend could not create the thumbnail directory. Check the path and container permissions.",
  thumb_dir_not_writable:
    "The backend cannot write to the thumbnail directory. Check filesystem permissions.",
};

function humanizeError(raw: string): string {
  // api.ts wraps errors as "HTTP <code>: <body>" where the body for FastAPI
  // HTTPException is typically '{"detail":"<code>"}'. Extract the code.
  const match = raw.match(/"detail"\s*:\s*"([^"]+)"/);
  const code = match?.[1];
  if (code && SETUP_ERROR_MESSAGES[code]) return SETUP_ERROR_MESSAGES[code];
  if (code) return code.replace(/_/g, " ");
  return raw;
}

export default function SetupPage() {
  const router = useRouter();

  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);
  const [step, setStep] = useState<Step>(1);

  // Step 1 — account
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  // Step 2 — storage
  const [dataDir, setDataDir] = useState("");
  const [thumbDir, setThumbDir] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSetupStatus()
      .then((s) => {
        if (cancelled) return;
        if (s.configured) {
          router.replace("/login");
          return;
        }
        setStatus(s);
        setDataDir(s.current_data_dir);
        setThumbDir(s.current_thumb_dir);
      })
      .catch((err) => {
        if (cancelled) return;
        setBootError(
          err?.message ??
            "Could not reach the backend. Make sure the API is running.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  function validateStep1(): string | null {
    if (username.trim().length < 3)
      return "Username must be at least 3 characters.";
    if (password.length < 8) return "Password must be at least 8 characters.";
    if (password !== confirm) return "Passwords do not match.";
    if (email && !email.includes("@"))
      return "Email looks invalid (or leave blank).";
    return null;
  }

  function handleNext() {
    const v = validateStep1();
    if (v) {
      setError(v);
      return;
    }
    setError(null);
    setStep(2);
  }

  async function handleSubmit() {
    setError(null);
    setBusy(true);
    try {
      const trimmedData = dataDir.trim();
      const trimmedThumb = thumbDir.trim();
      const res = await completeSetup({
        username: username.trim(),
        password,
        email: email.trim() || undefined,
        // Only send overrides if the user actually changed the value.
        data_dir:
          trimmedData && trimmedData !== status?.current_data_dir
            ? trimmedData
            : undefined,
        thumb_dir:
          trimmedThumb && trimmedThumb !== status?.current_thumb_dir
            ? trimmedThumb
            : undefined,
      });
      const stored: StoredUser = {
        id: res.user_id,
        username: res.username,
        email: email.trim() || null,
        is_superuser: true,
      };
      storeLogin(res.access_token, stored);
      router.replace("/");
    } catch (err: any) {
      setError(humanizeError(err?.message ?? "Setup failed."));
      setBusy(false);
    }
  }

  // ---- Render ---------------------------------------------------------------

  if (bootError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--surface-container-lowest)] px-4">
        <div className="max-w-md w-full bg-[var(--surface-container-low)] border border-[var(--outline-variant)] rounded p-6 space-y-3">
          <h1 className="text-lg font-semibold text-[var(--on-surface)]">
            Cannot reach the vault
          </h1>
          <p className="text-sm text-[var(--on-surface-variant)] font-mono break-words">
            {bootError}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="h-9 px-4 rounded bg-[var(--primary)] text-[var(--primary-foreground)] font-mono text-xs uppercase tracking-wider hover:opacity-90"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--surface-container-lowest)]">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--on-surface-variant)]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--surface-container-lowest)] px-4 py-10">
      <div className="w-full max-w-lg mx-auto space-y-6">
        {/* Header */}
        <div className="text-center">
          <div className="w-14 h-14 mx-auto rounded bg-[var(--primary-container)] flex items-center justify-center text-[var(--on-primary-container)] mb-4">
            <Box className="h-7 w-7" />
          </div>
          <h1 className="text-2xl font-bold text-[var(--on-surface)]">
            Welcome to PrintStash
          </h1>
          <p className="text-sm text-[var(--on-surface-variant)] mt-1">
            Let&apos;s get your self-hosted vault configured.
          </p>
        </div>

        {/* Stepper */}
        <div className="flex items-center justify-center gap-3 text-xs font-mono uppercase tracking-wider">
          <StepIndicator active={step === 1} done={step > 1} label="Account" icon={UserPlus} />
          <div className="h-px w-10 bg-[var(--outline-variant)]" />
          <StepIndicator active={step === 2} done={false} label="Storage" icon={HardDrive} />
        </div>

        {/* Card */}
        <div className="bg-[var(--surface-container-low)] border border-[var(--outline-variant)] rounded p-6 space-y-4">
          {step === 1 ? (
            <AccountStep
              username={username}
              setUsername={setUsername}
              email={email}
              setEmail={setEmail}
              password={password}
              setPassword={setPassword}
              confirm={confirm}
              setConfirm={setConfirm}
            />
          ) : (
            <StorageStep
              dataDir={dataDir}
              setDataDir={setDataDir}
              thumbDir={thumbDir}
              setThumbDir={setThumbDir}
              defaultDataDir={status.default_data_dir}
              defaultThumbDir={status.default_thumb_dir}
            />
          )}

          {error && (
            <div className="text-xs text-[var(--error)] font-mono">{error}</div>
          )}

          <div className="flex items-center justify-between gap-2 pt-2">
            {step === 2 ? (
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  setStep(1);
                }}
                disabled={busy}
                className="h-10 px-4 rounded border border-[var(--outline-variant)] text-[var(--on-surface-variant)] font-mono text-xs uppercase tracking-wider hover:bg-[var(--surface-container)] disabled:opacity-50 flex items-center gap-1.5"
              >
                <ChevronLeft className="h-4 w-4" />
                Back
              </button>
            ) : (
              <span />
            )}

            {step === 1 ? (
              <button
                type="button"
                onClick={handleNext}
                className="h-10 px-4 rounded bg-[var(--primary)] text-[var(--primary-foreground)] font-mono text-xs uppercase tracking-wider hover:opacity-90 flex items-center gap-1.5"
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={busy}
                className="h-10 px-4 rounded bg-[var(--primary)] text-[var(--primary-foreground)] font-mono text-xs uppercase tracking-wider hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
              >
                {busy ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ShieldCheck className="h-4 w-4" />
                )}
                Complete setup
              </button>
            )}
          </div>
        </div>

        <p className="text-center text-xs text-[var(--on-surface-variant)] font-mono">
          This wizard only runs once. Subsequent admins can be added later.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step components
// ---------------------------------------------------------------------------

function AccountStep(props: {
  username: string;
  setUsername: (v: string) => void;
  email: string;
  setEmail: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  confirm: string;
  setConfirm: (v: string) => void;
}) {
  return (
    <>
      <p className="text-sm text-[var(--on-surface-variant)]">
        Create the first administrator account. You can add more users later.
      </p>
      <Field
        label="Username"
        id="setup-username"
        value={props.username}
        onChange={props.setUsername}
        autoFocus
        autoComplete="username"
        required
      />
      <Field
        label="Email (optional)"
        id="setup-email"
        value={props.email}
        onChange={props.setEmail}
        autoComplete="email"
        type="email"
      />
      <Field
        label="Password"
        id="setup-password"
        value={props.password}
        onChange={props.setPassword}
        type="password"
        autoComplete="new-password"
        required
        hint="Minimum 8 characters."
      />
      <Field
        label="Confirm password"
        id="setup-confirm"
        value={props.confirm}
        onChange={props.setConfirm}
        type="password"
        autoComplete="new-password"
        required
      />
    </>
  );
}

function StorageStep(props: {
  dataDir: string;
  setDataDir: (v: string) => void;
  thumbDir: string;
  setThumbDir: (v: string) => void;
  defaultDataDir: string;
  defaultThumbDir: string;
}) {
  return (
    <>
      <p className="text-sm text-[var(--on-surface-variant)]">
        Confirm where the vault should store ingested files and generated
        thumbnails. These paths are inside the backend container — make sure
        they live on a persistent Docker volume.
      </p>
      <Field
        label="Data directory"
        id="setup-data-dir"
        value={props.dataDir}
        onChange={props.setDataDir}
        required
        hint={`Default: ${props.defaultDataDir}`}
        mono
      />
      <Field
        label="Thumbnail directory"
        id="setup-thumb-dir"
        value={props.thumbDir}
        onChange={props.setThumbDir}
        required
        hint={`Default: ${props.defaultThumbDir}`}
        mono
      />
      <div className="text-xs text-[var(--on-surface-variant)] font-mono bg-[var(--surface-container-lowest)] border border-[var(--outline-variant)] rounded p-3">
        The backend will attempt to create these directories and probe them
        for writability before completing setup.
      </div>
    </>
  );
}

function Field(props: {
  label: string;
  id: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  autoFocus?: boolean;
  autoComplete?: string;
  required?: boolean;
  hint?: string;
  mono?: boolean;
}) {
  return (
    <div>
      <label
        htmlFor={props.id}
        className="block text-xs font-mono uppercase tracking-wider text-[var(--on-surface-variant)] mb-1.5"
      >
        {props.label}
      </label>
      <input
        id={props.id}
        type={props.type ?? "text"}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        autoComplete={props.autoComplete}
        autoFocus={props.autoFocus}
        required={props.required}
        className={`w-full h-10 bg-[var(--surface-container-lowest)] text-[var(--on-surface)] ${
          props.mono ? "font-mono" : ""
        } text-sm border border-[var(--outline-variant)] rounded px-3 focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent`}
      />
      {props.hint && (
        <p className="text-[10px] text-[var(--on-surface-variant)] font-mono mt-1">
          {props.hint}
        </p>
      )}
    </div>
  );
}

function StepIndicator(props: {
  active: boolean;
  done: boolean;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  const Icon = props.icon;
  const tone = props.done
    ? "bg-[var(--primary)] text-[var(--primary-foreground)] border-transparent"
    : props.active
      ? "bg-[var(--primary-container)] text-[var(--on-primary-container)] border-[var(--primary)]"
      : "bg-transparent text-[var(--on-surface-variant)] border-[var(--outline-variant)]";
  return (
    <div className={`flex items-center gap-1.5 px-2.5 h-7 rounded border ${tone}`}>
      <Icon className="h-3.5 w-3.5" />
      <span>{props.label}</span>
    </div>
  );
}
