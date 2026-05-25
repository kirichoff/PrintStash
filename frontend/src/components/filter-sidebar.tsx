"use client";

import { useEffect, useMemo, useState } from "react";
import { CategoryRead, TagRead } from "@/types";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronRight, X } from "lucide-react";

interface CategoryNode {
  cat: CategoryRead;
  children: CategoryNode[];
}

function buildTree(cats: CategoryRead[]): CategoryNode[] {
  const byId = new Map<number, CategoryNode>();
  for (const c of cats) byId.set(c.id, { cat: c, children: [] });
  const roots: CategoryNode[] = [];
  for (const node of byId.values()) {
    if (node.cat.parent_id == null) {
      roots.push(node);
    } else {
      const parent = byId.get(node.cat.parent_id);
      if (parent) parent.children.push(node);
      else roots.push(node);
    }
  }
  const sortRec = (nodes: CategoryNode[]) => {
    nodes.sort((a, b) => a.cat.name.localeCompare(b.cat.name));
    nodes.forEach((n) => sortRec(n.children));
  };
  sortRec(roots);
  return roots;
}

function CategoryNodeRow({
  node,
  depth,
  selected,
  onSelect,
  expanded,
  toggle,
}: {
  node: CategoryNode;
  depth: number;
  selected: string | null;
  onSelect: (path: string | null) => void;
  expanded: Set<string>;
  toggle: (path: string) => void;
}) {
  const isOpen = expanded.has(node.cat.path);
  const isSelected = selected === node.cat.path;
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <div
        className={`flex items-center justify-between rounded-lg py-1.5 cursor-pointer transition-colors ${
          isSelected
            ? "bg-[var(--secondary-container)] text-[var(--on-secondary-container)] font-medium"
            : "text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-low)] hover:text-[var(--on-surface)]"
        }`}
        style={{ paddingLeft: `${depth * 12 + 12}px`, paddingRight: "4px" }}
      >
        <div className="flex items-center gap-1 flex-1 min-w-0">
          {hasChildren ? (
            <button
              type="button"
              onClick={() => toggle(node.cat.path)}
              className="rounded p-0.5 hover:bg-[var(--surface-container-high)] flex-shrink-0"
              aria-label={isOpen ? "Collapse" : "Expand"}
            >
              <ChevronRight
                className={`h-3 w-3 transition-transform ${
                  isOpen ? "rotate-90" : ""
                }`}
              />
            </button>
          ) : (
            <span className="inline-block w-[18px] flex-shrink-0" />
          )}
          <button
            type="button"
            onClick={() => onSelect(isSelected ? null : node.cat.path)}
            className="flex flex-1 items-center justify-between gap-2 truncate text-left font-mono text-[13px]"
            title={node.cat.path}
          >
            <span className="truncate">{node.cat.name}</span>
          </button>
        </div>
        <span className="bg-[var(--surface-container)] px-1 rounded text-[10px] font-mono text-[var(--on-surface-variant)] mr-1">
          {node.cat.model_count}
        </span>
      </div>
      {isOpen &&
        node.children.map((child) => (
          <CategoryNodeRow
            key={child.cat.id}
            node={child}
            depth={depth + 1}
            selected={selected}
            onSelect={onSelect}
            expanded={expanded}
            toggle={toggle}
          />
        ))}
    </div>
  );
}

export function FilterSidebar({
  categories,
  tags,
  selectedCategory,
  selectedTags,
  onCategoryChange,
  onTagsChange,
  loading,
}: {
  categories: CategoryRead[];
  tags: TagRead[];
  selectedCategory: string | null;
  selectedTags: string[];
  onCategoryChange: (path: string | null) => void;
  onTagsChange: (tags: string[]) => void;
  loading?: boolean;
}) {
  const tree = useMemo(() => buildTree(categories), [categories]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!selectedCategory) return;
    const parts = selectedCategory.split("/");
    const ancestors = new Set<string>();
    for (let i = 1; i < parts.length; i++) {
      ancestors.add(parts.slice(0, i).join("/"));
    }
    setExpanded((prev) => {
      const next = new Set(prev);
      ancestors.forEach((a) => next.add(a));
      return next;
    });
  }, [selectedCategory]);

  function toggleTag(slug: string) {
    if (selectedTags.includes(slug)) {
      onTagsChange(selectedTags.filter((t) => t !== slug));
    } else {
      onTagsChange([...selectedTags, slug]);
    }
  }

  function toggleExpanded(path: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  if (loading) {
    return (
      <aside className="w-56 shrink-0 p-4 space-y-6">
        <Skeleton className="h-5 w-20" />
        <Skeleton className="h-36 w-full" />
        <Skeleton className="h-5 w-14" />
        <Skeleton className="h-28 w-full" />
      </aside>
    );
  }

  return (
    <aside className="w-56 shrink-0 overflow-y-auto border-r border-[var(--outline-variant)] bg-[var(--surface-container-lowest)] p-4 flex flex-col gap-5">
      {/* Categories */}
      <div>
        <h3 className="font-mono text-[10px] text-[var(--on-surface-variant)] tracking-wider uppercase mb-2">
          Categories
        </h3>
        <div className="flex flex-col gap-0.5">
          <button
            type="button"
            onClick={() => onCategoryChange(null)}
            className={`flex items-center justify-between px-3 py-1.5 rounded-lg font-mono text-[13px] transition-colors ${
              selectedCategory === null
                ? "bg-[var(--secondary-container)] text-[var(--on-secondary-container)] font-medium"
                : "text-[var(--on-surface-variant)] hover:bg-[var(--surface-container-low)] hover:text-[var(--on-surface)]"
            }`}
          >
            <span>All Models</span>
          </button>
          {tree.length === 0 ? (
            <p className="px-3 py-2 text-[11px] text-[var(--on-surface-variant)] font-mono">
              No categories yet.
            </p>
          ) : (
            tree.map((node) => (
              <CategoryNodeRow
                key={node.cat.id}
                node={node}
                depth={0}
                selected={selectedCategory}
                onSelect={onCategoryChange}
                expanded={expanded}
                toggle={toggleExpanded}
              />
            ))
          )}
        </div>
      </div>

      {/* Tags */}
      {tags.length > 0 && (
        <>
          <hr className="border-t border-[var(--outline-variant)]" />
          <div>
            <h3 className="font-mono text-[10px] text-[var(--on-surface-variant)] tracking-wider uppercase mb-2">
              Tags
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {tags.map((t) => {
                const active = selectedTags.includes(t.slug);
                return (
                  <button
                    type="button"
                    key={t.id}
                    onClick={() => toggleTag(t.slug)}
                    className={`flex items-center gap-1 px-2 py-1 rounded-lg font-mono text-[10px] tracking-wider uppercase border transition-colors ${
                      active
                        ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
                        : "border-[var(--outline-variant)] text-[var(--on-surface-variant)] hover:border-[var(--outline)] hover:bg-[var(--surface-container-low)]"
                    }`}
                  >
                    {t.name}
                    <span className="opacity-60">{t.model_count}</span>
                    {active && <X className="h-3 w-3 ml-0.5" />}
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}
    </aside>
  );
}
