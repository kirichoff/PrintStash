"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { CategoryRead, TagRead } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronRight, FolderTree, Tag as TagIcon, X } from "lucide-react";

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
        className={`group flex items-center gap-1 rounded-md px-1 py-1 text-sm hover:bg-accent ${
          isSelected ? "bg-accent font-medium" : ""
        }`}
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={() => toggle(node.cat.path)}
            className="rounded p-0.5 hover:bg-muted"
            aria-label={isOpen ? "Collapse" : "Expand"}
          >
            <ChevronRight
              className={`h-3.5 w-3.5 transition-transform ${
                isOpen ? "rotate-90" : ""
              }`}
            />
          </button>
        ) : (
          <span className="inline-block w-4" />
        )}
        <button
          type="button"
          onClick={() => onSelect(isSelected ? null : node.cat.path)}
          className="flex flex-1 items-center justify-between gap-2 truncate text-left"
          title={node.cat.path}
        >
          <span className="truncate">{node.cat.name}</span>
          <span className="text-xs text-muted-foreground">
            {node.cat.model_count}
          </span>
        </button>
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

  // Auto-expand ancestors of the selected category.
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
      <div className="space-y-4">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  return (
    <aside className="space-y-6">
      <section>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <FolderTree className="h-4 w-4" /> Categories
          </h3>
          {selectedCategory && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs"
              onClick={() => onCategoryChange(null)}
            >
              Clear
            </Button>
          )}
        </div>
        <div className="rounded-md border bg-card p-2">
          <button
            type="button"
            onClick={() => onCategoryChange(null)}
            className={`flex w-full items-center justify-between rounded-md px-2 py-1 text-sm hover:bg-accent ${
              selectedCategory === null ? "bg-accent font-medium" : ""
            }`}
          >
            <span>All</span>
          </button>
          {tree.length === 0 ? (
            <p className="px-2 py-1 text-xs text-muted-foreground">
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
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <TagIcon className="h-4 w-4" /> Tags
          </h3>
          {selectedTags.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs"
              onClick={() => onTagsChange([])}
            >
              Clear
            </Button>
          )}
        </div>
        {tags.length === 0 ? (
          <p className="text-xs text-muted-foreground">No tags yet.</p>
        ) : (
          <div className="flex flex-wrap gap-1">
            {tags.map((t) => {
              const active = selectedTags.includes(t.slug);
              return (
                <button
                  type="button"
                  key={t.id}
                  onClick={() => toggleTag(t.slug)}
                  className="focus:outline-none"
                >
                  <Badge
                    variant={active ? "default" : "outline"}
                    className="cursor-pointer"
                  >
                    {t.name}
                    <span className="ml-1 opacity-70">{t.model_count}</span>
                    {active && <X className="ml-1 h-3 w-3" />}
                  </Badge>
                </button>
              );
            })}
          </div>
        )}
      </section>

      <section className="text-xs text-muted-foreground">
        <Link href="/printers" className="hover:underline">
          Manage printers →
        </Link>
      </section>
    </aside>
  );
}
