export type AnalysisConfidence = {
  inputQuality: "high" | "moderate" | "limited" | "unknown";
  separationIntegrity: "high" | "moderate" | "limited" | "unknown";
  referenceCompatibility: "high" | "moderate" | "limited" | "unknown";
  candidateMargin: "high" | "moderate" | "limited" | "unknown";
  temporalConsensus: "high" | "moderate" | "limited" | "unknown";
};

export type AnalysisStatus = {
  id: string;
  state: "awaiting_upload" | "queued" | "running" | "completed" | "failed";
  resultKind?: "recording_match" | "similarity_candidate" | "no_result";
  historicalClaimAllowed?: boolean;
  artifactFlags?: string[];
  confidence?: AnalysisConfidence;
  message?: string;
};

export type UploadGrant = {
  jobId: string;
  upload: {
    method: "PUT";
    url: string;
    headers: Record<string, string>;
    expiresAt: string;
  };
  constraints: {
    maxBytes: number;
    acceptedMimePrefixes: string[];
    retentionClass: string;
  };
};

export type PresetSummary = {
  id: string;
  name: string;
  maker?: string;
  product?: string;
  evidenceLabel?: "verified" | "official" | "similarity";
};

const baseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "");

export class SynthNowApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "SynthNowApiError";
  }
}

function requireBaseUrl(): string {
  if (!baseUrl) {
    throw new SynthNowApiError(503, "The Synth Now API is not configured in this build.");
  }
  return baseUrl;
}

async function request<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  const response = await fetch(`${requireBaseUrl()}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new SynthNowApiError(response.status, body.detail || body.message || "Synth Now could not complete this request.");
  }

  return response.json() as Promise<T>;
}

export const synthNowApi = {
  listPresets: (query: string, token?: string | null) =>
    request<{ items: PresetSummary[] }>(`/v1/presets?query=${encodeURIComponent(query)}`, {}, token),
  createUpload: (
    input: { filename: string; mimeType: string; sizeBytes?: number | null; inputType: "mix" | "stem" },
    token?: string | null,
  ) => request<UploadGrant>("/v1/analysis/uploads", { method: "POST", body: JSON.stringify(input) }, token),
  completeUpload: (jobId: string, input: { checksum?: string; sizeBytes?: number | null }, token?: string | null) =>
    request<AnalysisStatus>(`/v1/analysis/uploads/${encodeURIComponent(jobId)}/complete`, { method: "POST", body: JSON.stringify(input) }, token),
  getAnalysis: (jobId: string, token?: string | null) =>
    request<AnalysisStatus>(`/v1/analysis/${encodeURIComponent(jobId)}`, {}, token),
};
