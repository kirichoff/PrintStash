export const CUSTOM_SLICERS_STORAGE_KEY = "printstash.custom_slicers";

export interface CustomSlicer {
  name: string;
  scheme: string;
  types: string[]; // file extensions without dots: ["stl", "3mf", "gcode"]
}

export const DEFAULT_CUSTOM_SLICERS: CustomSlicer[] = [
  {
    name: "Snapmaker Orca",
    scheme: "snapmaker-orca",
    types: ["stl", "3mf", "obj", "step", "gcode"],
  },
];

export function readCustomSlicers(): CustomSlicer[] {
  if (typeof window === "undefined") return DEFAULT_CUSTOM_SLICERS;
  const raw = window.localStorage.getItem(CUSTOM_SLICERS_STORAGE_KEY);
  if (!raw) return DEFAULT_CUSTOM_SLICERS;
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.length === 0) return DEFAULT_CUSTOM_SLICERS;
    return parsed;
  } catch {
    return DEFAULT_CUSTOM_SLICERS;
  }
}

export function writeCustomSlicers(slicers: CustomSlicer[]): void {
  window.localStorage.setItem(
    CUSTOM_SLICERS_STORAGE_KEY,
    JSON.stringify(slicers),
  );
}
