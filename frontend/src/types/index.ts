export interface MetadataRead {
  slicer_name: string | null;
  slicer_version: string | null;
  printer_model: string | null;
  nozzle_diameter_mm: number | null;
  layer_height_mm: number | null;
  infill_percent: number | null;
  estimated_time_s: number | null;
  filament_weight_g: number | null;
  filament_length_mm: number | null;
  filament_cost: number | null;
  material_type: string | null;
  material_brand: string | null;
  bbox_x_mm: number | null;
  bbox_y_mm: number | null;
  bbox_z_mm: number | null;
  volume_mm3: number | null;
  triangle_count: number | null;
}

export interface FileRead {
  id: number;
  model_id: number;
  original_filename: string;
  file_type: "stl" | "3mf" | "gcode" | "obj";
  version: number;
  size_bytes: number;
  sha256: string;
  uploaded_at: string;
  metadata: MetadataRead | null;
}

export interface ModelRead {
  id: number;
  name: string;
  slug: string;
  hash: string;
  category: string | null;
  category_id: number | null;
  description: string | null;
  tags: string[];
  thumbnail_url: string | null;
  created_at: string;
  updated_at: string;
  files: FileRead[];
}

export interface ModelListItem {
  id: number;
  name: string;
  slug: string;
  category: string | null;
  category_id: number | null;
  tags: string[];
  thumbnail_url: string | null;
  file_count: number;
  updated_at: string;
}

export interface ModelUpdate {
  name?: string;
  description?: string;
  category?: string;
  tags?: string[];
}

export interface IngestResponse {
  job_id: string;
  state: "pending" | "running" | "completed" | "failed";
  message: string;
}

export interface IngestJobStatus {
  job_id: string;
  state: "pending" | "running" | "completed" | "failed";
  model_id: number | null;
  file_id: number | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface ListModelsParams {
  category?: string;
  tag?: string[];
  q?: string;
  limit?: number;
  offset?: number;
}

export interface CategoryCreate {
  name: string;
  parent_id?: number | null;
}

export interface TagCreate {
  name: string;
}

export interface CategoryRead {
  id: number;
  name: string;
  slug: string;
  path: string;
  parent_id: number | null;
  model_count: number;
}

export interface TagRead {
  id: number;
  name: string;
  slug: string;
  model_count: number;
}

export type PrinterStatus =
  | "unknown"
  | "offline"
  | "ready"
  | "printing"
  | "paused"
  | "error";

export type PrintJobState =
  | "queued"
  | "uploading"
  | "started"
  | "printing"
  | "paused"
  | "completed"
  | "cancelled"
  | "failed";

export interface PrinterRead {
  id: number;
  name: string;
  moonraker_url: string;
  has_api_key: boolean;
  notes: string | null;
  status: PrinterStatus;
  last_seen_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface PrinterCreate {
  name: string;
  moonraker_url: string;
  api_key?: string;
  notes?: string;
}

export interface PrinterUpdate {
  name?: string;
  moonraker_url?: string;
  api_key?: string;
  notes?: string;
}

export interface PrintJobRead {
  id: number;
  printer_id: number;
  file_id: number;
  model_id: number;
  remote_filename: string;
  state: PrintJobState;
  progress: number;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SendToPrinter {
  file_id: number;
  start_print?: boolean;
  remote_filename?: string;
}

/** Loose typing for the Moonraker objects snapshot kept by the hub. */
export interface PrinterSnapshot {
  print_stats?: {
    state?: string;
    filename?: string;
    print_duration?: number;
    total_duration?: number;
    message?: string;
  };
  virtual_sdcard?: {
    progress?: number;
    file_position?: number;
    file_size?: number;
  };
  extruder?: { temperature?: number; target?: number };
  heater_bed?: { temperature?: number; target?: number };
  toolhead?: { position?: number[]; homed_axes?: string };
  webhooks?: { state?: string; state_message?: string };
  [k: string]: any;
}

export interface PrinterStatusResponse {
  printer: PrinterRead;
  snapshot: PrinterSnapshot;
}

// -- Auth --------------------------------------------------------------------

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserRead {
  id: number;
  username: string;
  email: string | null;
  is_superuser: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// -- First-run setup ---------------------------------------------------------

export interface SetupStatus {
  configured: boolean;
  user_count: number;
  default_data_dir: string;
  default_thumb_dir: string;
  current_data_dir: string;
  current_thumb_dir: string;
  configured_at: string | null;
}

export interface SetupRequest {
  username: string;
  password: string;
  email?: string;
  data_dir?: string;
  thumb_dir?: string;
}

export interface SetupResponse {
  configured: boolean;
  user_id: number;
  username: string;
  data_dir: string;
  thumb_dir: string;
  access_token: string;
  token_type: string;
}

// -- Vault Configuration ----------------------------------------------------

export interface VaultConfigRead {
  storage_backend: string;
  data_dir: string;
  thumb_dir: string;
  s3_bucket: string;
  s3_endpoint_url: string;
  s3_region: string;
  s3_access_key: string;
  s3_secret_key: string;
  has_s3_access_key: boolean;
  has_s3_secret_key: boolean;
  backup_retention_days: number;
  backup_s3_bucket: string;
  backup_s3_endpoint_url: string;
  backup_s3_region: string;
  backup_s3_access_key: string;
  backup_s3_secret_key: string;
  has_backup_s3_access_key: boolean;
  has_backup_s3_secret_key: boolean;
  has_backup_s3: boolean;
}

export interface VaultConfigUpdate {
  storage_backend?: string;
  data_dir?: string;
  thumb_dir?: string;
  s3_bucket?: string;
  s3_endpoint_url?: string;
  s3_region?: string;
  s3_access_key?: string;
  s3_secret_key?: string;
  backup_retention_days?: number;
  backup_s3_bucket?: string;
  backup_s3_endpoint_url?: string;
  backup_s3_region?: string;
  backup_s3_access_key?: string;
  backup_s3_secret_key?: string;
}
