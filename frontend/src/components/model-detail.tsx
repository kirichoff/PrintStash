"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { ModelRead } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { STLViewer } from "@/components/stl-viewer";
import { SendToPrinterButton } from "@/components/send-to-printer";
import { deleteModel, getAssetUrl } from "@/lib/api";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Clock,
  Weight,
  Ruler,
  Printer,
  Layers,
  Download,
  Trash2,
  Box,
} from "lucide-react";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}h ${m}m ${s}s`;
}

export function ModelDetail({ model }: { model: ModelRead }) {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    if (!confirm("Delete this model? This cannot be undone.")) return;
    const key = prompt("Enter API key to confirm deletion:");
    if (!key) return;
    setDeleting(true);
    try {
      await deleteModel(model.id, key);
      router.push("/");
      router.refresh();
    } catch (e: any) {
      alert("Delete failed: " + e.message);
    } finally {
      setDeleting(false);
    }
  }

  const latestFile = model.files[model.files.length - 1];
  const meta = latestFile?.metadata;
  const meshFile = model.files.find((f) =>
    f.file_type === "stl" || f.file_type === "3mf" || f.file_type === "obj"
  );

  const thumbUrl = model.thumbnail_url
    ? getAssetUrl(model.thumbnail_url)
    : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Link>
        </Button>
        <div className="flex items-center gap-2">
          <SendToPrinterButton files={model.files} />
          <Button
            variant="destructive"
            size="sm"
            onClick={handleDelete}
            disabled={deleting}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            {deleting ? "Deleting..." : "Delete"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left column — thumbnail / 3D viewer */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <div className="aspect-video w-full bg-muted relative overflow-hidden rounded-t-lg">
              {thumbUrl ? (
                <img
                  src={thumbUrl}
                  alt={model.name}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                  <Printer className="h-16 w-16" />
                </div>
              )}
            </div>
            <CardHeader>
              <CardTitle className="text-2xl">{model.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {model.category && (
                  <Badge variant="secondary">{model.category}</Badge>
                )}
                {model.tags.map((tag) => (
                  <Badge key={tag} variant="outline">
                    {tag}
                  </Badge>
                ))}
              </div>
              {model.description && (
                <p className="text-muted-foreground">{model.description}</p>
              )}
            </CardContent>
          </Card>

          {meshFile && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">3D Preview</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="aspect-video w-full rounded-md border bg-muted">
                  <Suspense
                    fallback={
                      <div className="flex h-full items-center justify-center text-muted-foreground">
                        Loading viewer...
                      </div>
                    }
                  >
                    <STLViewer
                      url={getAssetUrl(`/api/v1/files/${meshFile.id}/stl`)}
                    />
                  </Suspense>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right column — metadata */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Print Profile</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <Printer className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="text-muted-foreground">Printer</span>
                <span className="ml-auto font-medium">
                  {meta?.printer_model ?? "—"}
                </span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Layers className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="text-muted-foreground">Layer height</span>
                <span className="ml-auto font-medium">
                  {meta?.layer_height_mm ? `${meta.layer_height_mm} mm` : "—"}
                </span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Ruler className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="text-muted-foreground">Nozzle</span>
                <span className="ml-auto font-medium">
                  {meta?.nozzle_diameter_mm
                    ? `${meta.nozzle_diameter_mm} mm`
                    : "—"}
                </span>
              </div>
              <Separator />
              <div className="flex items-center gap-2 text-sm">
                <Clock className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="text-muted-foreground">Est. time</span>
                <span className="ml-auto font-medium">
                  {formatDuration(meta?.estimated_time_s ?? null)}
                </span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Weight className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="text-muted-foreground">Filament</span>
                <span className="ml-auto font-medium">
                  {meta?.filament_weight_g
                    ? `${meta.filament_weight_g} g`
                    : "—"}
                </span>
              </div>
              {meta?.material_type && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Material</span>
                  <span className="ml-auto font-medium">
                    {meta.material_type}
                  </span>
                </div>
              )}
              {meta?.slicer_version && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Slicer</span>
                  <span className="ml-auto font-medium text-xs">
                    {meta.slicer_name} {meta.slicer_version}
                  </span>
                </div>
              )}
              {(meta?.bbox_x_mm || meta?.volume_mm3 || meta?.triangle_count) && (
                <>
                  <Separator />
                  <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    <Box className="h-4 w-4 shrink-0" />
                    Mesh Geometry
                  </div>
                  {meta?.bbox_x_mm && meta?.bbox_y_mm && meta?.bbox_z_mm && (
                    <div className="flex items-center gap-2 text-sm">
                      <Ruler className="h-4 w-4 text-muted-foreground shrink-0" />
                      <span className="text-muted-foreground">Dimensions</span>
                      <span className="ml-auto font-medium">
                        {meta.bbox_x_mm} × {meta.bbox_y_mm} × {meta.bbox_z_mm} mm
                      </span>
                    </div>
                  )}
                  {meta?.volume_mm3 && (
                    <div className="flex items-center gap-2 text-sm">
                      <Weight className="h-4 w-4 text-muted-foreground shrink-0" />
                      <span className="text-muted-foreground">Volume</span>
                      <span className="ml-auto font-medium">
                        {meta.volume_mm3 < 1000
                          ? `${meta.volume_mm3.toFixed(1)} mm³`
                          : `${(meta.volume_mm3 / 1000).toFixed(2)} cm³`}
                      </span>
                    </div>
                  )}
                  {meta?.triangle_count && (
                    <div className="flex items-center gap-2 text-sm">
                      <Layers className="h-4 w-4 text-muted-foreground shrink-0" />
                      <span className="text-muted-foreground">Triangles</span>
                      <span className="ml-auto font-medium">
                        {meta.triangle_count.toLocaleString()}
                      </span>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Files</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {model.files.map((file) => (
                <div
                  key={file.id}
                  className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                >
                  <div className="flex items-center gap-2 overflow-hidden">
                    <Badge
                      variant="outline"
                      className="shrink-0 text-[10px] uppercase"
                    >
                      {file.file_type}
                    </Badge>
                    <span className="truncate">{file.original_filename}</span>
                    <span className="text-xs text-muted-foreground shrink-0">
                      v{file.version}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-muted-foreground hidden sm:inline">
                      {formatBytes(file.size_bytes)}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      asChild
                    >
                      <a
                        href={getAssetUrl(
                          `/api/v1/files/${file.id}/download`
                        )}
                        download={file.original_filename}
                      >
                        <Download className="h-4 w-4" />
                      </a>
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
