"use client";

import { useEffect, useState } from "react";
import { CategoryRead, TagRead } from "@/types";
import {
  listCategories,
  listTags,
  createCategory,
  createTag,
  deleteCategory,
  deleteTag,
} from "@/lib/api";
import { Plus, X, FolderTree, Tag as TagIcon } from "lucide-react";

export function TaxonomyManager() {
  const [categories, setCategories] = useState<CategoryRead[]>([]);
  const [tags, setTags] = useState<TagRead[]>([]);
  const [newCat, setNewCat] = useState("");
  const [newTag, setNewTag] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      const [c, t] = await Promise.all([listCategories(), listTags()]);
      setCategories(c);
      setTags(t);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function handleCreateCategory() {
    const name = newCat.trim();
    if (!name) return;
    try {
      await createCategory({ name });
      setNewCat("");
      refresh();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleDeleteCategory(id: number) {
    try {
      await deleteCategory(id);
      refresh();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleCreateTag() {
    const name = newTag.trim();
    if (!name) return;
    try {
      await createTag({ name });
      setNewTag("");
      refresh();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleDeleteTag(id: number) {
    try {
      await deleteTag(id);
      refresh();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <div className="space-y-8">
      {error && (
        <div className="rounded border border-[var(--error)]/30 bg-[var(--error-container)]/20 p-3 text-xs text-[var(--error)] font-mono">
          {error}
        </div>
      )}

      {/* Categories */}
      <div className="bg-[var(--surface-container-lowest)] border border-[var(--outline-variant)] rounded overflow-hidden">
        <div className="px-6 py-4 border-b border-[var(--outline-variant)] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FolderTree className="h-4 w-4 text-[var(--on-surface-variant)]" />
            <h3 className="text-sm font-semibold text-[var(--on-surface)]">
              Categories
            </h3>
            <span className="font-mono text-xs text-[var(--on-surface-variant)]">
              ({categories.length})
            </span>
          </div>
          <form
            onSubmit={(e) => { e.preventDefault(); handleCreateCategory(); }}
            className="flex items-center gap-2"
          >
            <input
              value={newCat}
              onChange={(e) => setNewCat(e.target.value)}
              placeholder="New category..."
              className="bg-[var(--surface-container-lowest)] text-[var(--on-surface)] font-mono text-xs border border-[var(--outline-variant)] rounded px-3 py-[6px] w-40 focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent"
            />
            <button
              type="submit"
              disabled={!newCat.trim()}
              className="p-1.5 rounded bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          </form>
        </div>

        <div className="p-4">
          {loading ? (
            <p className="text-xs text-[var(--on-surface-variant)] font-mono">Loading...</p>
          ) : categories.length === 0 ? (
            <p className="text-xs text-[var(--on-surface-variant)] font-mono">
              No categories yet. Create one above.
            </p>
          ) : (
            <div className="space-y-1">
              {categories.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-[var(--surface-container-low)] group"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm text-[var(--on-surface)] truncate">
                      {c.name}
                    </span>
                    <span className="font-mono text-[10px] text-[var(--on-surface-variant)] truncate">
                      {c.path}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs text-[var(--on-surface-variant)]">
                      {c.model_count} models
                    </span>
                    <button
                      onClick={() => {
                        if (c.model_count > 0) {
                          alert("Cannot delete: category has models assigned.");
                          return;
                        }
                        handleDeleteCategory(c.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-[var(--error-container)]/30 text-[var(--error)]"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Tags */}
      <div className="bg-[var(--surface-container-lowest)] border border-[var(--outline-variant)] rounded overflow-hidden">
        <div className="px-6 py-4 border-b border-[var(--outline-variant)] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TagIcon className="h-4 w-4 text-[var(--on-surface-variant)]" />
            <h3 className="text-sm font-semibold text-[var(--on-surface)]">
              Tags
            </h3>
            <span className="font-mono text-xs text-[var(--on-surface-variant)]">
              ({tags.length})
            </span>
          </div>
          <form
            onSubmit={(e) => { e.preventDefault(); handleCreateTag(); }}
            className="flex items-center gap-2"
          >
            <input
              value={newTag}
              onChange={(e) => setNewTag(e.target.value)}
              placeholder="New tag..."
              className="bg-[var(--surface-container-lowest)] text-[var(--on-surface)] font-mono text-xs border border-[var(--outline-variant)] rounded px-3 py-[6px] w-40 focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent"
            />
            <button
              type="submit"
              disabled={!newTag.trim()}
              className="p-1.5 rounded bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          </form>
        </div>

        <div className="p-4">
          {loading ? (
            <p className="text-xs text-[var(--on-surface-variant)] font-mono">Loading...</p>
          ) : tags.length === 0 ? (
            <p className="text-xs text-[var(--on-surface-variant)] font-mono">
              No tags yet. Create one above.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {tags.map((t) => (
                <span
                  key={t.id}
                  className="inline-flex items-center gap-1.5 bg-[var(--surface-container)] text-[var(--on-surface)] px-2.5 py-1.5 rounded font-mono text-xs uppercase tracking-wider group"
                >
                  {t.name}
                  <span className="text-[10px] text-[var(--on-surface-variant)]">
                    ({t.model_count})
                  </span>
                  <button
                    onClick={() => handleDeleteTag(t.id)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:text-[var(--error)]"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
