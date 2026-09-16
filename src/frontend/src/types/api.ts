// src/types/api.ts — TypeScript types matching the FastAPI Pydantic schemas

export interface HealthResponse {
  status: string;
  version: string;
  generated_at: string;
}

export interface PaginationMeta {
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface LotSummary {
  lot_id: number;
  lot_id_str: string;
  product: string;
  technology_node: string;
  priority: string;
  status: string;
  actual_start_at: string | null;
  mean_yield: number | null;
  excursion: boolean;
  excursion_severity: 'none' | 'mild' | 'moderate' | 'severe';
  risk_score: number | null;
  risk_class: 'low' | 'medium' | 'high' | null;
}

export interface LotListResponse {
  lots: LotSummary[];
  meta: PaginationMeta;
}

export interface FleetYieldSummary {
  fleet_mean_yield: number;
  fleet_std_yield: number;
  excursion_count_7d: number;
  excursion_count_30d: number;
  high_risk_lots_pending: number;
  generated_at: string;
}

export interface YieldExcursionSummary {
  observed_yield: number;
  baseline_yield: number;
  deviation_sigma: number;
  severity: string;
  is_excursion: boolean;
  method: string;
  evidence_id: string;
}

export interface ParameterAnomalySummary {
  param_name: string;
  z_score: number;
  direction: string;
  severity: string;
  baseline_mean: number;
  baseline_std: number;
  observed_value: number;
  evidence_id: string;
}

export interface LotDetailResponse {
  lot_id: number;
  lot_id_str: string;
  product: string;
  technology_node: string;
  priority: string;
  status: string;
  actual_start_at: string | null;
  actual_end_at: string | null;
  queue_time_h: number | null;
  mean_yield: number | null;
  wafer_count: number;
  yield_excursion: YieldExcursionSummary | null;
  parameter_anomalies: ParameterAnomalySummary[];
  generated_at: string;
}

export interface WaferDefectPattern {
  wafer_id: number;
  pattern_type: string;
  pattern_score: number;
  defect_count: number;
  spatial_statistics: Record<string, number>;
  evidence_id: string;
}

export interface WaferPatternResponse {
  lot_id_str: string;
  patterns: WaferDefectPattern[];
  generated_at: string;
}

export interface RootCauseCandidate {
  rank: number;
  cause_id: string;
  cause_type: string;
  cause_description: string;
  score: number;
  confidence: number;
  evidence_ids: string[];
  supporting_signals: Record<string, number>;
  contradicting_signals: Record<string, number>;
  affected_lot_count: number;
  affected_wafer_count: number;
  temporal_precedence: boolean;
  model_version: string;
  generated_at: string;
}

export interface RootCauseResponse {
  lot_id_str: string;
  candidates: RootCauseCandidate[];
  insufficient_evidence: boolean;
  evidence_summary: Record<string, unknown>;
  model_version: string;
  generated_at: string;
  disclaimer: string;
}

export interface PreRunRiskSummary {
  lot_id_str: string;
  planned_start_at: string | null;
  risk_score: number;
  risk_class: 'low' | 'medium' | 'high';
  top_features: Record<string, number>;
  model_version: string;
  evidence_id: string;
  generated_at: string;
}

export interface PreRunRiskListResponse {
  assessments: PreRunRiskSummary[];
  model_version: string;
  generated_at: string;
}

export interface ChamberRecurrenceSummary {
  chamber_id: number;
  chamber_name: string;
  tool_name: string;
  affected_lot_count: number;
  chamber_mean_yield: number;
  fleet_mean_yield: number;
  yield_gap: number;
  recurrence_score: number;
  is_recurrent: boolean;
  algorithm_version: string;
}

export interface ChamberRecurrenceResponse {
  chambers: ChamberRecurrenceSummary[];
  generated_at: string;
}

export interface YieldTrendPoint {
  lot_id_str: string;
  actual_start_at: string;
  mean_yield: number;
  is_excursion: boolean;
  scenario_hint: string | null;
}

export interface YieldTrendResponse {
  points: YieldTrendPoint[];
  fleet_mean: number;
  excursion_threshold: number;
  generated_at: string;
}

export interface ActionRecommendation {
  action_id: number | null;
  lot_id_str: string;
  recommendation: string;
  action_type: string;
  priority: string;
  evidence_ids: string[];
  status: string;
  created_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
}

export interface ActionListResponse {
  actions: ActionRecommendation[];
  total: number;
  generated_at: string;
}

export interface ReviewRequest {
  action_id: number;
  decision: 'approved' | 'rejected';
  reviewer: string;
  notes?: string;
}

export interface ReviewResponse {
  action_id: number;
  decision: string;
  reviewer: string;
  reviewed_at: string;
  message: string;
}

export interface EvidenceSummaryItem {
  evidence_id: string;
  source_type: string;
  feature: string;
  observed_value: number;
  baseline_value: number;
  deviation_score: number;
  direction: string;
  algorithm_version: string;
  generated_at: string;
}

export interface EvidenceResponse {
  lot_id_str: string;
  items: EvidenceSummaryItem[];
  total: number;
}
