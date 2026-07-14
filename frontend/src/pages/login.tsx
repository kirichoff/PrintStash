"use client";

import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useRouter } from "@/lib/navigation";
import { AlertCircle, Clock3, ShieldCheck } from "lucide-react";
import { BrandMark } from "@/components/brand-mark";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth-context";
import { ThemeToggle } from "@/components/theme-toggle";
import { consumeSessionExpired } from "@/lib/auth";

export default function LoginPage() {
  const { login, user } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [remember_me, setremember_me] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sessionExpired] = useState(consumeSessionExpired);

  if (user) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username, password, remember_me);
      router.replace("/");
    } catch (err: any) {
      if (err.message?.includes("401")) {
        setError("Invalid username or password.");
      } else {
        setError(err.message || "Login failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-12">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 h-80 w-80 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/5 blur-3xl"
      />

      <div className="absolute right-5 top-5">
        <ThemeToggle />
      </div>

      <div className="relative mx-auto w-full max-w-md">
        <Card className="border-outline-variant bg-surface-container-low shadow-lg">
          <CardHeader className="items-center px-6 pb-5 pt-8 text-center sm:px-8">
            <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
              <BrandMark className="h-9 w-9" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-on-surface">
              Welcome back
            </h1>
            <CardDescription className="text-on-surface-variant">
              Sign in to manage your PrintStash vault.
            </CardDescription>
          </CardHeader>

          <CardContent className="px-6 pb-8 sm:px-8">
            <form onSubmit={handleSubmit} className="space-y-5">
              {sessionExpired && (
                <div
                  role="status"
                  className="flex gap-2.5 rounded-md border border-warning/30 bg-warning/10 px-3 py-2.5 text-sm text-on-surface"
                >
                  <Clock3 className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
                  <p>Session expired. Sign in again to continue.</p>
                </div>
              )}

              <div className="space-y-2">
                <label
                  htmlFor="username"
                  className="block text-xs font-mono uppercase tracking-wider text-on-surface-variant"
                >
                  Username
                </label>
                <Input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  aria-invalid={!!error}
                  aria-describedby={error ? "login-error" : undefined}
                  autoComplete="username"
                  autoFocus
                  required
                  className="bg-surface-container-lowest font-mono text-on-surface"
                />
              </div>

              <div className="space-y-2">
                <label
                  htmlFor="password"
                  className="block text-xs font-mono uppercase tracking-wider text-on-surface-variant"
                >
                  Password
                </label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  aria-invalid={!!error}
                  aria-describedby={error ? "login-error" : undefined}
                  autoComplete="current-password"
                  required
                  className="bg-surface-container-lowest font-mono text-on-surface"
                />
              </div>

              <div className="flex items-center gap-2.5">
                <Checkbox
                  checked={remember_me}
                  onChange={setremember_me}
                  ariaLabel="Remember me"
                />
                <span className="text-sm text-on-surface-variant">Remember me on this device</span>
              </div>

              {error && (
                <div
                  id="login-error"
                  role="alert"
                  className="flex gap-2.5 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-sm text-destructive"
                >
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                  <p>{error}</p>
                </div>
              )}

              <Button type="submit" loading={busy} className="w-full">
                Sign in
              </Button>
            </form>

            <div className="mt-6 flex items-center justify-center gap-2 border-t border-outline-variant pt-5 text-xs text-on-surface-variant">
              <ShieldCheck className="h-4 w-4 text-primary" aria-hidden />
              <span>Your credentials stay with your self-hosted server.</span>
            </div>
          </CardContent>
        </Card>

        <p className="mt-5 text-center font-mono text-2xs uppercase tracking-wider text-muted-foreground">
          PrintStash · Your prints, your vault
        </p>
      </div>
    </main>
  );
}
