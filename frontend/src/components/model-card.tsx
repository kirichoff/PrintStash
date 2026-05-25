"use client";

import Link from "next/link";
import { memo } from "react";
import { ModelListItem } from "@/types";
import { FileText, MoreVertical } from "lucide-react";
import { getAssetUrl } from "@/lib/api";

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function ModelCardInner({ model }: { model: ModelListItem }) {
  const thumb = model.thumbnail_url
    ? getAssetUrl(model.thumbnail_url)
    : null;

  return (
    <Link
      href={`/models/${model.id}`}
      className="block group"
      style={{ contentVisibility: "auto", containIntrinsicSize: "320px" } as React.CSSProperties}
    >
      <article className="bg-[var(--surface-container-lowest)] border border-[var(--outline-variant)] rounded hover:shadow-[0_4px_12px_rgba(0,0,0,0.05)] hover:border-[var(--primary)] transition-all duration-200 flex flex-col overflow-hidden h-full">
        <div className="aspect-[4/3] bg-[var(--surface-container-low)] relative border-b border-[var(--outline-variant)] overflow-hidden flex items-center justify-center p-4">
          {model.file_count > 0 && (
            <div className="absolute top-2 right-2 bg-[var(--surface-container-lowest)] border border-[var(--outline-variant)] px-[6px] py-[2px] rounded flex items-center gap-1 z-10">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="font-mono text-[9px] text-[var(--on-surface)] uppercase tracking-wider leading-none">
                {model.file_count} file{model.file_count !== 1 ? "s" : ""}
              </span>
            </div>
          )}

          {thumb ? (
            <img
              src={thumb}
              alt={model.name}
              className="h-full w-full object-cover group-hover:scale-105 transition-transform duration-500"
              loading="lazy"
              decoding="async"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-[var(--on-surface-variant)]">
              <FileText className="h-12 w-12 opacity-30" />
            </div>
          )}
        </div>

        <div className="p-4 flex flex-col gap-1 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3
              className="text-[15px] font-semibold text-[var(--on-surface)] truncate leading-tight"
              title={model.name}
            >
              {model.name}
            </h3>
            <MoreVertical className="h-[18px] w-[18px] text-[var(--on-surface-variant)] opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-0.5" />
          </div>

          <div className="mt-auto pt-2 flex items-center justify-between border-t border-[var(--surface-variant)]">
            <div className="flex gap-1.5">
              {model.category && (
                <span className="bg-[var(--surface-container)] text-[var(--on-surface)] px-1.5 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider">
                  {model.category}
                </span>
              )}
              {model.tags.slice(0, 2).map((tag) => (
                <span
                  key={tag}
                  className="bg-[var(--surface-container)] text-[var(--on-surface)] px-1.5 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider"
                >
                  {tag}
                </span>
              ))}
            </div>
            <span className="font-mono text-[11px] text-[var(--on-surface-variant)]">
              {timeAgo(model.updated_at)}
            </span>
          </div>
        </div>
      </article>
    </Link>
  );
}

export const ModelCard = memo(ModelCardInner);

