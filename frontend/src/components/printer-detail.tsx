"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  PrintJobRead,
  PrinterRead,
  PrinterSnapshot,
  PrinterStatus,
} from "@/types";
import {
  cancelPrinter,
  getPrinter,
  listPrinterJobs,
  openPrinterWS,
  pausePrinter,
  resumePrinter,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  Pause,
  Play,
  Square,
  Thermometer,
  Wifi,
  WifiOff,
} from "lucide-react";

const STATUS_VARIANT: Record<
  PrinterStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  ready: "default",
  printing: "default",
  paused: "secondary",
  offline: "outline",
  unknown: "outline",
  error: "destructive",
};

function formatDuration(s?: number | null): string {
  if (!s || s <= 0) return "—";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${sec}s`;
  return `${sec}s`;
}

function deepMerge<T extends Record<string, any>>(a: T, b: Partial<T>): T {
  const out: any = { ...a };
  for (const k of Object.keys(b)) {
    const av = (a as any)[k];
    const bv = (b as any)[k];
    if (
      av &&
      bv &&
      typeof av === "object" &&
      typeof bv === "object" &&
      !Array.isArray(av) &&
      !Array.isArray(bv)
    ) {
      out[k] = deepMerge(av, bv);
    } else {
      out[k] = bv;
    }
  }
  return out;
}

export function PrinterDetailPage({ printerId }: { printerId: number }) {
  const [printer, setPrinter] = useState<PrinterRead | null>(null);
  const [snapshot, setSnapshot] = useState<PrinterSnapshot>({});
  const [jobs, setJobs] = useState<PrintJobRead[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function loadJobs() {
    try {
      setJobs(await listPrinterJobs(printerId));
    } catch (e: any) {
      // non-fatal
      console.warn("Failed to load jobs:", e);
    }
  }

  async function loadPrinter() {
    try {
      setPrinter(await getPrinter(printerId));
    } catch (e: any) {
      setError(e.message);
    }
  }

  function connect() {
    try {
      const ws = openPrinterWS(printerId);
      wsRef.current = ws;
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => {
        setWsConnected(false);
        if (reconnectRef.current) clearTimeout(reconnectRef.current);
        reconnectRef.current = setTimeout(connect, 3000);
      };
      ws.onerror = () => {
        // onclose will follow.
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "snapshot") {
            setSnapshot(msg.data || {});
          } else if (msg.type === "update") {
            setSnapshot((prev) => deepMerge(prev, msg.data || {}));
          }
          // Refresh job list when print state changes are observed.
          const state = msg?.data?.print_stats?.state;
          if (state) loadJobs();
        } catch {
          /* ignore parse errors */
        }
      };
    } catch (e: any) {
      setError(`WS error: ${e.message}`);
    }
  }

  useEffect(() => {
    loadPrinter();
    loadJobs();
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [printerId]);

  async function control(
    fn: (key: string) => Promise<void>,
    label: string,
  ) {
    const key = prompt(`Enter API key to ${label}:`);
    if (!key) return;
    try {
      await fn(key);
    } catch (e: any) {
      alert(`${label} failed: ${e.message}`);
    }
  }

  const ps = snapshot.print_stats || {};
  const vs = snapshot.virtual_sdcard || {};
  const ext = snapshot.extruder || {};
  const bed = snapshot.heater_bed || {};
  const progress = typeof vs.progress === "number" ? vs.progress * 100 : null;

  if (!printer) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/printers">
            <ArrowLeft className="mr-2 h-4 w-4" /> Printers
          </Link>
        </Button>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {wsConnected ? (
            <>
              <Wifi className="h-3.5 w-3.5 text-emerald-500" /> Live
            </>
          ) : (
            <>
              <WifiOff className="h-3.5 w-3.5 text-amber-500" /> Reconnecting…
            </>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold tracking-tight">{printer.name}</h1>
        <Badge variant={STATUS_VARIANT[printer.status]} className="capitalize">
          {printer.status}
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground break-all">
        {printer.moonraker_url}
      </p>

      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">Current print</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">File</span>
              <span className="ml-auto truncate font-medium">
                {ps.filename || "—"}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">State</span>
              <span className="ml-auto font-medium capitalize">
                {ps.state || "—"}
              </span>
            </div>
            <div>
              <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                <span>Progress</span>
                <span>{progress != null ? `${progress.toFixed(1)}%` : "—"}</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded bg-muted">
                <div
                  className="h-full bg-primary transition-all"
                  style={{ width: `${Math.min(100, progress ?? 0)}%` }}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="text-xs text-muted-foreground">Elapsed</div>
                <div className="font-medium">
                  {formatDuration(ps.print_duration)}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Total</div>
                <div className="font-medium">
                  {formatDuration(ps.total_duration)}
                </div>
              </div>
            </div>

            <Separator />

            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  control((k) => pausePrinter(printerId, k), "pause")
                }
                disabled={ps.state !== "printing"}
              >
                <Pause className="mr-2 h-4 w-4" /> Pause
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  control((k) => resumePrinter(printerId, k), "resume")
                }
                disabled={ps.state !== "paused"}
              >
                <Play className="mr-2 h-4 w-4" /> Resume
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() =>
                  control((k) => cancelPrinter(printerId, k), "cancel")
                }
                disabled={ps.state !== "printing" && ps.state !== "paused"}
              >
                <Square className="mr-2 h-4 w-4" /> Cancel
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Controls will prompt for the vault API key.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Thermometer className="h-4 w-4" /> Temperatures
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <TempRow label="Hotend" cur={ext.temperature} tgt={ext.target} />
            <TempRow label="Bed" cur={bed.temperature} tgt={bed.target} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Print history</CardTitle>
        </CardHeader>
        <CardContent>
          {jobs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No print jobs yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3">When</th>
                    <th className="py-2 pr-3">File</th>
                    <th className="py-2 pr-3">State</th>
                    <th className="py-2 pr-3">Progress</th>
                    <th className="py-2 pr-3">Started</th>
                    <th className="py-2 pr-3">Finished</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((j) => (
                    <tr key={j.id} className="border-t">
                      <td className="py-2 pr-3 text-xs text-muted-foreground">
                        {new Date(j.created_at).toLocaleString()}
                      </td>
                      <td className="py-2 pr-3 max-w-[260px] truncate">
                        <Link
                          href={`/models/${j.model_id}`}
                          className="hover:underline"
                          title={j.remote_filename}
                        >
                          {j.remote_filename}
                        </Link>
                      </td>
                      <td className="py-2 pr-3 capitalize">{j.state}</td>
                      <td className="py-2 pr-3">
                        {(j.progress * 100).toFixed(0)}%
                      </td>
                      <td className="py-2 pr-3 text-xs text-muted-foreground">
                        {j.started_at
                          ? new Date(j.started_at).toLocaleTimeString()
                          : "—"}
                      </td>
                      <td className="py-2 pr-3 text-xs text-muted-foreground">
                        {j.finished_at
                          ? new Date(j.finished_at).toLocaleTimeString()
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function TempRow({
  label,
  cur,
  tgt,
}: {
  label: string;
  cur?: number;
  tgt?: number;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">
          {cur != null ? cur.toFixed(1) : "—"}°C
          {tgt != null && tgt > 0 && (
            <span className="ml-1 text-xs text-muted-foreground">
              / {tgt.toFixed(0)}°C
            </span>
          )}
        </span>
      </div>
      {tgt != null && tgt > 0 && cur != null && (
        <div className="h-1 w-full overflow-hidden rounded bg-muted">
          <div
            className="h-full bg-orange-500 transition-all"
            style={{
              width: `${Math.min(100, Math.max(0, (cur / tgt) * 100))}%`,
            }}
          />
        </div>
      )}
    </div>
  );
}
