/*
  Real API client — every function here calls the actual FastAPI
  server (app/api/server.py) at API_BASE. No mock data lives in this
  file or anywhere downstream of it; the earlier data/mockData.ts has
  been removed entirely now that every screen reads from here instead.

  Types here match the SERVER's real response shapes exactly (see
  app/api/server.py's _case_summary/_evidence_chain/etc.) — a leaner
  shape than the old mock data used to illustrate the full intended UI.
  Two honest gaps versus that mock data, both explained in the
  server's own docstring:
    - recoveredPaise is always null (no Outcome rows persisted yet)
    - evidenceChain has 4 steps for most cases (detected/diagnosed/
      decided/authorized), not 7 — Intervened/Outcome/Stopped aren't
      real yet
*/

export const API_BASE = "http://localhost:8000";

export type Verdict = "ALLOW" | "BLOCK" | "ESCALATE" | "HOLDOUT";

export interface CaseSummary {
  id: string;
  traceId: string;
  surface: string;
  category: string;
  rootCause: string | null;
  ladderLevel: string;
  arm: "treatment" | "holdout";
  amountPaise: number;
  ltvBand: string;
  verdict: Verdict;
  detectedAt: string | null;
  channel: string | null;
  recoveredPaise: number | null;
}

export interface EvidenceNode {
  step: "detected" | "diagnosed" | "decided" | "authorized";
  label: string;
  timestamp: string | null;
  summary: string;
  hash: string | null;
  detail: Record<string, unknown>;
}

export interface CaseDetailResponse extends CaseSummary {
  evidenceChain: EvidenceNode[];
}

export interface ApprovalItem {
  id: string;
  surface: string;
  rootCause: string | null;
  reason: string;
  confidence: number | null;
  amountPaise: number;
  ltvBand: string;
  waitingSince: string | null;
}

export interface DashboardSummary {
  totalCases: number;
  byVerdict: Record<string, number>;
  byArm: Record<string, number>;
  blockReasons: Record<string, number>;
  duplicateFinancialActions: number;
  policyViolations: number;
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new ApiError(res.status, `${path} -> ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function fetchCases(): Promise<CaseSummary[]> {
  return getJson<CaseSummary[]>("/api/cases");
}

export function fetchCaseDetail(id: string): Promise<CaseDetailResponse> {
  return getJson<CaseDetailResponse>(`/api/cases/${encodeURIComponent(id)}`);
}

export function fetchApprovals(): Promise<ApprovalItem[]> {
  return getJson<ApprovalItem[]>("/api/approvals");
}

export function fetchDashboardSummary(): Promise<DashboardSummary> {
  return getJson<DashboardSummary>("/api/dashboard/summary");
}

export function rupees(paise: number): string {
  return `Rs ${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
}

