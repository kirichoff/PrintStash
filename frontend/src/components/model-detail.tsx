"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import type { STLViewerControls } from "@/components/stl-viewer";
import dynamic from "next/dynamic";
import Link from "next/link";
import { CategoryRead, ModelRead, PrinterRead, TagRead } from "@/types";

const STLViewer = dynamic(
  () => import("@/components/stl-viewer").then((m) => ({ default: m.STLViewer })),
  { ssr: false, loading: () => <Loader2 className="h-8 w-8 animate-spin text-[var(--on-surface-variant)]" /> },
);
import {
  createTag,
  deleteModel,
  getAssetUrl,
  listCategories,
  listPrinters,
  listTags,
  sendToPrinter,
  updateModel,
} from "@/lib/api";
import { toast } from "@/lib/toast";
import { useRequireAuth } from "@/lib/use-require-auth";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  Download,
  FileText,
  Loader2,
  Minus,
  Pencil,
  Plus,
  RotateCcw,
  Send,
  Trash2,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function ModelDetail({ model: initialModel }: { model: ModelRead }) {
  const router = useRouter();
  const auth = useRequireAuth();
  const [model, setModel] = useState(initialModel);
  const [deleting, setDeleting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editName, setEditName] = useState(model.name);
  const [editDescription, setEditDescription] = useState(model.description || "");
  const [editCategory, setEditCategory] = useState(model.category || "");
  const [editTags, setEditTags] = useState<string[]>([...model.tags]);
  const [catOpen, setCatOpen] = useState(false);
  const [tagInput, setTagInput] = useState("");
  const [categories, setCategories] = useState<CategoryRead[]>([]);
  const [tags, setTags] = useState<TagRead[]>([]);
  const [catLoaded, setCatLoaded] = useState(false);
  const viewerControls = useRef<STLViewerControls | null>(null);

  async function doDelete() {
    if (!confirm("Delete this model? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await deleteModel(model.id);
      toast.success("Model deleted");
      router.push("/");
      router.refresh();
    } catch (e) {
      toast.error(e);
    } finally {
      setDeleting(false);
    }
  }

  function enterEdit() {
    setEditName(model.name);
    setEditDescription(model.description || "");
    setEditCategory(model.category || "");
    setEditTags([...model.tags]);
    setTagInput("");
    setCatOpen(false);
    if (!catLoaded) {
      listCategories().then((c) => { setCategories(c); setCatLoaded(true); }).catch(() => {});
      listTags().then(setTags).catch(() => {});
    }
    setEditing(true);
  }

  function cancelEdit() {
    setEditing(false);
  }

  async function saveEdit() {
    setSaving(true);
    try {
      const updated = await updateModel(model.id, {
        name: editName.trim() || undefined,
        description: editDescription.trim() || undefined,
        category: editCategory || undefined,
        tags: editTags.length ? editTags : undefined,
      });
      setModel(updated);
      setEditing(false);
      toast.success("Model updated");
    } catch (e) {
      toast.error(e);
    } finally {
      setSaving(false);
    }
  }

  function editToggleTag(slug: string) {
    setEditTags((p) =>
      p.includes(slug) ? p.filter((s) => s !== slug) : [...p, slug],
    );
  }

  async function editCreateTag(name: string) {
    const trimmed = name.trim();
    if (!trimmed) return;
    const existing = tags.find(
      (t) => t.name.toLowerCase() === trimmed.toLowerCase(),
    );
    if (existing) {
      if (!editTags.includes(existing.slug)) editToggleTag(existing.slug);
      return;
    }
    try {
      const t = await createTag({ name: trimmed });
      setTags((p) => [...p, t]);
      setEditTags((p) => [...p, t.slug]);
    } catch {
      /* ignored */
    }
  }

  const editFilteredTags = useMemo(() => {
    const q = tagInput.toLowerCase().trim();
    return tags.filter(
      (t) =>
        !editTags.includes(t.slug) &&
        (q === "" || t.name.toLowerCase().includes(q)),
    );
  }, [tags, tagInput, editTags]);

  const editCanCreate =
    tagInput.trim().length > 0 &&
    !tags.find(
      (t) => t.name.toLowerCase() === tagInput.trim().toLowerCase(),
    );

  const latestFile = model.files[model.files.length - 1];
  const meta = latestFile?.metadata;
  const meshFile = model.files.find(
    (f) => f.file_type === "stl" || f.file_type === "3mf" || f.file_type === "obj",
  );
  const gcodeFiles = model.files.filter((f) => f.file_type === "gcode");
  const hasGcode = gcodeFiles.length > 0;
  const thumbUrl = model.thumbnail_url ? getAssetUrl(model.thumbnail_url) : null;

  return (
    <div className="flex flex-col h-full">
      {/* Detail Header */}
      <header className="h-16 flex items-center justify-between px-6 border-b border-[var(--outline-variant)] bg-[var(--surface-container-lowest)] shrink-0">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="w-10 h-10 flex items-center justify-center rounded hover:bg-[var(--surface-container-high)] text-[var(--on-surface-variant)] transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            {editing ? (
              <input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full bg-[var(--surface)] text-[var(--on-surface)] font-mono text-lg border border-[var(--outline-variant)] rounded px-2 py-0.5 focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent"
                placeholder="Model name"
              />
            ) : (
              <h1 className="text-xl font-semibold text-[var(--on-surface)] leading-tight">
                {model.name}
              </h1>
            )}
            <span className="font-mono text-[13px] text-[var(--on-surface-variant)]">
              Last updated: {timeAgo(model.updated_at)}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {editing ? (
            <>
              <button
                onClick={cancelEdit}
                className="px-4 py-2 rounded border border-[var(--outline-variant)] text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-low)] transition-colors font-mono text-xs uppercase tracking-wider"
              >
                Cancel
              </button>
              <button
                onClick={saveEdit}
                disabled={saving}
                className="px-4 py-2 rounded bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 transition-opacity font-mono text-xs uppercase tracking-wider flex items-center gap-1.5 disabled:opacity-50"
              >
                {saving ? (
                  <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</>
                ) : (
                  <><Check className="h-4 w-4" /> Save</>
                )}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={auth.isAuthenticated ? enterEdit : auth.showAuthRequiredToast}
                disabled={!auth.isAuthenticated}
                title={auth.blockReason ?? "Edit model"}
                className="px-4 py-2 rounded border border-[var(--outline-variant)] text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-low)] transition-colors font-mono text-xs uppercase tracking-wider flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Pencil className="h-4 w-4" /> {auth.isAuthenticated ? "Edit" : "Sign in to edit"}
              </button>
              <button
                onClick={auth.isAuthenticated ? doDelete : auth.showAuthRequiredToast}
                disabled={deleting || !auth.isAuthenticated}
                title={auth.blockReason ?? "Delete model"}
                className="px-4 py-2 rounded border border-[var(--outline-variant)] text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-low)] transition-colors font-mono text-xs uppercase tracking-wider flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleting ? (
                  <><Loader2 className="h-4 w-4 animate-spin" /> Deleting...</>
                ) : auth.isAuthenticated ? (
                  <><Trash2 className="h-4 w-4" /> Delete</>
                ) : (
                  <><Trash2 className="h-4 w-4" /> Sign in to delete</>
                )}
              </button>
            </>
          )}
        </div>
      </header>

      {/* Two-Column Layout */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* Left: 3D Model Preview */}
        <div className="flex-1 bg-[var(--surface-container-low)] relative border-r border-[var(--outline-variant)] flex items-center justify-center m-4 rounded overflow-hidden"
          style={{ boxShadow: "inset 0 0 0 1px var(--surface-variant)" }}>
          {meshFile ? (
            <Suspense fallback={
              <div className="flex items-center justify-center text-[var(--on-surface-variant)]">
                <Loader2 className="h-8 w-8 animate-spin" />
              </div>
            }>
              <STLViewer
                url={getAssetUrl(`/api/v1/files/${meshFile.id}/stl`)}
                onControlsReady={(api) => { viewerControls.current = api; }}
              />
            </Suspense>
          ) : thumbUrl ? (
            <img
              src={thumbUrl}
              alt={model.name}
              className="max-w-full max-h-full object-contain"
            />
          ) : (
            <div className="flex items-center justify-center text-[var(--on-surface-variant)]">
              <FileText className="h-20 w-20 opacity-20" />
            </div>
          )}

          {/* 3D Viewer Controls */}
          <div className="absolute bottom-4 right-4 flex flex-col gap-1 z-10">
            <div className="flex bg-[var(--surface-container-lowest)]/90 backdrop-blur border border-[var(--outline-variant)] rounded overflow-hidden shadow-sm">
              <button
                onClick={() => viewerControls.current?.zoomIn()}
                className="w-9 h-9 flex items-center justify-center text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-high)] hover:text-[var(--primary)] transition-colors border-r border-[var(--outline-variant)]"
                title="Zoom in"
              >
                <Plus className="h-4 w-4" />
              </button>
              <button
                onClick={() => viewerControls.current?.zoomOut()}
                className="w-9 h-9 flex items-center justify-center text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-high)] hover:text-[var(--primary)] transition-colors"
                title="Zoom out"
              >
                <Minus className="h-4 w-4" />
              </button>
            </div>
            <button
              onClick={() => viewerControls.current?.resetView()}
              className="h-9 px-3 bg-[var(--surface-container-lowest)]/90 backdrop-blur border border-[var(--outline-variant)] rounded shadow-sm flex items-center justify-center text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-high)] hover:text-[var(--primary)] transition-colors"
              title="Reset view"
            >
              <RotateCcw className="h-4 w-4" />
            </button>
          </div>

          {/* Dimensions overlay */}
          {meta?.bbox_x_mm && meta?.bbox_y_mm && meta?.bbox_z_mm && (
            <div className="absolute top-4 left-4 z-10">
              <div className="bg-[var(--surface-container-lowest)]/90 backdrop-blur border border-[var(--outline-variant)] rounded px-2 py-1 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="font-mono text-[13px] text-[var(--on-surface)]">
                  {meta.bbox_x_mm}×{meta.bbox_y_mm}×{meta.bbox_z_mm} mm
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Right: Settings & Files Panel */}
        <div className="w-[400px] bg-[var(--surface-container-lowest)] border-l border-[var(--outline-variant)] flex flex-col h-full shrink-0 min-h-0">
          <div className="flex-1 overflow-y-auto p-6 space-y-8">
            {/* Print Settings */}
            <section>
              <h2 className="text-lg font-semibold text-[var(--on-surface)] mb-4 pb-1 border-b border-[var(--outline-variant)]">
                Print Settings
              </h2>
              <div className="bg-[var(--surface)] border border-[var(--outline-variant)] rounded flex flex-col">
                <SettingRow label="PRINTER PROFILE" value={meta?.printer_model ?? "—"} />
                <SettingRow label="MATERIAL" value={meta?.material_type ?? "—"} chip />
                <SettingRow label="LAYER HEIGHT" value={meta?.layer_height_mm ? `${meta.layer_height_mm}mm` : "—"} />
                <SettingRow label="NOZZLE" value={meta?.nozzle_diameter_mm ? `${meta.nozzle_diameter_mm}mm` : "—"} />
                <SettingRow label="INFILL" value={meta?.infill_percent ? `${meta.infill_percent}%` : "—"} />
                <SettingRow label="EST. TIME" value={formatDuration(meta?.estimated_time_s ?? null)} highlight />
                <SettingRow label="FILAMENT" value={meta?.filament_weight_g ? `${meta.filament_weight_g}g` : "—"} last />
              </div>
            </section>

            {/* Mesh Geometry */}
            {(meta?.volume_mm3 || meta?.triangle_count) && (
              <section>
                <h2 className="text-lg font-semibold text-[var(--on-surface)] mb-4 pb-1 border-b border-[var(--outline-variant)]">
                  Mesh Geometry
                </h2>
                <div className="bg-[var(--surface)] border border-[var(--outline-variant)] rounded flex flex-col">
                  {meta?.volume_mm3 && (
                    <SettingRow
                      label="VOLUME"
                      value={meta.volume_mm3 < 1000 ? `${meta.volume_mm3.toFixed(1)} mm³` : `${(meta.volume_mm3 / 1000).toFixed(2)} cm³`}
                    />
                  )}
                  {meta?.triangle_count && (
                    <SettingRow label="TRIANGLES" value={meta.triangle_count.toLocaleString()} last />
                  )}
                </div>
              </section>
            )}

            {/* Slicer info */}
            {meta?.slicer_name && (
              <p className="font-mono text-xs text-[var(--on-surface-variant)]">
                Sliced with {meta.slicer_name}
                {meta.slicer_version ? ` v${meta.slicer_version}` : ""}
              </p>
            )}

            {/* Tags & Category */}
            {editing ? (
              <div className="space-y-4">
                {/* Category picker */}
                <div>
                  <label className="block font-mono text-[10px] text-[var(--on-surface-variant)] tracking-wider uppercase mb-1.5">
                    Category
                  </label>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setCatOpen((v) => !v)}
                      className="w-full h-10 flex items-center justify-between bg-[var(--surface)] text-[var(--on-surface)] font-mono text-sm border border-[var(--outline-variant)] rounded px-3 focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent"
                    >
                      <span className={editCategory ? "" : "text-[var(--on-surface-variant)]/60"}>
                        {editCategory || "None"}
                      </span>
                      <ChevronDown className="h-4 w-4 text-[var(--on-surface-variant)]" />
                    </button>
                    {catOpen && (
                      <>
                        <div className="fixed inset-0 z-40" onClick={() => setCatOpen(false)} />
                        <div className="absolute left-0 right-0 top-full mt-1 z-50 bg-[var(--surface-container-lowest)] border border-[var(--outline-variant)] rounded shadow-lg py-1 max-h-56 overflow-y-auto">
                          <button
                            type="button"
                            onClick={() => { setEditCategory(""); setCatOpen(false); }}
                            className="w-full text-left px-3 py-1.5 font-mono text-xs text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-low)]"
                          >
                            None
                          </button>
                          {categories.map((c) => (
                            <button
                              key={c.id}
                              type="button"
                              onClick={() => { setEditCategory(c.path); setCatOpen(false); }}
                              className={`w-full text-left px-3 py-1.5 font-mono text-xs transition-colors ${
                                editCategory === c.path
                                  ? "text-[var(--primary)] bg-[var(--secondary-container)]"
                                  : "text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-low)]"
                              }`}
                            >
                              {c.path} <span className="opacity-50">({c.model_count})</span>
                            </button>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                </div>
                {/* Description */}
                <div>
                  <label className="block font-mono text-[10px] text-[var(--on-surface-variant)] tracking-wider uppercase mb-1.5">
                    Description
                  </label>
                  <textarea
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    rows={2}
                    className="w-full bg-[var(--surface)] text-[var(--on-surface)] font-mono text-sm border border-[var(--outline-variant)] rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent resize-none"
                    placeholder="Optional description"
                  />
                </div>
                {/* Tags */}
                <div>
                  <label className="block font-mono text-[10px] text-[var(--on-surface-variant)] tracking-wider uppercase mb-1.5">
                    Tags
                  </label>
                  <div className="relative">
                    <input
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && tagInput.trim()) {
                          e.preventDefault();
                          editCreateTag(tagInput);
                          setTagInput("");
                        } else if (e.key === "Backspace" && !tagInput && editTags.length) {
                          setEditTags((p) => p.slice(0, -1));
                        }
                      }}
                      placeholder="Search or create — press Enter"
                      className="w-full h-10 bg-[var(--surface)] text-[var(--on-surface)] font-mono text-sm border border-[var(--outline-variant)] rounded px-3 focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent"
                    />
                    {tagInput && (editFilteredTags.length > 0 || editCanCreate) && (
                      <div className="absolute left-0 right-0 top-full mt-1 z-50 bg-[var(--surface-container-lowest)] border border-[var(--outline-variant)] rounded shadow-lg py-1 max-h-40 overflow-y-auto">
                        {editFilteredTags.slice(0, 6).map((t) => (
                          <button
                            key={t.id}
                            type="button"
                            onClick={() => { editToggleTag(t.slug); setTagInput(""); }}
                            className="w-full text-left px-3 py-1.5 font-mono text-xs text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-low)] flex justify-between"
                          >
                            <span>{t.name}</span>
                            <span className="opacity-50">({t.model_count})</span>
                          </button>
                        ))}
                        {editCanCreate && (
                          <button
                            type="button"
                            onClick={() => { editCreateTag(tagInput); setTagInput(""); }}
                            className="w-full text-left px-3 py-1.5 font-mono text-xs text-[var(--primary)] hover:bg-[var(--surface-container-low)] flex items-center gap-2"
                          >
                            <Plus className="h-3 w-3" /> Create &quot;{tagInput.trim()}&quot;
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                  {editTags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {editTags.map((slug) => {
                        const t = tags.find((x) => x.slug === slug);
                        return (
                          <span key={slug} className="inline-flex items-center gap-1 bg-[var(--secondary-container)] text-[var(--on-secondary-container)] pl-2 pr-1 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider">
                            {t?.name || slug}
                            <button type="button" onClick={() => editToggleTag(slug)} aria-label={`Remove ${t?.name || slug}`} className="h-3.5 w-3.5 rounded-sm flex items-center justify-center hover:bg-[var(--on-secondary-container)]/10">
                              <X className="h-3 w-3" />
                            </button>
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {model.category && (
                  <span className="bg-[var(--surface-container)] text-[var(--on-surface)] px-3 py-1 rounded font-mono text-xs uppercase tracking-wider">
                    {model.category}
                  </span>
                )}
                {model.tags.map((t) => (
                  <span key={t} className="bg-[var(--secondary-container)] text-[var(--on-secondary-container)] px-3 py-1 rounded font-mono text-xs uppercase tracking-wider">
                    {t}
                  </span>
                ))}
              </div>
            )}

            {/* Associated Files */}
            <section>
              <h2 className="text-lg font-semibold text-[var(--on-surface)] mb-4 pb-1 border-b border-[var(--outline-variant)]">
                Associated Files
              </h2>
              <div className="space-y-2">
                {model.files.map((f) => {
                  const isGcode = f.file_type === "gcode";
                  return (
                    <div
                      key={f.id}
                      className={`flex items-center justify-between p-3 border rounded hover:shadow-sm transition-all group bg-[var(--surface)] ${isGcode ? "border-[var(--primary)]/30 bg-[var(--primary-fixed)]/20 hover:border-[var(--primary)]" : "border-[var(--outline-variant)] hover:border-[var(--primary)]"}`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <FileText className={`h-5 w-5 flex-shrink-0 ${isGcode ? "text-[var(--primary)]" : "text-[var(--outline)] group-hover:text-[var(--primary)]"}`} />
                        <div className="min-w-0">
                          <p className="text-sm text-[var(--on-surface)] font-medium truncate">
                            {f.original_filename}
                          </p>
                          <p className="font-mono text-[11px] text-[var(--on-surface-variant)]">
                            {formatBytes(f.size_bytes)} · v{f.version}
                            {isGcode ? " · Sliced" : " · Source"}
                          </p>
                        </div>
                      </div>
                      <a
                        href={getAssetUrl(`/api/v1/files/${f.id}/download`)}
                        download={f.original_filename}
                        className="text-[var(--on-surface-variant)] hover:text-[var(--primary)] p-2 rounded hover:bg-[var(--surface-container-high)] transition-colors flex-shrink-0"
                      >
                        <Download className="h-5 w-5" />
                      </a>
                    </div>
                  );
                })}
              </div>
            </section>
          </div>

          {/* Klipper Sync Panel */}
          <div className="p-6 border-t border-[var(--outline-variant)] bg-[var(--surface-container-low)] shrink-0 space-y-3">
            {hasGcode && (
              <SendToButtons modelId={model.id} gcodeFiles={gcodeFiles} />
            )}
            {!hasGcode && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-[var(--on-surface-variant)] uppercase tracking-wider">
                    Sync status
                  </span>
                  <div className="flex items-center gap-1.5 px-2 py-1 bg-[var(--surface-container-lowest)] border border-[var(--outline-variant)] rounded">
                    <Wifi className="h-3 w-3 text-[var(--on-surface-variant)]" />
                    <span className="font-mono text-xs text-[var(--on-surface-variant)]">
                      No G-code file
                    </span>
                  </div>
                </div>
              </div>
            )}
            <div className="flex items-center justify-between border-t border-[var(--surface-container-highest)] pt-3">
              <span className="font-mono text-xs text-[var(--on-surface-variant)] uppercase tracking-wider">Files</span>
              <span className="font-mono text-sm text-[var(--on-surface)] font-semibold">{model.files.length}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-[var(--on-surface-variant)] uppercase tracking-wider">Created</span>
              <span className="font-mono text-xs text-[var(--on-surface)]">{new Date(model.created_at).toLocaleDateString()}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SendToButtons({ modelId, gcodeFiles }: { modelId: number; gcodeFiles: { id: number; original_filename: string; version: number }[] }) {
  const auth = useRequireAuth();
  const [showSend, setShowSend] = useState(false);
  const [selectedFile, setSelectedFile] = useState<number>(gcodeFiles[gcodeFiles.length - 1]?.id ?? 0);
  const [startPrint, setStartPrint] = useState(false);
  const [printers, setPrinters] = useState<PrinterRead[]>([]);
  const [printerId, setPrinterId] = useState<number | null>(null);
  const [printersLoading, setPrintersLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!showSend) return;
    let alive = true;
    setPrintersLoading(true);
    listPrinters()
      .then((p) => {
        if (!alive) return;
        setPrinters(p);
        if (p.length > 0) setPrinterId(p[0].id);
      })
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setPrintersLoading(false));
    return () => {
      alive = false;
    };
  }, [showSend]);

  const selectedPrinter = printers.find((p) => p.id === printerId) ?? null;
  const online = selectedPrinter && selectedPrinter.status !== "offline" && selectedPrinter.status !== "unknown";

  async function send() {
    if (!selectedFile || !printerId) return;
    setSending(true);
    setError(null);
    try {
      const job = await sendToPrinter(printerId, {
        file_id: selectedFile,
        start_print: startPrint,
      });
      setShowSend(false);
      toast.success(startPrint ? `Print started (job #${job.id})` : `Sent to printer (job #${job.id})`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-[var(--on-surface-variant)] uppercase tracking-wider">Klipper status</span>
        <div className="flex items-center gap-1.5 px-2 py-1 bg-[var(--surface-container-lowest)] border border-[var(--outline-variant)] rounded">
          {printersLoading ? (
            <>
              <Loader2 className="h-3 w-3 animate-spin text-[var(--on-surface-variant)]" />
              <span className="font-mono text-xs text-[var(--on-surface-variant)]">Checking…</span>
            </>
          ) : printers.length === 0 ? (
            <>
              <WifiOff className="h-3 w-3 text-[var(--on-surface-variant)]" />
              <span className="font-mono text-xs text-[var(--on-surface-variant)]">No printers</span>
            </>
          ) : online ? (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="font-mono text-xs font-bold text-emerald-500 tracking-wider capitalize">{selectedPrinter?.status}</span>
            </>
          ) : (
            <>
              <WifiOff className="h-3 w-3 text-amber-500" />
              <span className="font-mono text-xs text-amber-500 capitalize">{selectedPrinter?.status ?? "offline"}</span>
            </>
          )}
        </div>
      </div>

      {showSend ? (
        <div className="space-y-3">
          {printers.length > 1 && (
            <select
              value={printerId ?? ""}
              onChange={(e) => setPrinterId(Number(e.target.value))}
              className="w-full bg-[var(--surface-container-lowest)] border border-[var(--outline-variant)] rounded px-3 py-2 font-mono text-xs text-[var(--on-surface)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
            >
              {printers.map((p) => (
                <option key={p.id} value={p.id}>{p.name} — {p.status}</option>
              ))}
            </select>
          )}
          <select
            value={selectedFile}
            onChange={(e) => setSelectedFile(Number(e.target.value))}
            className="w-full bg-[var(--surface-container-lowest)] border border-[var(--outline-variant)] rounded px-3 py-2 font-mono text-xs text-[var(--on-surface)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
          >
            {gcodeFiles.map((f) => (
              <option key={f.id} value={f.id}>{f.original_filename} (v{f.version})</option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-xs font-mono text-[var(--on-surface-variant)]">
            <input type="checkbox" checked={startPrint} onChange={(e) => setStartPrint(e.target.checked)} className="rounded" />
            Start print immediately
          </label>
          {error && (
            <div className="rounded border border-[var(--error)]/30 bg-[var(--error-container)]/20 p-2 text-[11px] text-[var(--error)] font-mono break-words">
              {error}
            </div>
          )}
          <div className="flex gap-2">
            <button onClick={() => setShowSend(false)} disabled={sending} className="flex-1 py-2 rounded border border-[var(--outline-variant)] text-[var(--on-surface-variant)] font-mono text-xs uppercase tracking-wider hover:bg-[var(--surface-container-low)] transition-colors disabled:opacity-50">Cancel</button>
            <button onClick={send} disabled={sending || !printerId} className="flex-1 py-2 rounded bg-[var(--primary)] text-[var(--primary-foreground)] font-mono text-xs uppercase tracking-wider hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-1.5">
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              {sending ? "Sending…" : startPrint ? "Send & Print" : "Send"}
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <Link href="/printers" className="w-full py-2 border border-[var(--outline-variant)] text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-low)] transition-colors rounded font-mono text-xs uppercase tracking-wider text-center">
            {printers.length === 0 ? "Configure printers" : "Manage printers"}
          </Link>
          <button
            onClick={() => {
              if (!auth.isAuthenticated) { auth.showAuthRequiredToast(); return; }
              setShowSend(true);
            }}
            disabled={printers.length === 0 || !auth.isAuthenticated}
            className="w-full py-2.5 bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 transition-opacity rounded font-mono text-xs uppercase tracking-wider shadow-sm flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {!auth.isAuthenticated ? (
              <><Send className="h-4 w-4" /> Sign in to send</>
            ) : (
              <><Send className="h-4 w-4" /> Send to printer</>
            )}
          </button>
        </div>
      )}
    </div>
  );
}

function SettingRow({
  label, value, chip, highlight, last,
}: { label: string; value: string; chip?: boolean; highlight?: boolean; last?: boolean }) {
  return (
    <div className={`flex justify-between items-center px-3 py-2.5 ${last ? "" : "border-b border-[var(--surface-container-high)]"}`}>
      <span className="font-mono text-xs text-[var(--on-surface-variant)] tracking-wider uppercase">{label}</span>
      {chip ? (
        <span className="px-2 py-0.5 bg-[var(--secondary-container)] text-[var(--on-secondary-container)] rounded font-mono text-[11px]">{value}</span>
      ) : (
        <span className={`font-mono text-[13px] ${highlight ? "text-[var(--primary)] font-bold" : "text-[var(--on-surface)]"}`}>{value}</span>
      )}
    </div>
  );
}
