import { PrinterDetailPage } from "@/components/printer-detail";

export const revalidate = 0;

export default function Page({ params }: { params: { id: string } }) {
  return <PrinterDetailPage printerId={Number(params.id)} />;
}
