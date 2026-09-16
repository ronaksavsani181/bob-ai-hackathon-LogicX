// src/api/client.ts — Typed API client for the FastAPI backend

// Vite injects import.meta.env at build time (declared in vite/client types)
const BASE_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

import type {
  FleetYieldSummary,
  LotListResponse,
  LotDetailResponse,
  WaferPatternResponse,
  RootCauseResponse,
  PreRunRiskListResponse,
  PreRunRiskSummary,
  ChamberRecurrenceResponse,
  YieldTrendResponse,
  ActionListResponse,
  ReviewRequest,
  ReviewResponse,
  EvidenceResponse,
  HealthResponse,
} from '../types/api';

export const api = {
  health: () => apiFetch<HealthResponse>('/api/health'),

  // Monitor
  fleetSummary: () => apiFetch<FleetYieldSummary>('/api/monitor/fleet-summary'),
  chamberRecurrence: () => apiFetch<ChamberRecurrenceResponse>('/api/monitor/chambers'),

  // Lots
  lots: (params?: { page?: number; page_size?: number; excursion_only?: boolean; status?: string }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set('page', String(params.page));
    if (params?.page_size) qs.set('page_size', String(params.page_size));
    if (params?.excursion_only) qs.set('excursion_only', 'true');
    if (params?.status) qs.set('status', params.status);
    return apiFetch<LotListResponse>(`/api/lots?${qs.toString()}`);
  },
  lotDetail: (lotIdStr: string) => apiFetch<LotDetailResponse>(`/api/lots/${lotIdStr}`),
  lotPatterns: (lotIdStr: string, sampleWafers = 5) =>
    apiFetch<WaferPatternResponse>(`/api/lots/${lotIdStr}/patterns?sample_wafers=${sampleWafers}`),
  lotRootCause: (lotIdStr: string) => apiFetch<RootCauseResponse>(`/api/lots/${lotIdStr}/root-cause`),

  // Monitor extras
  yieldTrend: (lastN = 150) => apiFetch<YieldTrendResponse>(`/api/monitor/yield-trend?last_n=${lastN}`),

  // Pre-run risk
  preRunRisk: (topN = 50) => apiFetch<PreRunRiskListResponse>(`/api/pre-run/risk?top_n=${topN}`),
  preRunRiskSingle: (lotIdStr: string) => apiFetch<PreRunRiskSummary>(`/api/pre-run/risk/${lotIdStr}`),

  // Evidence
  lotEvidence: (lotIdStr: string) => apiFetch<EvidenceResponse>(`/api/lots/${lotIdStr}/evidence`),

  // Actions
  listActions: (status?: string) => {
    const qs = status ? `?status=${status}` : '';
    return apiFetch<ActionListResponse>(`/api/actions${qs}`);
  },
  submitReview: (body: ReviewRequest) =>
    apiFetch<ReviewResponse>('/api/actions/review', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};
