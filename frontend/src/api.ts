export type Perspective = "provider" | "customer";
export type AnalysisLevel = "groups" | "service_clusters" | "division_only" | "division_territory" | "territory_only";

export type Status = {
  ok: boolean;
  source: string;
  message?: string;
  rows?: number;
  source_rows?: number;
  overall_nps?: number;
  source_overall_nps?: number;
  blue_counts?: Record<string, number>;
  source_blue_counts?: Record<string, number>;
  service_cluster_non_null?: number;
  service_cluster_missing?: number;
  service_cluster_unique?: number;
  checks?: Record<string, boolean>;
  baseline_matches?: boolean;
};

export type SummaryRow = {
  group_name: string;
  group_code: string;
  ratings: number;
  nps: number;
  avg_criticality: number | null;
  dominant_frequency: string;
  busted: number;
  leveled: number;
  uplifted: number;
  exceptional: number;
  busted_pct: number;
  leveled_pct: number;
  uplifted_pct: number;
  exceptional_pct: number;
  raw_service_rows: number;
  unique_raw_service_texts: number;
  defined_service_clusters: number;
  attention_score: number;
  small_n: boolean;
  [key: string]: string | number | boolean | null;
};

export type HomeSummary = {
  status: Status;
  perspective: Perspective;
  tiles: Record<string, string | number | null>;
  rows: SummaryRow[];
};

export type AppSettings = {
  csv_source_path: string;
  default_csv_source_path: string;
  runtime_override: string | null;
  csv_exists: boolean;
  source_is_managed_copy?: boolean;
  imported_filename?: string;
  imported_rows?: number;
};

export type GroupProfile = {
  status: Status;
  group_name: string;
  is_synthetic?: boolean;
  profile_note?: string;
  source?: string;
  demographics?: DemographicChart[];
  received: Record<string, string | number | boolean | null>;
  gave: Record<string, string | number | boolean | null>;
  disparity: number | null;
  inter_intra: Record<string, string | number | boolean | null>;
  comparison: Array<Record<string, string | number | boolean | null>>;
};

export type DemographicRow = {
  label: string;
  count: number;
  pct: number;
};

export type DemographicChart = {
  key: string;
  title: string;
  column: string;
  total: number;
  rows: DemographicRow[];
};

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, cache: "no-store" });
  return parseResponse<T>(response);
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseResponse<T>(response);
}

export async function uploadFile<T>(path: string, file: File): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": file.type || "text/csv",
      "X-Filename": file.name,
    },
    body: file,
  });
  return parseResponse<T>(response);
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null) as { detail?: string } | null;
  if (!response.ok) {
    throw new Error(payload?.detail || `${response.status} ${response.statusText}`);
  }
  return payload as T;
}
