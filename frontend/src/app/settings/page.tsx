import { SettingsPanel } from "@/components/settings-panel";

export const metadata = {
  title: "Settings — Nexus3D Vault",
};

export default function SettingsPage() {
  return (
    <div className="h-full overflow-y-auto p-6">
      <SettingsPanel />
    </div>
  );
}
