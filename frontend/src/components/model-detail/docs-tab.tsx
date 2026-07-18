"use client";

import { useEffect, useState } from "react";
import {
  FileText,
  Image as ImageIcon,
  Loader2,
  Pencil,
  Plus,
} from "lucide-react";

import { getJson } from "@/lib/api/request";
import { createDocument, updateDocument } from "@/lib/api/documents";
import { MarkdownView } from "@/components/markdown-view";
import { Button } from "@/components/ui/button";
import { toast } from "@/lib/toast";
import { userMessage } from "@/lib/errors";
import type { DocumentRead } from "@/types";

interface ModelFile {
  id: number;
  file_type: string;
  original_filename: string;
  thumbnail_url?: string;
}

interface ModelData {
  files: ModelFile[];
}

// Image files whose names identify them as slicer plate renders vs. the
// user's own project pictures, so we can group them in the gallery.
function isPlateRender(name: string): boolean {
  const n = name.toLowerCase();
  return (
    n.startsWith("plate_") ||
    n.startsWith("top_") ||
    n.startsWith("pick_") ||
    n.startsWith("thumbnail_")
  );
}

export function DocsTab({
  modelId,
  collectionId,
  canEdit,
}: {
  modelId: number;
  collectionId: number | null;
  canEdit: boolean;
}) {
  const [docs, setDocs] = useState<DocumentRead[]>([]);
  const [imageFiles, setImageFiles] = useState<ModelFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openDocId, setOpenDocId] = useState<number | null>(null);

  // Inline markdown editing state. `editingBody === null` means view mode.
  const [editingBody, setEditingBody] = useState<string | null>(null);
  const [savingDoc, setSavingDoc] = useState(false);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      getJson<DocumentRead[]>(`/api/v1/models/${modelId}/documents`),
      getJson<ModelData>(`/api/v1/models/${modelId}`),
    ])
      .then(([docItems, modelData]) => {
        if (cancelled) return;
        setDocs(docItems);
        if (docItems.length > 0) setOpenDocId(docItems[0].id);
        const imgs = (modelData.files || []).filter(
          (f) => f.file_type === "image",
        );
        setImageFiles(imgs);
      })
      .catch((e) => {
        if (!cancelled) setError(userMessage(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [modelId]);

  const activeDoc = docs.find((d) => d.id === openDocId) ?? docs[0];
  const canEditDoc =
    canEdit &&
    !!activeDoc &&
    activeDoc.kind === "markdown" &&
    (activeDoc.effective_role === "edit" || activeDoc.effective_role === "admin");

  async function saveDoc() {
    if (!activeDoc || editingBody === null) return;
    setSavingDoc(true);
    try {
      const updated = await updateDocument(activeDoc.id, { body: editingBody });
      setDocs((ds) =>
        ds.map((d) => (d.id === updated.id ? { ...d, body: updated.body } : d)),
      );
      setEditingBody(null);
      toast.success("Project notes saved");
    } catch (e) {
      toast.error(e);
    } finally {
      setSavingDoc(false);
    }
  }

  async function addNotes() {
    setCreating(true);
    try {
      const created = await createDocument({
        name: "Project Notes",
        collection_id: collectionId,
        body: "",
      });
      setDocs((ds) => [created, ...ds]);
      setOpenDocId(created.id);
      setEditingBody("");
      toast.success("Project notes created");
    } catch (e) {
      toast.error(e);
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-on-surface-variant" />
      </div>
    );
  }

  if (error) {
    return <p className="text-sm text-destructive py-4">{error}</p>;
  }

  const hasDocs = docs.length > 0;
  const plateImages = imageFiles.filter((f) =>
    isPlateRender(f.original_filename),
  );
  const projectPictures = imageFiles.filter(
    (f) => !isPlateRender(f.original_filename),
  );
  const hasImages = plateImages.length > 0 || projectPictures.length > 0;

  if (!hasDocs && !hasImages) {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-center">
        <FileText className="h-8 w-8 text-on-surface-variant/40" />
        <div>
          <p className="text-sm font-medium text-on-surface">
            No project documentation
          </p>
          <p className="text-xs text-on-surface-variant mt-1">
            {canEdit
              ? "Add project notes, or upload a 3MF/README to see its description and previews here."
              : "Upload a README or a 3MF with an embedded description to see it here."}
          </p>
        </div>
        {canEdit && (
          <Button size="sm" onClick={addNotes} loading={creating}>
            <Plus className="h-3.5 w-3.5" /> Add project notes
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Document tabs */}
      {docs.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {docs.map((doc) => (
            <button
              key={doc.id}
              type="button"
              onClick={() => {
                setOpenDocId(doc.id);
                setEditingBody(null);
              }}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                doc.id === (openDocId ?? docs[0].id)
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-outline-variant text-on-surface-variant hover:border-primary/50 hover:text-on-surface"
              }`}
            >
              <FileText className="h-3 w-3" />
              {doc.name}
            </button>
          ))}
        </div>
      )}

      {/* Document body */}
      {hasDocs && activeDoc && (
        <div className="rounded-lg border border-outline-variant bg-surface-container-low p-4 md:p-6">
          {activeDoc.kind === "markdown" ? (
            <>
              {/* Edit toolbar */}
              {canEditDoc && (
                <div className="mb-3 flex items-center justify-end gap-2">
                  {editingBody === null ? (
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={() => setEditingBody(activeDoc.body ?? "")}
                    >
                      <Pencil className="h-3.5 w-3.5" /> Edit
                    </Button>
                  ) : (
                    <>
                      <Button
                        variant="ghost"
                        size="xs"
                        onClick={() => setEditingBody(null)}
                        disabled={savingDoc}
                      >
                        Cancel
                      </Button>
                      <Button size="xs" onClick={saveDoc} loading={savingDoc}>
                        Save
                      </Button>
                    </>
                  )}
                </div>
              )}
              {editingBody !== null ? (
                <textarea
                  value={editingBody}
                  onChange={(e) => setEditingBody(e.target.value)}
                  placeholder="Write project notes in Markdown…"
                  className="min-h-[240px] w-full rounded border border-outline-variant bg-surface p-3 font-mono text-sm text-on-surface focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary"
                />
              ) : activeDoc.body ? (
                <MarkdownView source={activeDoc.body} />
              ) : (
                <p className="text-sm text-on-surface-variant">
                  This document is empty.
                </p>
              )}
            </>
          ) : activeDoc.kind === "pdf" || activeDoc.filename ? (
            <p className="text-sm text-on-surface-variant">
              <a
                href={`/api/v1/documents/${activeDoc.id}/file`}
                target="_blank"
                rel="noreferrer noopener"
                className="text-primary hover:underline"
              >
                Open {activeDoc.filename ?? activeDoc.name}
              </a>
            </p>
          ) : (
            <p className="text-sm text-on-surface-variant">
              No preview available.
            </p>
          )}
        </div>
      )}

      {/* "Add project notes" when there are images but no markdown doc yet. */}
      {canEdit && !docs.some((d) => d.kind === "markdown") && (
        <Button
          variant="outline"
          size="sm"
          onClick={addNotes}
          loading={creating}
        >
          <Plus className="h-3.5 w-3.5" /> Add project notes
        </Button>
      )}

      {/* Project pictures (user-authored) */}
      {projectPictures.length > 0 && (
        <ImageGallery title="Project Pictures" images={projectPictures} />
      )}

      {/* Plate previews (slicer renders) */}
      {plateImages.length > 0 && (
        <ImageGallery title="Plate Previews" images={plateImages} />
      )}
    </div>
  );
}

function ImageGallery({
  title,
  images,
}: {
  title: string;
  images: ModelFile[];
}) {
  return (
    <div>
      <h3 className="text-sm font-medium text-on-surface mb-3 flex items-center gap-2">
        <ImageIcon className="h-4 w-4 text-on-surface-variant" />
        {title}
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {images.map((img) => (
          <a
            key={img.id}
            href={`/api/v1/files/${img.id}/thumbnail`}
            target="_blank"
            rel="noreferrer noopener"
            className="group relative aspect-video rounded-lg border border-outline-variant overflow-hidden bg-surface-container-low hover:border-primary/50 transition-colors"
          >
            <img
              src={`/api/v1/files/${img.id}/thumbnail`}
              alt={img.original_filename}
              className="h-full w-full object-cover"
              loading="lazy"
            />
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent p-2 pt-6 opacity-0 group-hover:opacity-100 transition-opacity">
              <span className="text-[10px] text-white truncate block">
                {img.original_filename}
              </span>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
