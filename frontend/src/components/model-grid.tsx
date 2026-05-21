"use client";

import { useEffect, useState } from "react";
import { CategoryRead, ModelListItem, TagRead } from "@/types";
import { ModelCard } from "@/components/model-card";
import { FilterSidebar } from "@/components/filter-sidebar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Search } from "lucide-react";
import { listCategories, listModels, listTags } from "@/lib/api";

export function ModelBrowser() {
  const [models, setModels] = useState<ModelListItem[]>([]);
  const [categories, setCategories] = useState<CategoryRead[]>([]);
  const [tags, setTags] = useState<TagRead[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [facetsLoading, setFacetsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load facets once.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [c, t] = await Promise.all([listCategories(), listTags()]);
        if (!alive) return;
        setCategories(c);
        setTags(t);
      } catch (e: any) {
        if (alive) setError(e.message);
      } finally {
        if (alive) setFacetsLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  // Reload models whenever filters change (with debounce for query).
  useEffect(() => {
    let alive = true;
    const handle = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await listModels({
          limit: 500,
          category: selectedCategory ?? undefined,
          tag: selectedTags.length ? selectedTags : undefined,
          q: query.trim() || undefined,
        });
        if (!alive) return;
        setModels(data);
        setError(null);
      } catch (e: any) {
        if (alive) setError(e.message);
      } finally {
        if (alive) setLoading(false);
      }
    }, 200);
    return () => {
      alive = false;
      clearTimeout(handle);
    };
  }, [selectedCategory, selectedTags, query]);

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[240px_1fr]">
      <FilterSidebar
        categories={categories}
        tags={tags}
        selectedCategory={selectedCategory}
        selectedTags={selectedTags}
        onCategoryChange={setSelectedCategory}
        onTagsChange={setSelectedTags}
        loading={facetsLoading}
      />

      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search models..."
              className="pl-8"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <Button variant="outline" asChild>
            <a href="/upload">Upload</a>
          </Button>
        </div>

        {error && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {loading ? (
          <ModelGridSkeleton />
        ) : models.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <p className="text-lg font-medium">No models found</p>
            <p className="text-sm">
              {query || selectedCategory || selectedTags.length
                ? "Try clearing some filters."
                : "Upload your first model to get started."}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {models.map((model) => (
              <ModelCard key={model.id} model={model} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function ModelGridSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="aspect-video w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      ))}
    </div>
  );
}
