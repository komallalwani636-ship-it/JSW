export interface ParseWarning {
  row: number;
  column: string;
  message: string;
}

export interface ParseSummary {
  total_rows: number;
  eligible_count: number;
  apl7_count: number;
  excluded_product: number;
  excluded_act_path: number;
  excluded_status: number;
  excluded_closed: number;
  parse_warnings: ParseWarning[];
}

export interface UploadResponse {
  upload_id: number;
  parse_summary: ParseSummary;
}

export interface CoilRecord {
  id: number;
  hr_coil_no: string;
  thk: number | null;
  wdt: number | null;
  wgt: number | null;
  grade: string | null;
  age_hours: number | null;
  status: string | null;
  product: string | null;
  silicon_pct: number | null;
  silicon_band: string | null;
  is_apl7: boolean;
  all_columns: Record<string, unknown>;
}

export interface ViolationDetail {
  id: number;
  position_a: number;
  position_b: number;
  rule_type: string;
  detail: Record<string, unknown>;
}

export interface ScheduleItem {
  id: number;
  position: number;
  coil: CoilRecord;
  is_apl7: boolean;
}

export interface KpiResult {
  total_eligible: number;
  hrpo_count: number;
  hrpo_weight: number;
  hrspo_count: number;
  hrspo_weight: number;
  ngo_count: number;
  ngo_weight: number;
  age_gt_72h: number;
  age_gt_120h: number;
  age_gt_168h: number;
  violation_count: number;
  schedule_status: string;
  version_label: string;
}

export interface ScheduleSummary {
  id: number;
  version_label: string;
  status: string;
  generated_at: string;
  upload_file_id: number;
  kpi_snapshot: KpiResult | null;
  upload_filename?: string | null;
  generator_username?: string | null;
  is_deleted?: boolean;
  deleted_at?: string | null;
}

export interface ScheduleDetail extends ScheduleSummary {
  items: ScheduleItem[];
  violations: ViolationDetail[];
}

export interface AuditEvent {
  id: number;
  event_type: string;
  user_id: number;
  occurred_at: string;
  schedule_id: number | null;
  upload_file_id: number | null;
  detail: Record<string, unknown> | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface JwtPayload {
  sub: string;
  role: "planner" | "viewer";
  exp: number;
}
