"use client";

import { useEffect, useState } from "react";
import { FileText, Loader2 } from "lucide-react";

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

export function DocsTab({ modelId }: { modelId: number }) {
  const [docs, setDocs] = useState<ModelDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openDocId, setOpenDocId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getJson<ModelDocument[]>(`/api/v1/models/${modelId}/documents`)
      .then((items) => {
        if (!cancelled) {
          setDocs(items);
          if (items.length > 0) setOpenDocId(items[0].id);
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
    return (
      <p className="text-sm text-destructive py-4">{error}</p>
    );
  }

  if (docs.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-center">
        <FileText className="h-8 w-8 text-on-surface-variant/40" />
        <div>
          <p className="text-sm font-medium text-on-surface">No documentation</p>
          <p className="text-xs text-on-surface-variant mt-1">
            Upload a README or manual to this model's collection to see it here.
          </p>
        </div>
      </div>
    );
  }

  const activeDoc = docs.find((d) => d.id === openDocId) ?? docs[0];

  return (
    <div className="space-y-4">
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

      {activeDoc.kind === "markdown" && activeDoc.body ? (
        <div className="rounded-lg border border-outline-variant bg-surface-container-low p-4 md:p-6">
          <MarkdownView content={activeDoc.body} />
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
          <p className="text-sm text-on-surface-variant">No preview available.</p>
        </div>
      )}
    </div>
  );
}
