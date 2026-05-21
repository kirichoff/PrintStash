import { UploadForm } from "@/components/upload-form";

export const metadata = {
  title: "Upload — Nexus3D Vault",
};

export default function UploadPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Upload</h1>
        <p className="text-muted-foreground">
          Manually push a G-code, STL, or 3MF file into the vault.
        </p>
      </div>
      <UploadForm />
    </div>
  );
}
