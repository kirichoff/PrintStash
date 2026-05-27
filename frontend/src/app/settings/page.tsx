import { SettingsPanel } from "@/components/settings-panel";

export const metadata = {
  title: "Settings — PrintStash",
};

export default function SettingsPage() {
  return (
    <div className="h-full overflow-y-auto p-6">
      <SettingsPanel />
    </div>
  );
}
