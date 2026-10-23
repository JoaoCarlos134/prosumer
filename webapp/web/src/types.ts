// The JSON of `prosumer.app.Result.to_dict()` (docs/library/app.md in the library). Timestamps are ISO text
// in the site's time zone; tables are lists of records; NaN arrives as null.

export type Lang = "en" | "pt";
export type Quantity = "generation" | "consumption";
export type Num = number | null;

export interface Site {
  latitude: number;
  longitude: number;
  timezone: string;
  address_found: string | null;
}

export interface ReadInfo {
  file: string;
  how: string;
  hours: number;
  start: string;
  end: string;
  measured: number;
  series: string[];
}

export interface OutlookHour {
  unique_id: string;
  ds: string;
  lead_day: number;
  y_hat: Num;
  low: Num;
  high: Num;
  source: string;
  n_models: number;
  trust: Num;
  skill: Num;
  sun: boolean;
}

export interface OutlookDay {
  unique_id: string;
  date: string;
  lead_day: number;
  total: Num;
  low: Num;
  high: Num;
  source: string;
  n_models: number;
  trust: Num;
  skill: Num;
  confidence: string;
  missing_hours: number;
}

export interface PlantMethod {
  tilt?: number;
  azimuth?: number;
  orientation?: string;
  kw_eff?: number;
  kw_eff_from?: string;
  clear_days_used?: number;
  clearness?: Record<string, { median: number; from: string }>;
}

export interface Outlook {
  quantity: Quantity;
  unit: string;
  hourly: OutlookHour[];
  daily: OutlookDay[];
  method: {
    site?: [number, number];
    trust?: number[];
    skill?: number[];
    series?: Record<string, PlantMethod>;
    rule?: string;
    weeks?: number;
  };
  notes: string[];
}

export interface Window {
  unique_id: string;
  date: string;
  start: string;
  end: string;
  energy: Num;
  confidence: string | null;
}

export interface CostWindow {
  unique_id: string;
  date: string;
  start: string;
  end: string;
  cost: Num;
  grid_kwh: Num;
  pv_kwh: Num;
  rank: number;
  confidence: string | null;
  currency: string;
  tariff: string;
}

export interface ForecastRow {
  forecast: string;
  regime: string;
  skill: Num;
  skill_ci_low: Num;
  skill_ci_high: Num;
  nRMSE: Num;
  MBE: Num;
  R2: Num;
  R2_daily: Num;
}

export interface ResolutionRow {
  forecast: string;
  level: string;
  blocks: number;
  skill: Num;
  R2: Num;
  R2_reference: Num;
  nRMSE: Num;
  MBE: Num;
}

export interface QualityRow {
  series: string;
  first: string;
  last_valid: string;
  steps: number;
  coverage: Num;
  gaps: number;
  longest_gap_h: Num;
}

export interface ClockRow {
  unique_id: string;
  period: string;
  offset_h: Num;
  centroid_shift_h: Num;
  score: Num;
  score_zero: Num;
  days: number;
  agreement: Num;
  confident: boolean;
}

export interface ProvenanceRow {
  role: string;
  name: string;
  license: string;
  sends_data: boolean;
  source: string;
  citation: string;
  url: string;
  retrieved: string;
  conditions: string;
}

export interface Diagnostics {
  // reliable: the roof is good enough for steps, a trend and a loss to be reported (given, or a good fit)
  orientation: { unique_id: string; tilt: Num; azimuth: Num; r2: Num; edge: boolean; reliable: boolean }[];
  segments: {
    unique_id: string;
    start: string;
    end: string;
    days: number;
    level_start: Num;
    level_end: Num;
    trend_pct_per_year: Num;
    lost_pct: Num;
    trend_reported: boolean; // the library's notes report this period's trend (its last one only)
    loss_reported: boolean;
  }[];
  steps: { unique_id: string; date: string; before: Num; after: Num; step_pct: Num; event: string }[];
  kwp: Record<string, number>;
  notes: string[];
}

// the monthly bill: the common columns; a Brazilian bill has more (charges, flag, credits...)
export interface BillMonth {
  unique_id: string;
  month: string;
  coverage: Num;
  consumption: Num;
  generation: Num;
  self_consumption: Num;
  grid_import: Num;
  export: Num;
  total: Num;
  without_pv: Num;
  savings: Num;
  [column: string]: string | number | boolean | null;
}

export interface BillTotals {
  unique_id: string;
  months: number;
  complete_months: number;
  consumption: Num;
  generation: Num;
  grid_import: Num;
  export: Num;
  total: Num;
  without_pv: Num;
  savings: Num;
  mean_month: Num;
}

export interface Economics {
  tariff: string;
  scheme: string;
  currency: string;
  monthly: BillMonth[];
  by_block: { unique_id: string; month: string; block: string; grid_import: Num; export: Num; compensated?: Num }[];
  totals: BillTotals[];
  notes: string[];
  provenance: ProvenanceRow[] | null;
}

export interface Report {
  summary: {
    quantity: Quantity;
    unit: string;
    tz: string;
    freq: string;
    n_series: number;
    start: string;
    end: string;
    test_start?: string;
    test_end?: string;
    issue_hour?: number;
    test_windows?: number;
    reference?: string;
    output?: string;
  };
  quality: QualityRow[];
  notes: string[];
  forecast: ForecastRow[] | null;
  resolution: ResolutionRow[] | null;
  clock: ClockRow[] | null;
  provenance: ProvenanceRow[] | null;
  diagnostics: Diagnostics | null;
  economics: Economics | null;
  pending: Record<string, string>;
}

export interface HistoryDay {
  unique_id: string;
  date: string;
  energy: Num;
  measured_hours: number;
}

export type CheckHour = { unique_id: string; ds: string; y: Num; evaluated: boolean } & Record<string, Num | string | boolean>;

export interface PerformanceDay {
  unique_id: string;
  date: string;
  energy: Num;
  expected: Num;
  index: Num;
}

export interface Credit {
  source: string;
  license: string;
  citation: string;
  url: string;
  retrieved: string | null;
  notes: string;
}

export interface Result {
  site: Site;
  read: Partial<Record<Quantity, ReadInfo>>;
  outlooks: Partial<Record<Quantity, Outlook>>;
  windows: Window[];
  windows_by_cost: CostWindow[] | null;
  pricing: string | null;
  charts: {
    history_generation?: HistoryDay[];
    history_consumption?: HistoryDay[];
    check?: CheckHour[];
    performance?: PerformanceDay[];
  };
  report: Report;
  notes: string[];
  log: string[];
  credits: Credit[];
}

export interface Payload {
  id: string;
  lang: Lang;
  meta: {
    demo: boolean;
    files: Partial<Record<Quantity, string>>;
    seconds: number;
    request: Record<string, unknown>;
    source?: DemoInfo;
  };
  result: Result;
}

export interface DemoInfo {
  name: string;
  place: string;
  license: string;
  citation: string;
  url: string;
}

export interface Info {
  version: string;
  languages: Lang[];
  max_days: number;
  models: { sets: string[]; lightgbm: boolean; foundation: string[] };
  price_kinds: string[];
  schemes: string[];
  brazil: { connections: string[]; gd: string[]; modalities: string[]; gd_i_requested_by: string };
  read_kinds: string[];
  demo: DemoInfo;
}
