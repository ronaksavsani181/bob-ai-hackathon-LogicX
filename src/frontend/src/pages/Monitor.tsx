// pages/Monitor.tsx — Monitor page: fleet KPIs, yield trend, excursion table
//
// Data flow:
//   GET /api/monitor/fleet-summary  → KPI cards
//   GET /api/monitor/yield-trend    → YieldTrendChart (Recharts)
//   GET /api/lots?excursion_only=true → Excursion table
//   GET /api/monitor/chambers       → Recurrent chambers summary
//
// Auto-refreshes every 30 seconds with clean interval lifecycle.
// All data comes from the backend — no analytical values are generated here.

import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type {
  FleetYieldSummary,
  LotListResponse,
  ChamberRecurrenceResponse,
  YieldTrendResponse,
} from '../types/api';
import { KpiTile, Card, Badge, severityBadge, Spinner, ErrorMessage } from '../components/Shared';
import YieldTrendChart from '../components/charts/YieldTrendChart';

const REFRESH_MS = 30_000;

export default function MonitorPage() {
  const [fleet, setFleet] = useState<FleetYieldSummary | null>(null);
  const [excursionLots, setExcursionLots] = useState<LotListResponse | null>(null);
  const [inflight, setInflight] = useState<LotListResponse | null>(null);
  const [chambers, setChambers] = useState<ChamberRecurrenceResponse | null>(null);
  const [trend, setTrend] = useState<YieldTrendResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadAll = () => {
    setLoading(prev => {
      // Only show full spinner on first load
      return prev && fleet === null;
    });
    setError(null);
    Promise.all([
      api.fleetSummary(),
      api.yieldTrend(150),
      api.lots({ page: 1, page_size: 50, excursion_only: true }),
      api.lots({ page: 1, page_size: 20, status: 'in_progress' }),
      api.chamberRecurrence(),
    ])
      .then(([f, t, exc, inf, c]) => {
        setFleet(f);
        setTrend(t);
        setExcursionLots(exc);
        setInflight(inf);
        setChambers(c);
        setLastRefreshed(new Date());
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadAll();
    intervalRef.current = setInterval(loadAll, REFRESH_MS);
    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading && fleet === null) return <Spinner />;
  if (error && fleet === null) return <ErrorMessage msg={error} />;

  const recurrentChambers = chambers?.chambers.filter(c => c.is_recurrent) ?? [];
  const allExcursions = excursionLots?.lots ?? [];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800">Fab Monitor — Fleet Overview</h1>
        <div className="flex items-center gap-3">
          {error && (
            <span className="text-xs text-red-500">Refresh error — showing stale data</span>
          )}
          {lastRefreshed && (
            <span className="text-xs text-gray-400">
              Updated {lastRefreshed.toLocaleTimeString()}
            </span>
          )}
          <span className="text-xs text-gray-400">Auto-refreshes every 30 s</span>
          <button
            onClick={loadAll}
            className="text-xs border border-gray-300 rounded px-2.5 py-1 text-gray-600 hover:bg-gray-50"
          >
            Refresh now
          </button>
        </div>
      </div>

      {/* KPI row — 5 tiles */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <KpiTile
          label="Avg Yield (7d)"
          value={fleet ? `${(fleet.fleet_mean_yield * 100).toFixed(2)}%` : '—'}
          sub={fleet ? `σ = ${(fleet.fleet_std_yield * 100).toFixed(2)}%` : undefined}
          accent
        />
        <KpiTile
          label="Open Excursions (7d)"
          value={fleet?.excursion_count_7d ?? '—'}
        />
        <KpiTile
          label="Open Excursions (30d)"
          value={fleet?.excursion_count_30d ?? '—'}
        />
        <KpiTile
          label="High-Risk Pending"
          value={fleet?.high_risk_lots_pending ?? '—'}
        />
        <KpiTile
          label="Lots In-Flight"
          value={inflight?.meta.total ?? '—'}
        />
      </div>

      {/* Yield Trend Chart */}
      <Card
        title={
          trend
            ? `Yield Trend — last ${trend.points.length} lots · fleet μ ${(trend.fleet_mean * 100).toFixed(2)}% · threshold ${(trend.excursion_threshold * 100).toFixed(2)}%`
            : 'Yield Trend'
        }
      >
        {trend ? (
          <YieldTrendChart data={trend} height={240} />
        ) : (
          <Spinner />
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Excursion table */}
        <Card title={`Yield Excursions (${allExcursions.length} open)`}>
          {allExcursions.length === 0 ? (
            <p className="text-sm text-gray-400">No excursions in current window.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400 border-b">
                    <th className="pb-2 pr-3">Lot</th>
                    <th className="pb-2 pr-3">Product</th>
                    <th className="pb-2 pr-3">Started</th>
                    <th className="pb-2 pr-3">Yield</th>
                    <th className="pb-2">Severity</th>
                  </tr>
                </thead>
                <tbody>
                  {allExcursions.map(lot => (
                    <tr key={lot.lot_id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="py-1.5 pr-3 font-mono text-xs text-blue-700">{lot.lot_id_str}</td>
                      <td className="py-1.5 pr-3 text-gray-600 text-xs truncate max-w-[120px]">{lot.product}</td>
                      <td className="py-1.5 pr-3 text-gray-400 text-xs">
                        {lot.actual_start_at
                          ? new Date(lot.actual_start_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                          : '—'}
                      </td>
                      <td className="py-1.5 pr-3 font-semibold text-red-600 text-xs">
                        {lot.mean_yield != null ? `${(lot.mean_yield * 100).toFixed(1)}%` : '—'}
                      </td>
                      <td className="py-1.5">{severityBadge(lot.excursion_severity)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Recurrent chambers */}
        <Card title={`Chamber Recurrence (${recurrentChambers.length} flagged)`}>
          {recurrentChambers.length === 0 ? (
            <p className="text-sm text-gray-400">No recurrent chambers detected.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400 border-b">
                    <th className="pb-2 pr-3">Chamber</th>
                    <th className="pb-2 pr-3">Tool</th>
                    <th className="pb-2 pr-3">Yield Gap</th>
                    <th className="pb-2 pr-3">Score</th>
                    <th className="pb-2">Lots</th>
                  </tr>
                </thead>
                <tbody>
                  {recurrentChambers.map(c => (
                    <tr key={c.chamber_id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="py-1.5 pr-3 font-mono text-xs">{c.chamber_name}</td>
                      <td className="py-1.5 pr-3 text-gray-500 text-xs">{c.tool_name}</td>
                      <td className="py-1.5 pr-3 text-red-600 font-semibold text-xs">
                        -{(c.yield_gap * 100).toFixed(1)}pp
                      </td>
                      <td className="py-1.5 pr-3">
                        <div className="flex items-center gap-1.5">
                          <div className="h-1.5 rounded-full bg-gray-200 w-16 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-orange-500"
                              style={{ width: `${Math.min(100, c.recurrence_score * 100)}%` }}
                            />
                          </div>
                          <span className="text-xs font-mono text-gray-600">
                            {(c.recurrence_score * 100).toFixed(0)}
                          </span>
                        </div>
                      </td>
                      <td className="py-1.5 text-xs text-gray-500">{c.affected_lot_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {/* All lots snapshot */}
      {inflight && inflight.lots.length > 0 && (
        <Card title={`In-Flight Lots (${inflight.meta.total})`}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b">
                  <th className="pb-2 pr-3">Lot ID</th>
                  <th className="pb-2 pr-3">Product</th>
                  <th className="pb-2 pr-3">Node</th>
                  <th className="pb-2 pr-3">Priority</th>
                  <th className="pb-2 pr-3">Risk</th>
                  <th className="pb-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {inflight.lots.map(lot => (
                  <tr key={lot.lot_id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-1.5 pr-3 font-mono text-xs text-blue-700">{lot.lot_id_str}</td>
                    <td className="py-1.5 pr-3 text-xs truncate max-w-[100px]">{lot.product}</td>
                    <td className="py-1.5 pr-3 text-gray-500 text-xs">{lot.technology_node}</td>
                    <td className="py-1.5 pr-3">
                      <Badge
                        label={lot.priority}
                        variant={lot.priority === 'high' ? 'red' : lot.priority === 'low' ? 'gray' : 'blue'}
                      />
                    </td>
                    <td className="py-1.5 pr-3">
                      {lot.risk_class ? (
                        <Badge
                          label={lot.risk_class}
                          variant={lot.risk_class === 'high' ? 'red' : lot.risk_class === 'medium' ? 'orange' : 'green'}
                        />
                      ) : (
                        <span className="text-xs text-gray-300">—</span>
                      )}
                    </td>
                    <td className="py-1.5">
                      <Badge label={lot.status} variant="gray" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
