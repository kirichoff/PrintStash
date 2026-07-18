import { getJson } from "@/lib/api/request";
import type { PlateLayoutRead } from "@/types";

/** Fetch the per-plate layout for a 3MF file (objects + bed placement). */
export function getPlateLayout(fileId: number): Promise<PlateLayoutRead> {
  return getJson<PlateLayoutRead>(`/api/v1/files/${fileId}/plates`);
}
