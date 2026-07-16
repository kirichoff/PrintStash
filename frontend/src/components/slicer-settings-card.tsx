"use client";

import { useCallback, useEffect, useState } from "react";
import { ExternalLink, Plus, RotateCcw, Trash2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { inputClasses } from "@/components/ui/input";
import {
  readCustomSlicers,
  writeCustomSlicers,
  type CustomSlicer,
} from "@/lib/slicer-config";
import { toast } from "@/lib/toast";

const BTN_SECONDARY = cn(
  buttonVariants({ variant: "outline", size: "xs" }),
  "uppercase tracking-wider text-muted-foreground",
);

const INPUT = cn(inputClasses, "h-auto py-2 rounded");

type SlicerEditor = {
  key: string; // unique key for list rendering
  name: string;
  scheme: string;
  types: string;
};

function emptyEditor(): SlicerEditor {
  return {
    key: crypto.randomUUID(),
    name: "",
    scheme: "",
    types: "stl, 3mf, gcode",
  };
}

function editorToSlicer(e: SlicerEditor): CustomSlicer | null {
  const name = e.name.trim();
  const scheme = e.scheme.trim();
  if (!name || !scheme) return null;
  const types = e.types
    .split(/[,\s]+/)
    .map((t) => t.trim().toLowerCase().replace(/^\./, ""))
    .filter(Boolean);
  if (types.length === 0) return null;
  return { name, scheme, types };
}

function slicerToEditor(s: CustomSlicer): SlicerEditor {
  return {
    key: crypto.randomUUID(),
    name: s.name,
    scheme: s.scheme,
    types: s.types.join(", "),
  };
}

export function SlicerSettingsCard() {
  const [editors, setEditors] = useState<SlicerEditor[]>([]);

  useEffect(() => {
    const slicers = readCustomSlicers();
    const defaults = slicers.length > 0 ? slicers : [];
    setEditors(defaults.length > 0 ? defaults.map(slicerToEditor) : [emptyEditor()]);
  }, []);

  const save = useCallback(() => {
    const slicers = editors
      .map(editorToSlicer)
      .filter((s): s is CustomSlicer => s !== null);
    writeCustomSlicers(slicers);
    toast.success("Slicers saved.");
  }, [editors]);

  const reset = useCallback(() => {
    setEditors([emptyEditor()]);
    writeCustomSlicers([]);
    toast.success("Slicers reset to defaults.");
  }, []);

  function update(idx: number, field: keyof SlicerEditor, value: string) {
    setEditors((current) => {
      const next = [...current];
      next[idx] = { ...next[idx], [field]: value };
      return next;
    });
  }

  function remove(idx: number) {
    setEditors((current) => {
      if (current.length <= 1) return current;
      return current.filter((_, i) => i !== idx);
    });
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card text-card-foreground shadow-sm">
      <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-4 sm:px-5">
        <div className="flex items-start gap-3 min-w-0">
          <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
            <ExternalLink className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-foreground">
              Custom slicers
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Add custom URL schemes for opening files in your slicer. Each
              entry appears in the "Open in slicer" menu on model files.
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={reset} className={BTN_SECONDARY}>
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </button>
          <button type="button" onClick={save} className={BTN_SECONDARY}>
            Save
          </button>
        </div>
      </div>

      <div className="p-4 sm:p-5 space-y-4">
        {editors.map((editor, idx) => (
          <div
            key={editor.key}
            className="rounded border border-border p-3 space-y-3"
          >
            <div className="grid gap-2 sm:grid-cols-[1fr_1fr_1.5fr_auto] sm:items-end">
              <label className="block space-y-1">
                <span className="block font-mono text-3xs uppercase tracking-wider text-muted-foreground">
                  Name
                </span>
                <input
                  value={editor.name}
                  onChange={(e) => update(idx, "name", e.target.value)}
                  className={INPUT}
                  placeholder="Snapmaker Orca"
                />
              </label>
              <label className="block space-y-1">
                <span className="block font-mono text-3xs uppercase tracking-wider text-muted-foreground">
                  URL scheme
                </span>
                <input
                  value={editor.scheme}
                  onChange={(e) => update(idx, "scheme", e.target.value)}
                  className={INPUT}
                  placeholder="snapmaker-orca"
                />
              </label>
              <label className="block space-y-1">
                <span className="block font-mono text-3xs uppercase tracking-wider text-muted-foreground">
                  File types
                </span>
                <input
                  value={editor.types}
                  onChange={(e) => update(idx, "types", e.target.value)}
                  className={INPUT}
                  placeholder="stl, 3mf, gcode"
                />
              </label>
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => remove(idx)}
                  disabled={editors.length <= 1}
                  className="inline-flex h-9 w-9 items-center justify-center rounded border border-border text-red-500 hover:bg-red-500/10 disabled:opacity-50"
                  title="Remove slicer"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Files will open via:{" "}
              <code className="font-mono break-all">
                {editor.scheme || "{scheme}"}://open?file=&#8203;{"{url}"}
              </code>
            </p>
          </div>
        ))}

        <button
          type="button"
          onClick={() =>
            setEditors((current) => [...current, emptyEditor()])
          }
          className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:text-primary/80 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          Add slicer
        </button>
      </div>
    </div>
  );
}
