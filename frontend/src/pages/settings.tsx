import { SettingsPanel } from "@/components/settings-panel";

export default function SettingsPage() {
  return (
    <div className="h-full overflow-y-auto [scrollbar-gutter:stable] bg-background p-6 pb-24 md:pb-6">
      <div className="mx-auto w-full max-w-6xl">
        <SettingsPanel />
      </div>
    </div>
  );
}
