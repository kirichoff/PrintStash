export interface PlateObjectRead {
  plate: number;
  index: number;
  name: string | null;
  bbox_mm: [number, number, number];
  origin_mm: [number, number, number];
  stl_url: string;
}

export interface PlateRead {
  index: number;
  objects: PlateObjectRead[];
}

export interface PlateLayoutRead {
  file_id: number;
  plate_count: number;
  object_count: number;
  plates: PlateRead[];
}
