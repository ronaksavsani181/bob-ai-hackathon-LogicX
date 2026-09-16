// pages/Investigate.tsx — Investigate page: lot search, detail, wafer grid, root cause
//
// Data flow:
//   GET /api/lots                           → Lot list with pagination/filter
//   GET /api/lots/{lot_id_str}              → Lot detail + parameter anomalies
//   GET /api/lots/{lot_id_str}/root-cause   → Top-3 root causes (never generated here)
//   GET /api/lots/{lot_id_str}/patterns     → Wafer patterns (for yield heat grid)
//
// HARD RULES:
//   - Root causes are NEVER generated in the frontend — only displayed from backend
//   - No hard-coded yields, risk labels, or analytical values
//   - All API calls go through src/api/client.ts

import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';
import type {
  LotSummary,
  LotDetailResponse,
  RootCauseResponse,
  WaferPatternResponse,
} from '../types/api';
import {
  Card,
  Badge,
  Spinner,
  ErrorMessage,
  severityBadge,
  DisclaimerBanner,
  ScoreBar,
} from '../components/Shared';
import ParamDeviationChart from '../components/charts/ParamDeviation';

// ---------------------------------------------------------------------------
// Wafer yield heat grid
// ---------------------------------------------------------------------------

interface WaferGridProps {
  patterns: WaferPatternResponse;
  waferCount: number;
}

const PATTERN_COLOR: Record<string, string> = {
  center_heavy:      '#ef4444',
  edge_ring:         '#f97316',
  localized_hotspot: '#a855f7',
  radial:            '#3b82f6',
  scratch_line:      '#ec4899',
  uniform:           '#22c55e',
  insufficient_data: '#d1d5db',
};

function WaferGrid({ patterns, waferCount }: WaferGridProps) {
  const patternByWafer = new Map(patterns.patterns.map(p => [p.wafer_id, p]));
  const slots = Array.from({ length: Math.min(waferCount, 25) }, (_, i) => i + 1);

  return (
    <div>
      <div className="grid grid-cols-5 gap-1.5">
        {slots.map(slot => {
          // Find a pattern whose wafer_id sequence position matches slot (best-effort)
          const pattern = patterns.patterns[slot - 1];
          const color = pattern ? (PATTERN_COLOR[pattern.pattern_type] ?? '#d1d5db') : '#f3f4f6';
          const score = pattern ? (pattern.pattern_score * 100).toFixed(0) : null;
          const title = pattern
            ? `Wafer ${slot} · ${pattern.pattern_type} · score ${score}% · ${pattern.defect_count} defects`
            : `Wafer ${slot} — no pattern data`;

          return (
            <div
              key={slot}
              title={title}
              className="relative rounded aspect-square flex items-center justify-center text-xs font-mono text-white font-semibold cursor-default"
              style={{ backgroundColor: color, minHeight: 32, opacity: pattern ? 1 : 0.25 }}
            >
              {slot}
              {pattern?.pattern_type === 'edge_ring' || pattern?.pattern_type === 'center_heavy' ? (
                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-red-200 border border-red-400" />
              ) : null}
            </div>
          );
        })}
      </div>
      {/* Pattern legend */}
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1">
        {Object.entries(PATTERN_COLOR).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1 text-xs text-gray-500">
            <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: color }} />
            {type.replace(/_/g, ' ')}
          </div>
        ))}
      </div>
      <p className="text-xs text-gray-400 mt-2">
        {patternByWafer.size} / {waferCount} wafers classified · colours = defect pattern type
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root cause panel
// ---------------------------------------------------------------------------

interface RootCausePanelProps {
  data: RootCauseResponse;
}

function RootCausePanel({ data }: RootCausePanelProps) {
  return (
    <div className="space-y-3">
      <DisclaimerBanner text={data.disclaimer} />
      {data.insufficient_evidence && (
        <div className="bg-yellow-50 border border-yellow-200 rounded px-3 py-2 text-xs text-yellow-700">
          Insufficient evidence for high-confidence ranking. Review the signals below carefully.
        </div>
      )}
      {data.candidates.length === 0 ? (
        <p className="text-sm text-gray-400">No root-cause candidates identified.</p>
      ) : (
        data.candidates.slice(0, 3).map(c => (
          <div key={c.cause_id} className="border border-gray-200 rounded-lg p-3 bg-gray-50">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold text-gray-400">#{c.rank}</span>
                  <Badge
                    label={c.cause_type}
                    variant={
                      c.cause_type === 'chamber_recurrence' ? 'orange'
                      : c.cause_type === 'yield_excursion' ? 'red'
                      : c.cause_type === 'maintenance_proximity' ? 'yellow'
                      : 'blue'
                    }
                  />
                  <span className="text-xs text-gray-500 font-mono">
                    v{c.model_version}
                  </span>
                </div>
                <p className="text-sm text-gray-700 font-medium leading-snug">
                  {c.cause_description}
                </p>
                <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs text-gray-500">
                  <span>Lots affected: {c.affected_lot_count}</span>
                  <span>Wafers: {c.affected_wafer_count}</span>
                  <span>Temporal precedence: {c.temporal_precedence ? 'Yes' : 'No'}</span>
                  <span>Evidence IDs: {c.evidence_ids.length}</span>
                </div>
                {Object.keys(c.supporting_signals).length > 0 && (
                  <div className="mt-1.5 text-xs text-gray-400">
                    Supporting:{' '}
                    {Object.entries(c.supporting_signals)
                      .map(([k, v]) => `${k}=${(v as number).toFixed(2)}`)
                      .join(', ')}
                  </div>
                )}
              </div>
              <div className="flex-shrink-0 text-right">
                <p className="text-xs text-gray-400 mb-0.5">Score</p>
                <p className="text-lg font-bold text-gray-800">{(c.score * 100).toFixed(0)}</p>
                <div className="w-20">
                  <ScoreBar score={c.score} />
                </div>
                <p className="text-xs text-gray-400 mt-1">conf {(c.confidence * 100).toFixed(0)}%</p>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type FilterStatus = 'all' | 'completed' | 'in_progress' | 'on_hold';

export default function InvestigatePage() {
  // --- Lot list state ---
  const [lots, setLots] = useState<LotSummary[]>([]);
  const [totalLots, setTotalLots] = useState(0);
  const [page, setPage] = useState(1);
  const [filterText, setFilterText] = useState('');
  const [excursionOnly, setExcursionOnly] = useState(false);
  const [statusFilter, setStatusFilter] = useState<FilterStatus>('all');
  const [loadingLots, setLoadingLots] = useState(true);
  const [lotsError, setLotsError] = useState<string | null>(null);

  // --- Lot detail state ---
  const [selectedLotId, setSelectedLotId] = useState<string | null>(null);
  const [detail, setDetail] = useState<LotDetailResponse | null>(null);
  const [rootCause, setRootCause] = useState<RootCauseResponse | null>(null);
  const [patterns, setPatterns] = useState<WaferPatternResponse | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'params' | 'wafers' | 'root-cause'>('overview');

  const PAGE_SIZE = 50;

  // --- Fetch lot list ---
  const fetchLots = useCallback(() => {
    setLoadingLots(true);
    setLotsError(null);
    api
      .lots({
        page,
        page_size: PAGE_SIZE,
        excursion_only: excursionOnly,
        status: statusFilter === 'all' ? undefined : statusFilter,
      })
      .then(res => {
        setLots(res.lots);
        setTotalLots(res.meta.total);
      })
      .catch(e => setLotsError(String(e)))
      .finally(() => setLoadingLots(false));
  }, [page, excursionOnly, statusFilter]);

  useEffect(() => {
    fetchLots();
  }, [fetchLots]);

  // --- Fetch lot detail ---
  const handleSelectLot = (lotIdStr: string) => {
    setSelectedLotId(lotIdStr);
    setDetail(null);
    setRootCause(null);
    setPatterns(null);
    setDetailError(null);
    setLoadingDetail(true);
    setActiveTab('overview');

    Promise.all([
      api.lotDetail(lotIdStr),
      api.lotRootCause(lotIdStr),
      api.lotPatterns(lotIdStr, 25),
    ])
      .then(([d, rc, p]) => {
        setDetail(d);
        setRootCause(rc);
        setPatterns(p);
      })
      .catch(e => setDetailError(String(e)))
      .finally(() => setLoadingDetail(false));
  };

  // --- Client-side text filter (applied on top of server pagination) ---
  const filteredLots = filterText
    ? lots.filter(
        l =>
          l.lot_id_str.toLowerCase().includes(filterText.toLowerCase()) ||
          l.product.toLowerCase().includes(filterText.toLowerCase()),
      )
    : lots;

  const totalPages = Math.ceil(totalLots / PAGE_SIZE);

  return (
    <div className="flex gap-4 min-h-0">
      {/* ---- Left panel: lot list ---- */}
      <div className="w-72 flex-shrink-0 space-y-3">
        <Card title="Lot Search">
          <div className="space-y-2">
            <input
              type="text"
              placeholder="Filter by lot ID or product…"
              value={filterText}
              onChange={e => setFilterText(e.target.value)}
              className="w-full border border-gray-200 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400"
            />
            <select
              value={statusFilter}
              onChange={e => {
                setStatusFilter(e.target.value as FilterStatus);
                setPage(1);
              }}
              className="w-full border border-gray-200 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400 bg-white"
            >
              <option value="all">All statuses</option>
              <option value="in_progress">In progress</option>
              <option value="completed">Completed</option>
              <option value="on_hold">On hold</option>
            </select>
            <label className="flex items-center gap-2 text-xs text-gray-500 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={excursionOnly}
                onChange={e => {
                  setExcursionOnly(e.target.checked);
                  setPage(1);
                }}
              />
              Excursions only
            </label>
          </div>
        </Card>

        {/* Lot list */}
        <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
          <div className="px-4 py-2.5 border-b border-gray-100 flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Lots ({totalLots})
            </span>
            <span className="text-xs text-gray-400">
              p{page}/{totalPages || 1}
            </span>
          </div>
          {lotsError && <ErrorMessage msg={lotsError} />}
          {loadingLots ? (
            <Spinner />
          ) : filteredLots.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-6">No lots found.</p>
          ) : (
            <div className="max-h-[55vh] overflow-y-auto">
              {filteredLots.map(lot => (
                <button
                  key={lot.lot_id}
                  onClick={() => handleSelectLot(lot.lot_id_str)}
                  className={`w-full text-left px-3 py-2.5 border-b border-gray-50 text-sm transition-colors ${
                    selectedLotId === lot.lot_id_str
                      ? 'bg-blue-50 border-l-2 border-l-blue-500'
                      : 'hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-blue-700">
                      {lot.lot_id_str}
                    </span>
                    <div className="flex items-center gap-1">
                      {lot.excursion && <span className="text-red-400 text-xs">⚠</span>}
                      {lot.risk_class && (
                        <Badge
                          label={lot.risk_class}
                          variant={
                            lot.risk_class === 'high' ? 'red'
                            : lot.risk_class === 'medium' ? 'orange'
                            : 'green'
                          }
                        />
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">{lot.product}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-gray-500">{lot.status}</span>
                    {lot.mean_yield != null && (
                      <span
                        className={`text-xs font-semibold ${lot.excursion ? 'text-red-600' : 'text-green-600'}`}
                      >
                        {(lot.mean_yield * 100).toFixed(1)}%
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="px-4 py-2 flex items-center justify-between border-t border-gray-100">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="text-xs px-2 py-1 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
              >
                ←
              </button>
              <span className="text-xs text-gray-400">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="text-xs px-2 py-1 rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
              >
                →
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ---- Right panel: lot detail ---- */}
      <div className="flex-1 min-w-0 space-y-4">
        {!selectedLotId && (
          <div className="flex items-center justify-center h-48 text-gray-400 text-sm bg-white rounded-lg border border-gray-200">
            Select a lot from the left panel to investigate.
          </div>
        )}

        {loadingDetail && <Spinner />}
        {detailError && <ErrorMessage msg={detailError} />}

        {detail && !loadingDetail && (
          <>
            {/* Lot header card */}
            <Card>
              <div className="flex flex-wrap gap-5 items-start">
                <div>
                  <p className="text-xs text-gray-400 uppercase tracking-wide">Lot ID</p>
                  <p className="font-mono font-bold text-xl text-gray-800">{detail.lot_id_str}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase">Product</p>
                  <p className="font-semibold text-gray-700">{detail.product}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase">Technology</p>
                  <p className="text-gray-700">{detail.technology_node}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase">Priority</p>
                  <Badge
                    label={detail.priority}
                    variant={detail.priority === 'high' ? 'red' : detail.priority === 'low' ? 'gray' : 'blue'}
                  />
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase">Status</p>
                  <Badge label={detail.status} variant="gray" />
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase">Mean Yield</p>
                  <p
                    className={`font-bold text-xl ${detail.yield_excursion?.is_excursion ? 'text-red-600' : 'text-green-600'}`}
                  >
                    {detail.mean_yield != null ? `${(detail.mean_yield * 100).toFixed(2)}%` : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase">Wafers</p>
                  <p className="text-gray-700 font-semibold">{detail.wafer_count}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase">Started</p>
                  <p className="text-gray-600 text-sm">
                    {detail.actual_start_at
                      ? new Date(detail.actual_start_at).toLocaleDateString()
                      : '—'}
                  </p>
                </div>
              </div>
            </Card>

            {/* Tab bar */}
            <div className="flex gap-0 border-b border-gray-200">
              {(
                [
                  { id: 'overview', label: 'Overview' },
                  { id: 'params', label: `Parameters (${detail.parameter_anomalies.length})` },
                  { id: 'wafers', label: `Wafer Grid (${detail.wafer_count})` },
                  { id: 'root-cause', label: `Root Cause (${rootCause?.candidates.length ?? 0})` },
                ] as const
              ).map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab.id
                      ? 'border-blue-600 text-blue-700'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Overview tab */}
            {activeTab === 'overview' && (
              <div className="space-y-4">
                {detail.yield_excursion ? (
                  <Card title="Yield Excursion">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <p className="text-xs text-gray-400">Observed Yield</p>
                        <p className="font-bold text-red-600 text-lg">
                          {(detail.yield_excursion.observed_yield * 100).toFixed(2)}%
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400">Baseline</p>
                        <p className="font-semibold text-gray-700">
                          {(detail.yield_excursion.baseline_yield * 100).toFixed(2)}%
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400">Deviation</p>
                        <p className="font-bold text-red-600">
                          {detail.yield_excursion.deviation_sigma.toFixed(2)}σ
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400">Severity</p>
                        {severityBadge(detail.yield_excursion.severity)}
                      </div>
                    </div>
                    <p className="text-xs text-gray-400 mt-3">
                      Method: {detail.yield_excursion.method}
                    </p>
                  </Card>
                ) : (
                  <Card title="Yield Status">
                    <p className="text-sm text-green-600 font-medium">
                      ✓ No yield excursion detected for this lot.
                    </p>
                  </Card>
                )}

                {/* Top parameter anomalies summary */}
                {detail.parameter_anomalies.length > 0 && (
                  <Card title={`Top Parameter Anomalies (${detail.parameter_anomalies.length} total)`}>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-xs text-gray-400 border-b">
                            <th className="pb-2 pr-3">Parameter</th>
                            <th className="pb-2 pr-3">Observed</th>
                            <th className="pb-2 pr-3">Baseline μ</th>
                            <th className="pb-2 pr-3">z-score</th>
                            <th className="pb-2">Severity</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detail.parameter_anomalies.slice(0, 5).map((a, i) => (
                            <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                              <td className="py-1.5 pr-3 font-mono text-xs">{a.param_name}</td>
                              <td className="py-1.5 pr-3 text-xs">{a.observed_value.toFixed(3)}</td>
                              <td className="py-1.5 pr-3 text-gray-400 text-xs">{a.baseline_mean.toFixed(3)}</td>
                              <td
                                className={`py-1.5 pr-3 font-semibold text-xs ${Math.abs(a.z_score) > 4 ? 'text-red-600' : 'text-orange-500'}`}
                              >
                                {a.z_score.toFixed(2)}
                              </td>
                              <td className="py-1.5">{severityBadge(a.severity)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                )}
              </div>
            )}

            {/* Params tab — full anomaly list + chart */}
            {activeTab === 'params' && (
              <div className="space-y-4">
                {detail.parameter_anomalies.length === 0 ? (
                  <Card title="Parameter Anomalies">
                    <p className="text-sm text-gray-400">No parameter anomalies detected (|z| &lt; 3.0).</p>
                  </Card>
                ) : (
                  <>
                    <Card title={`Parameter Deviation Chart (top 10 by |z|)`}>
                      <ParamDeviationChart anomalies={detail.parameter_anomalies} />
                    </Card>
                    <Card title={`All Anomalies (${detail.parameter_anomalies.length})`}>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-left text-xs text-gray-400 border-b">
                              <th className="pb-2 pr-3">Parameter</th>
                              <th className="pb-2 pr-3">Observed</th>
                              <th className="pb-2 pr-3">Baseline μ</th>
                              <th className="pb-2 pr-3">Baseline σ</th>
                              <th className="pb-2 pr-3">z-score</th>
                              <th className="pb-2 pr-3">Direction</th>
                              <th className="pb-2">Severity</th>
                            </tr>
                          </thead>
                          <tbody>
                            {detail.parameter_anomalies.map((a, i) => (
                              <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                                <td className="py-1.5 pr-3 font-mono text-xs">{a.param_name}</td>
                                <td className="py-1.5 pr-3 text-xs">{a.observed_value.toFixed(3)}</td>
                                <td className="py-1.5 pr-3 text-gray-400 text-xs">{a.baseline_mean.toFixed(3)}</td>
                                <td className="py-1.5 pr-3 text-gray-400 text-xs">{a.baseline_std.toFixed(3)}</td>
                                <td
                                  className={`py-1.5 pr-3 font-semibold text-xs ${Math.abs(a.z_score) > 4 ? 'text-red-600' : 'text-orange-500'}`}
                                >
                                  {a.z_score.toFixed(2)}
                                </td>
                                <td className="py-1.5 pr-3">
                                  <Badge
                                    label={a.direction}
                                    variant={a.direction === 'high' ? 'orange' : 'blue'}
                                  />
                                </td>
                                <td className="py-1.5">{severityBadge(a.severity)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </Card>
                  </>
                )}
              </div>
            )}

            {/* Wafer grid tab */}
            {activeTab === 'wafers' && (
              <Card title={`Wafer Pattern Grid — ${detail.wafer_count} wafers`}>
                {patterns ? (
                  <WaferGrid patterns={patterns} waferCount={detail.wafer_count} />
                ) : (
                  <p className="text-sm text-gray-400">No pattern data available.</p>
                )}
              </Card>
            )}

            {/* Root cause tab */}
            {activeTab === 'root-cause' && (
              <Card title="Root-Cause Candidates (top 3)">
                {rootCause ? (
                  <RootCausePanel data={rootCause} />
                ) : (
                  <p className="text-sm text-gray-400">Root-cause analysis unavailable.</p>
                )}
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
}
