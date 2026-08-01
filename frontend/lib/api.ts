export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type HealthResponse = {
  status: string;
  db: string;
  detail?: string;
};

export type MissingField = {
  field: string;
  label: string;
  reason?: string | null;
  required: boolean;
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
