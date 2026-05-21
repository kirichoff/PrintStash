import { notFound } from "next/navigation";
import { getModel } from "@/lib/api";
import { ModelDetail } from "@/components/model-detail";

export const revalidate = 0;

export default async function ModelPage({
  params,
}: {
  params: { id: string };
}) {
  const id = parseInt(params.id, 10);
  if (isNaN(id)) {
    notFound();
  }

  let model;
  try {
    model = await getModel(id);
  } catch {
    notFound();
  }

  return <ModelDetail model={model} />;
}
