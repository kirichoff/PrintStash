"use client";

import Link from "next/link";
import { ModelListItem } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FileText } from "lucide-react";
import { getAssetUrl } from "@/lib/api";

export function ModelCard({ model }: { model: ModelListItem }) {
  const thumb = model.thumbnail_url
    ? getAssetUrl(model.thumbnail_url)
    : null;

  return (
    <Link href={`/models/${model.id}`} className="block h-full">
      <Card className="h-full overflow-hidden transition-shadow hover:shadow-md">
        <div className="aspect-video w-full bg-muted relative overflow-hidden">
          {thumb ? (
            <img
              src={thumb}
              alt={model.name}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-muted-foreground">
              <FileText className="h-10 w-10" />
            </div>
          )}
        </div>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg truncate">{model.name}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="flex flex-wrap gap-1">
              {model.category && (
                <Badge variant="secondary" className="text-xs">
                  {model.category}
                </Badge>
              )}
              {model.tags.slice(0, 2).map((tag) => (
                <Badge key={tag} variant="outline" className="text-xs">
                  {tag}
                </Badge>
              ))}
            </div>
            <span className="text-xs text-muted-foreground">
              {model.file_count} file{model.file_count !== 1 ? "s" : ""}
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
