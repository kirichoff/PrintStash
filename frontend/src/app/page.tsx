import { ModelBrowser } from "@/components/model-grid";

export const revalidate = 0;

export default function HomePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Assets</h1>
        <p className="text-muted-foreground">
          Browse your 3D models, sliced jobs, and print profiles.
        </p>
      </div>
      <ModelBrowser />
    </div>
  );
}
