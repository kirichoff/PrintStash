import { PrintersPage } from "@/components/printers-list";

export const revalidate = 0;

export default function Page() {
  return (
    <div className="h-full overflow-y-auto p-6">
      <PrintersPage />
    </div>
  );
}
