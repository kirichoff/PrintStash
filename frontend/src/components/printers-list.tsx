"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PrinterRead } from "@/types";
import {
  createPrinter,
  deletePrinter,
  listPrinters,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowRight,
  Plus,
  Printer as PrinterIcon,
  RefreshCw,
  Trash2,
} from "lucide-react";

const STATUS_VARIANT: Record<
  PrinterRead["status"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  ready: "default",
  printing: "default",
  paused: "secondary",
  offline: "outline",
  unknown: "outline",
  error: "destructive",
};

function StatusBadge({ status }: { status: PrinterRead["status"] }) {
  return (
    <Badge variant={STATUS_VARIANT[status]} className="capitalize">
      {status}
    </Badge>
  );
}

export function PrintersPage() {
  const [printers, setPrinters] = useState<PrinterRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      setPrinters(await listPrinters());
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleDelete(p: PrinterRead) {
    if (!confirm(`Remove printer "${p.name}"?`)) return;
    const key = prompt("Enter API key to confirm:");
    if (!key) return;
    try {
      await deletePrinter(p.id, key);
      await refresh();
    } catch (e: any) {
      alert("Delete failed: " + e.message);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Printers</h1>
          <p className="text-muted-foreground">
            Klipper/Moonraker printers connected to the vault.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw className="mr-2 h-4 w-4" /> Refresh
          </Button>
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="mr-2 h-4 w-4" /> Add printer
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : printers.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-muted-foreground">
            <PrinterIcon className="h-10 w-10" />
            <p className="text-sm">No printers configured yet.</p>
            <Button size="sm" onClick={() => setAddOpen(true)}>
              <Plus className="mr-2 h-4 w-4" /> Add your first printer
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {printers.map((p) => (
            <Card key={p.id} className="overflow-hidden">
              <CardHeader className="flex flex-row items-start justify-between gap-2 pb-2">
                <CardTitle className="text-lg leading-tight">{p.name}</CardTitle>
                <StatusBadge status={p.status} />
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="text-xs text-muted-foreground break-all">
                  {p.moonraker_url}
                </div>
                {p.last_error && (
                  <div className="rounded border border-destructive/40 bg-destructive/5 p-2 text-xs text-destructive">
                    {p.last_error}
                  </div>
                )}
                <div className="text-xs text-muted-foreground">
                  {p.last_seen_at
                    ? `Last seen ${new Date(p.last_seen_at).toLocaleString()}`
                    : "Never connected"}
                </div>
                <div className="flex items-center justify-between pt-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(p)}
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="mr-2 h-4 w-4" /> Remove
                  </Button>
                  <Button size="sm" variant="outline" asChild>
                    <Link href={`/printers/${p.id}`}>
                      Open <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <AddPrinterModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onCreated={() => {
          setAddOpen(false);
          refresh();
        }}
      />
    </div>
  );
}

function AddPrinterModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [notes, setNotes] = useState("");
  const [vaultKey, setVaultKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setName("");
      setUrl("");
      setApiKey("");
      setNotes("");
      setVaultKey("");
      setErr(null);
    }
  }, [open]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setErr(null);
    try {
      await createPrinter(
        {
          name: name.trim(),
          moonraker_url: url.trim(),
          api_key: apiKey || undefined,
          notes: notes || undefined,
        },
        vaultKey,
      );
      onCreated();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Add printer">
      <form onSubmit={submit} className="space-y-3">
        <div className="space-y-1">
          <label className="text-sm font-medium">Name</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Voron 2.4"
            required
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">Moonraker URL</label>
          <Input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://voron.local:7125"
            required
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">
            Moonraker API key{" "}
            <span className="text-xs font-normal text-muted-foreground">
              (optional)
            </span>
          </label>
          <Input
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Leave blank if auth is disabled"
            type="password"
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">Notes</label>
          <Input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional"
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">
            Vault API key <Badge variant="destructive">required</Badge>
          </label>
          <Input
            value={vaultKey}
            onChange={(e) => setVaultKey(e.target.value)}
            type="password"
            required
          />
        </div>
        {err && (
          <div className="rounded border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
            {err}
          </div>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={submitting || !name || !url || !vaultKey}>
            {submitting ? "Adding…" : "Add printer"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
