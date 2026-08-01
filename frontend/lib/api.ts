export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type HealthResponse = {
  status: string;
  db: string;
  detail?: string;
};

/** Matches the InputType literal on the backend. */
export type InputType =
  | "text"
  | "textarea"
  | "number"
  | "tel"
  | "date"
  | "datetime-local"
  | "file";

export type MissingField = {
  field: string;
  label: string;
  reason?: string | null;
  required: boolean;
  /** Which control to render. Older rows default to "text" server-side. */
  input_type: InputType;
  placeholder?: string | null;
  unit?: string | null;
};

export type ServiceCategory = {
  id: number;
  code: string;
  name: string;
};

/** Known shape of the mock provider output. Unknown keys stay accessible. */
export type ParsedDemand = {
  title?: string | null;
  summary?: string | null;
  category_code?: string | null;
  category_name?: string | null;
  service_type?: string | null;
  budget?: {
    amount?: number | null;
    currency?: string | null;
    note?: string | null;
  } | null;
  location?: {
    city?: string | null;
    district?: string | null;
    address?: string | null;
  } | null;
  urgency?: string | null;
  preferred_time?: string | null;
  contact?: { name?: string | null; phone?: string | null } | null;
  attachments?: string[] | null;
  keywords?: string[] | null;
  _meta?: {
    provider?: string | null;
    model?: string | null;
    confidence?: number | null;
    analyzed_at?: string | null;
  } | null;
} & Record<string, unknown>;

export type LifeTask = {
  id: number;
  user_id: number;
  category_id: number | null;
  category: ServiceCategory | null;
  status: string;
  raw_input: string | null;
  parsed_data: ParsedDemand;
  missing_fields: MissingField[];
  created_at: string;
  updated_at: string;
};

/** Error carrying the HTTP status so callers can react to 4xx vs 5xx. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readErrorMessage(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      // FastAPI validation errors.
      const first = body.detail[0] as { msg?: string } | undefined;
      if (first?.msg) return first.msg;
    }
  } catch {
    // Response had no JSON body.
  }
  return `HTTP ${res.status}`;
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/health`, {
    cache: "no-store",
    signal,
  });
  // 503 still carries a usable body, so parse before deciding.
  return (await res.json()) as HealthResponse;
}

export async function analyzeDemand(
  prompt: string,
  signal?: AbortSignal,
): Promise<LifeTask> {
  const res = await fetch(`${API_BASE_URL}/api/ai/analyze-demand`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
    cache: "no-store",
    signal,
  });

  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as LifeTask;
}

export type VendorRecommendation = {
  vendor_id: number;
  name: string;
  rating: number;
  description?: string | null;
  service_city?: string | null;
  service_districts: string[];
  price_min?: number | null;
  price_max?: number | null;
  categories: string[];
  estimated_price?: number | null;
  match_score: number;
  recommendation_reason: string;
};

export type MatchVendorsResponse = {
  task_id: number;
  status: string;
  category_code?: string | null;
  candidate_count: number;
  recommendations: VendorRecommendation[];
  provider: string;
  model?: string | null;
  fallback_used: boolean;
  fallback_reason?: string | null;
};

/** Write filled-in fields back to a task and optionally move its status. */
export async function updateTask(
  taskId: number,
  body: { filled_fields?: Record<string, unknown>; status?: string },
  signal?: AbortSignal,
): Promise<LifeTask> {
  const res = await fetch(`${API_BASE_URL}/api/tasks/${taskId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
    signal,
  });
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as LifeTask;
}

export async function matchVendors(
  taskId: number,
  limit = 3,
  signal?: AbortSignal,
): Promise<MatchVendorsResponse> {
  const res = await fetch(`${API_BASE_URL}/api/matching/vendors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id: taskId, limit }),
    cache: "no-store",
    signal,
  });
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as MatchVendorsResponse;
}

export type CaseTimelineStep = {
  key: string;
  label: string;
  state: "done" | "current" | "upcoming";
  at?: string | null;
  note?: string | null;
};

export type CaseHistoryEntry = {
  from_status?: string | null;
  to_status: string;
  actor: string;
  note?: string | null;
  created_at: string;
};

export type SharedWithVendor = {
  title?: string | null;
  summary?: string | null;
  category_name?: string | null;
  city?: string | null;
  district?: string | null;
  budget_amount?: number | null;
  urgency?: string | null;
  preferred_time?: string | null;
  /** Coarse location, always shared. */
  area?: string | null;
  /** True once the resident confirmed; the three fields below are then set. */
  contact_unlocked: boolean;
  address?: string | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  withheld: string[];
};

export type VendorDetail = {
  id: number;
  name: string;
  rating: number;
  description?: string | null;
  service_city?: string | null;
  service_districts: string[];
  price_min?: number | null;
  price_max?: number | null;
  categories: ServiceCategory[];
};

export type ConsultationCase = {
  id: number;
  case_number: string;
  status: string;
  status_label: string;
  task_id: number;
  task_status: string;
  next_action?: string | null;
  blocked_reason?: string | null;
  estimated_price?: number | null;
  recommendation_reason?: string | null;
  vendor_note?: string | null;
  proposed_time?: string | null;
  responded_at?: string | null;
  contact_shared: boolean;
  privacy_notice: string;
  vendor: VendorDetail;
  shared_with_vendor: SharedWithVendor;
  timeline: CaseTimelineStep[];
  history: CaseHistoryEntry[];
  created_at: string;
  updated_at: string;
};

/** Extra payload the API attaches to a duplicate-case 409. */
export type CaseConflictDetail = {
  message: string;
  case_id: number;
  case_number: string;
  status: string;
  status_label: string;
};

/** Thrown when a case already exists, carrying the id so the UI can jump to it. */
export class DuplicateCaseError extends ApiError {
  readonly detail: CaseConflictDetail;

  constructor(detail: CaseConflictDetail) {
    super(detail.message, 409);
    this.name = "DuplicateCaseError";
    this.detail = detail;
  }
}

export async function createCase(
  body: {
    taskId: number;
    selectedVendorId: number;
    formData: Record<string, unknown>;
    estimatedPrice?: number | null;
    recommendationReason?: string | null;
  },
  signal?: AbortSignal,
): Promise<ConsultationCase> {
  const res = await fetch(`${API_BASE_URL}/api/cases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
    signal,
  });

  if (res.status === 409) {
    // The duplicate branch returns a structured detail object.
    const payload = (await res.json().catch(() => null)) as {
      detail?: CaseConflictDetail | string;
    } | null;
    const detail = payload?.detail;
    if (detail && typeof detail === "object" && "case_id" in detail) {
      throw new DuplicateCaseError(detail);
    }
    throw new ApiError(typeof detail === "string" ? detail : "無法建立案件", 409);
  }

  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as ConsultationCase;
}

export async function getCase(
  caseId: number,
  signal?: AbortSignal,
): Promise<ConsultationCase> {
  const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}`, {
    cache: "no-store",
    signal,
  });
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as ConsultationCase;
}

export type VendorSummary = {
  id: number;
  name: string;
  rating: number;
  service_city?: string | null;
  open_case_count: number;
};

export type VendorCaseListItem = {
  case_id: number;
  case_number: string;
  vendor_id: number;
  vendor_name: string;
  status: string;
  status_label: string;
  estimated_price?: number | null;
  recommendation_reason?: string | null;
  vendor_note?: string | null;
  proposed_time?: string | null;
  responded_at?: string | null;
  contact_shared: boolean;
  demand: SharedWithVendor;
  created_at: string;
};

export type VendorCaseListResponse = {
  vendor: VendorSummary | null;
  total: number;
  pending: number;
  responded_total: number;
  completed_total: number;
  /** How many of `pending` are actually in `cases`. */
  pending_shown: number;
  responded_shown: number;
  completed_shown: number;
  truncated: boolean;
  cases: VendorCaseListItem[];
};

export type VendorRespondResponse = {
  case_id: number;
  case_number: string;
  status: string;
  status_label: string;
  task_id: number;
  task_status: string;
  task_next_action?: string | null;
  vendor_note?: string | null;
  proposed_time?: string | null;
  history: Array<Record<string, unknown>>;
};

export async function listVendors(signal?: AbortSignal): Promise<VendorSummary[]> {
  const res = await fetch(`${API_BASE_URL}/api/vendor/list`, {
    cache: "no-store",
    signal,
  });
  if (!res.ok) throw new ApiError(await readErrorMessage(res), res.status);
  return (await res.json()) as VendorSummary[];
}

export async function listVendorCases(
  vendorId: number | null,
  signal?: AbortSignal,
): Promise<VendorCaseListResponse> {
  const query = new URLSearchParams({ limit: "20" });
  if (vendorId !== null) query.set("vendor_id", String(vendorId));

  const res = await fetch(`${API_BASE_URL}/api/vendor/cases?${query}`, {
    cache: "no-store",
    signal,
  });
  if (!res.ok) throw new ApiError(await readErrorMessage(res), res.status);
  return (await res.json()) as VendorCaseListResponse;
}

export async function respondToCase(
  caseId: number,
  body: {
    action: "accept" | "reject";
    vendorNote?: string | null;
    proposedTime?: string | null;
  },
  vendorId?: number | null,
  signal?: AbortSignal,
): Promise<VendorRespondResponse> {
  const query = vendorId != null ? `?vendor_id=${vendorId}` : "";
  const res = await fetch(
    `${API_BASE_URL}/api/vendor/cases/${caseId}/respond${query}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal,
    },
  );
  if (!res.ok) throw new ApiError(await readErrorMessage(res), res.status);
  return (await res.json()) as VendorRespondResponse;
}

/** Resident accepts the quote, unlocking their contact details to the vendor. */
export async function confirmCase(
  caseId: number,
  signal?: AbortSignal,
): Promise<ConsultationCase> {
  const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}/confirm`, {
    method: "POST",
    cache: "no-store",
    signal,
  });
  if (!res.ok) throw new ApiError(await readErrorMessage(res), res.status);
  return (await res.json()) as ConsultationCase;
}

/** Mark the service delivered. `actor` is recorded in the audit trail. */
export async function completeCase(
  caseId: number,
  actor: "consumer" | "vendor" = "consumer",
  signal?: AbortSignal,
): Promise<ConsultationCase> {
  const res = await fetch(
    `${API_BASE_URL}/api/cases/${caseId}/complete?actor=${actor}`,
    { method: "POST", cache: "no-store", signal },
  );
  if (!res.ok) throw new ApiError(await readErrorMessage(res), res.status);
  return (await res.json()) as ConsultationCase;
}
