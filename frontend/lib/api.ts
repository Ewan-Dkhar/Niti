export type LanguageCode = "hi-IN" | "ta-IN" | "bn-IN" | "te-IN" | "en-IN";

export interface PolicyExtraction {
  policy_name: string;
  issuing_authority: string;
  gazette_or_order_no: string | null;
  effective_date: string | null;
  target_beneficiaries: string[];
  mandatory_eligibility: string[];
  disqualifications: string[];
  direct_benefits: string[];
  penalty_or_deadlines: string[];
  required_documents: string[];
  citation_source_map: Record<string, string>;
}

export interface AuditResult {
  is_grounded: boolean;
  unsupported_claims: string[];
  confidence_score: number;
  correction_guidance: string | null;
}

export interface VoicePayload {
  language_code: LanguageCode;
  plain_text_script: string;
  audio_base64: string | null;
  duration_estimate_sec: number;
}

export interface AnalysisResult {
  policy_data: PolicyExtraction;
  audit_status: AuditResult;
  voice_payload: VoicePayload | null;
  audio_url: string | null;
  audio_is_mock: boolean;
  from_cache: boolean;
}

export interface ResultResponse {
  task_id: string;
  status: "processing" | "completed" | "failed";
  result: AnalysisResult | null;
  error: string | null;
}

export interface SourceItem {
  source: "myscheme" | "pib";
  title: string;
  url: string;
  summary: string | null;
  published_at: string | null;
}

export interface SourcesResponse {
  query: string;
  items: SourceItem[];
  errors: string[];
}

export interface VerifyResponse {
  is_eligible: boolean;
  matched_clauses: string[];
  missing_documents: string[];
}

export interface CitizenProfile {
  income: number;
  occupation: string;
  state: string;
  documents: string[];
}

export function getApiBase(): string {
  const envBase = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
  if (envBase && envBase !== "http://localhost:8000") {
    return envBase;
  }
  if (
    typeof window !== "undefined" &&
    window.location.hostname &&
    window.location.hostname !== "localhost" &&
    window.location.hostname !== "127.0.0.1"
  ) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return envBase || "http://localhost:8000";
}

export const API_BASE = getApiBase();

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const base = getApiBase();
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail[0]?.msg ?? detail;
    } catch {
      // Non-JSON error body; keep the status message.
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export function analyzeDocument(documentUrl: string, targetLanguage: LanguageCode) {
  return request<{ status: "processing"; task_id: string }>("/api/v1/analyze", {
    method: "POST",
    body: JSON.stringify({ document_url: documentUrl, target_language: targetLanguage }),
  });
}

export function getResult(taskId: string) {
  return request<ResultResponse>(`/api/v1/results/${taskId}`);
}

export function verifyCitizen(policyId: string, profile: CitizenProfile) {
  return request<VerifyResponse>("/api/v1/verify-citizen", {
    method: "POST",
    body: JSON.stringify({ policy_id: policyId, citizen_profile: profile }),
  });
}

export function getSources(query = "", limit = 6) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (query.trim()) params.set("q", query.trim());
  return request<SourcesResponse>(`/api/v1/sources?${params.toString()}`);
}

export function audioUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${getApiBase()}${path}`;
}

export const LANGUAGES: { code: LanguageCode; label: string; english: string }[] = [
  { code: "hi-IN", label: "हिन्दी", english: "Hindi" },
  { code: "ta-IN", label: "தமிழ்", english: "Tamil" },
  { code: "bn-IN", label: "বাংলা", english: "Bengali" },
  { code: "te-IN", label: "తెలుగు", english: "Telugu" },
  { code: "en-IN", label: "English", english: "English" },
];
