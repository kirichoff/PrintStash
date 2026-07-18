"use client";

import { useEffect, useState } from "react";
import { FileText, Image as ImageIcon, Loader2 } from "lucide-react";

import { getJson } from "@/lib/api/request";
import { MarkdownView } from "@/components/markdown-view";
import { userMessage } from "@/lib/errors";

interface ModelDocument {
  id: number;
  name: string;
  kind: "markdown" | "pdf" | "other";
  body?: string | null;
  filename?: string | null;
}

interface ModelFile {
  id: number;
  file_type: string;
  original_filename: string;
  thumbnail_url?: string;
}

interface ModelData {
  files: ModelFile[];
}

export function DocsTab({ modelId }: { modelId: number }) {
  const [docs, setDocs] = useState<ModelDocument[]>([]);
  const [imageFiles, setImageFiles] = useState<ModelFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openDocId, setOpenDocId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      getJson<ModelDocument[]>(`/api/v1/models/${modelId}/documents`),
      getJson<ModelData>(`/api/v1/models/${modelId}`),
    ])
      .then(([docItems, modelData]) => {
        if (!cancelled) {
          setDocs(docItems);
          if (docItems.length > 0) setOpenDocId(docItems[0].id);
          // Collect image files (plate previews, thumbnails from 3MF)
          const imgs = (modelData.files || []).filter(
            (f) => f.file_type === "image"
          );
          setImageFiles(imgs);
        }
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
  const hasImages = imageFiles.length > 0;

  if (!hasDocs && !hasImages) {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-center">
        <FileText className="h-8 w-8 text-on-surface-variant/40" />
        <div>
          <p className="text-sm font-medium text-on-surface">
            No documentation
          </p>
          <p className="text-xs text-on-surface-variant mt-1">
            Upload a README or manual to this model's collection to see it
            here.
          </p>
        </div>
      </div>
    );
  }

  const activeDoc = docs.find((d) => d.id === openDocId) ?? docs[0];

  return (
    <div className="space-y-4">
      {/* Document tabs */}
      {docs.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {docs.map((doc) => (
            <button
              key={doc.id}
              type="button"
              onClick={() => setOpenDocId(doc.id)}
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
      {hasDocs && (
        <>
          {activeDoc.kind === "markdown" && activeDoc.body ? (
            <div className="rounded-lg border border-outline-variant bg-surface-container-low p-4 md:p-6">
              <MarkdownView source={activeDoc.body} />
            </div>
          ) : activeDoc.kind === "pdf" || activeDoc.filename ? (
            <div className="rounded-lg border border-outline-variant bg-surface-container-low p-4 md:p-6">
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
            </div>
          ) : (
            <div className="rounded-lg border border-outline-variant bg-surface-container-low p-4 md:p-6">
              <p className="text-sm text-on-surface-variant">
                No preview available.
              </p>
            </div>
          )}
        </>
      )}

      {/* Image gallery — plate previews from 3MF */}
      {hasImages && (
        <div>
          <h3 className="text-sm font-medium text-on-surface mb-3 flex items-center gap-2">
            <ImageIcon className="h-4 w-4 text-on-surface-variant" />
            Plate Previews
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {imageFiles
              .filter(
                (f) =>
                  f.original_filename &&
                  (f.original_filename.startsWith("plate_") ||
                    f.original_filename.startsWith("top_") ||
                    f.original_filename.startsWith("pick_") ||
                    f.original_filename.startsWith("thumbnail_") ||
                    f.original_filename.endsWith(".png"))
              )
              .map((img) => (
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
      )}
    </div>
  );
}
