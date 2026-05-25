import { PrinterDetailPage } from "@/components/printer-detail";

export const revalidate = 0;

export default function Page({ params }: { params: { id: string } }) {
  return (
    <div className="h-full overflow-y-auto p-6">
      <PrinterDetailPage printerId={Number(params.id)} />
    </div>
  );
}
