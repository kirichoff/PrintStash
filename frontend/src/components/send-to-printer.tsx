"use client";

import { useEffect, useState } from "react";
import { FileRead, PrinterRead } from "@/types";
import { listPrinters, sendToPrinter } from "@/lib/api";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Printer, Send } from "lucide-react";

export function SendToPrinterButton({ files }: { files: FileRead[] }) {
  const [open, setOpen] = useState(false);
  const gcodeFiles = files.filter((f) => f.file_type === "gcode");
  if (gcodeFiles.length === 0) return null;

  return (
    <>
      <Button
        variant="default"
        size="sm"
        onClick={() => setOpen(true)}
      >
        <Send className="mr-2 h-4 w-4" /> Send to printer
      </Button>
      <SendDialog
        open={open}
        onClose={() => setOpen(false)}
        files={gcodeFiles}
      />
    </>
  );
}

function SendDialog({
  open,
  onClose,
  files,
}: {
  open: boolean;
  onClose: () => void;
  files: FileRead[];
}) {
  const [printers, setPrinters] = useState<PrinterRead[]>([]);
  const [printerId, setPrinterId] = useState<number | null>(null);
  const [fileId, setFileId] = useState<number>(files[files.length - 1]?.id);
  const [startPrint, setStartPrint] = useState(false);
  const [remoteName, setRemoteName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setErr(null);
    setDone(null);
    setRemoteName("");
    setStartPrint(false);
    setApiKey("");
    setFileId(files[files.length - 1]?.id);
    listPrinters()
      .then((ps) => {
        setPrinters(ps);
        if (ps.length > 0) setPrinterId(ps[0].id);
      })
      .catch((e) => setErr(e.message));
  }, [open, files]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!printerId || !fileId) return;
    setSubmitting(true);
    setErr(null);
    try {
      const job = await sendToPrinter(
        printerId,
        {
          file_id: fileId,
          start_print: startPrint,
          remote_filename: remoteName.trim() || undefined,
        },
        apiKey,
      );
      setDone(
        startPrint
          ? `Print started (job #${job.id}).`
          : `Uploaded to printer (job #${job.id}).`,
      );
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Send to printer">
      {printers.length === 0 ? (
        <div className="space-y-3 text-sm">
          <p className="text-muted-foreground">
            No printers configured yet. Add one first.
          </p>
          <Button asChild>
            <a href="/printers">
              <Printer className="mr-2 h-4 w-4" /> Manage printers
            </a>
          </Button>
        </div>
      ) : done ? (
        <div className="space-y-4 text-sm">
          <div className="rounded border border-emerald-500/30 bg-emerald-500/10 p-3 text-emerald-700 dark:text-emerald-300">
            {done}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>
              Close
            </Button>
            <Button asChild>
              <a href={`/printers/${printerId}`}>Open printer →</a>
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-1">
            <label className="text-sm font-medium">Printer</label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={printerId ?? ""}
              onChange={(e) => setPrinterId(Number(e.target.value))}
            >
              {printers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} — {p.status}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">G-code file</label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={fileId ?? ""}
              onChange={(e) => setFileId(Number(e.target.value))}
            >
              {files.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.original_filename} (v{f.version})
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">
              Remote filename{" "}
              <span className="text-xs font-normal text-muted-foreground">
                (optional)
              </span>
            </label>
            <Input
              value={remoteName}
              onChange={(e) => setRemoteName(e.target.value)}
              placeholder="defaults to source filename"
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={startPrint}
              onChange={(e) => setStartPrint(e.target.checked)}
              className="h-4 w-4"
            />
            Start print immediately after upload
          </label>
          <div className="space-y-1">
            <label className="text-sm font-medium">
              API key <Badge variant="destructive">required</Badge>
            </label>
            <Input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
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
            <Button
              type="submit"
              disabled={submitting || !printerId || !fileId || !apiKey}
            >
              {submitting ? "Sending…" : startPrint ? "Upload & print" : "Upload"}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
