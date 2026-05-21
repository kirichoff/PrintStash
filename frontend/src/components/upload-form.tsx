"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ingestOrca, ingestModel } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Upload, File, X, Loader2 } from "lucide-react";

const MESH_EXTENSIONS = [".stl", ".3mf", ".obj"];
const GCODE_EXTENSIONS = [".gcode", ".g", ".gco"];

function isMeshFile(filename: string): boolean {
  const ext = "." + filename.split(".").pop()?.toLowerCase();
  return MESH_EXTENSIONS.includes(ext);
}

function isGcodeFile(filename: string): boolean {
  const ext = "." + filename.split(".").pop()?.toLowerCase();
  return GCODE_EXTENSIONS.includes(ext);
}

export function UploadForm() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [modelName, setModelName] = useState("");
  const [category, setCategory] = useState("");
  const [tags, setTags] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    if (f && !modelName) {
      setModelName(f.name.replace(/\.[^/.]+$/, ""));
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !apiKey) return;
    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("model_name", modelName || file.name);
      if (category) formData.append("category", category);
      if (tags) formData.append("tags", tags);

      const isMesh = isMeshFile(file.name);
      const res = isMesh
        ? await ingestModel(formData, apiKey)
        : await ingestOrca(formData, apiKey);
      setJobId(res.job_id);
    } catch (err: any) {
      alert("Upload failed: " + err.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (jobId) {
    return (
      <Card className="max-w-xl mx-auto">
        <CardHeader>
          <CardTitle>Upload queued</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Your file is being processed in the background.
          </p>
          <div className="rounded-md bg-muted p-3 font-mono text-xs break-all">
            Job ID: {jobId}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setJobId(null)}>
              Upload another
            </Button>
            <Button asChild>
              <a href="/">View assets</a>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="max-w-xl mx-auto">
      <CardHeader>
        <CardTitle>Upload model</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div
            className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
              file ? "border-primary bg-primary/5" : "border-muted-foreground/25"
            }`}
          >
            {file ? (
              <div className="flex items-center gap-2">
                <File className="h-5 w-5 text-primary" />
                <span className="text-sm font-medium">{file.name}</span>
                <Badge variant="secondary" className="text-[10px]">
                  {isMeshFile(file.name) ? "mesh" : isGcodeFile(file.name) ? "gcode" : "file"}
                </Badge>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={() => setFile(null)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <>
                <Upload className="mb-2 h-8 w-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  Drag & drop or click to select a file
                </p>
              </>
            )}
            <input
              type="file"
              accept=".gcode,.g,.gco,.stl,.3mf,.obj"
              onChange={handleFileChange}
              className="mt-2 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-2 file:text-xs file:font-medium file:text-primary-foreground hover:file:bg-primary/90"
            />
          </div>

          <Separator />

          <div className="space-y-2">
            <label className="text-sm font-medium">Model name</label>
            <Input
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="e.g. Bracket v2"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Category</label>
              <Input
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="e.g. Functional"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Tags</label>
              <Input
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="comma, separated"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">
              API Key <Badge variant="destructive">required</Badge>
            </label>
            <Input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Your vault API key"
              required
            />
          </div>

          <Button
            type="submit"
            className="w-full"
            disabled={submitting || !file || !apiKey}
          >
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Uploading...
              </>
            ) : (
              "Upload to vault"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
