// screens/MonitorScreen.tsx — Screen 1: Fleet monitoring dashboard
// Includes inline SVG yield trend chart (no external chart library dependency)

import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type {
  FleetYieldSummary,
  LotListResponse,
  ChamberRecurrenceResponse,
  YieldTrendResponse,
} from '../types/api';
import { KpiTile, Card, Badge, severityBadge, Spinner, ErrorMessage } from '../components/Shared';

// ---------------------------------------------------------------------------
// Inline SVG Yield Trend Chart
// ---------------------------------------------------------------------------

interface TrendChartProps {
  data: YieldTrendResponse;
  width?: number;
  height?: number;
}

function YieldTrendChart({ data, width = 700, height = 180 }: TrendChartProps) {
  if (!data.points.length) return (
    <p className="text-sm text-gray-400 py-4 text-center">No trend data available.</p>
  );

  const PAD = { top: 10, right: 16, bottom: 30, left: 52 };
  const W = width - PAD.left - PAD.right;
  const H = height - PAD.top - PAD.bottom;

  const yields = data.points.map(p => p.mean_yield);
  const minY = Math.max(0, Math.min(...yields) - 0.02);
  const maxY = Math.min(1, Math.max(...yields) + 0.02);

  const scaleX = (i: number) => (i / (data.points.length - 1)) * W;
  const scaleY = (v: number) => H - ((v - minY) / (maxY - minY)) * H;

  // Polyline points
  const linePts = data.points
    .map((_, i) => `${scaleX(i)},${scaleY(yields[i])}`)
    .join(' ');

  // Fleet mean and excursion threshold lines
  const fleetY = scaleY(data.fleet_mean);
  const thrY = scaleY(data.excursion_threshold);

  // Y-axis ticks
  const yTicks = Array.from({ length: 5 }, (_, i) => {
    const v = minY + ((maxY - minY) * i) / 4;
    return { v, y: scaleY(v) };
  });

  // X-axis: first / mid / last dates
  const dates = data.points.map(p => new Date(p.actual_start_at));
  const xLabels = [0, Math.floor(data.points.length / 2), data.points.length - 1]
    .filter(i => i >= 0 && i < data.points.length)
    .map(i => ({
      x: scaleX(i),
      label: dates[i].toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    }));

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      style={{ height, fontFamily: 'inherit' }}
    >
      <g transform={`translate(${PAD.left},${PAD.top})`}>
        {/* Grid + y-axis ticks */}
        {yTicks.map(({ v, y }) => (
          <g key={v}>
            <line x1={0} y1={y} x2={W} y2={y} stroke="#e5e7eb" strokeWidth={1} />
            <text x={-6} y={y + 4} fontSize={9} fill="#9ca3af" textAnchor="end">
              {(v * 100).toFixed(0)}%
            </text>
          </g>
        ))}

        {/* Excursion threshold band */}
        <rect
          x={0} y={thrY}
          width={W} height={Math.max(0, H - thrY)}
          fill="#fef2f2"
          opacity={0.6}
        />

        {/* Threshold line */}
        <line
          x1={0} y1={thrY} x2={W} y2={thrY}
          stroke="#f87171" strokeWidth={1} strokeDasharray="4 3"
        />
        <text x={W + 2} y={thrY + 3} fontSize={8} fill="#f87171">thr</text>

        {/* Fleet mean line */}
        <line
          x1={0} y1={fleetY} x2={W} y2={fleetY}
          stroke="#6b7280" strokeWidth={1} strokeDasharray="6 3"
        />
        <text x={W + 2} y={fleetY + 3} fontSize={8} fill="#6b7280">μ</text>

        {/* Trend polyline */}
        <polyline
          points={linePts}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={1.5}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* Excursion dots */}
        {data.points.map((p, i) =>
          p.is_excursion ? (
            <circle
              key={i}
              cx={scaleX(i)}
              cy={scaleY(p.mean_yield)}
              r={3.5}
              fill="#ef4444"
              opacity={0.85}
            />
          ) : null
        )}

        {/* X-axis labels */}
        {xLabels.map(({ x, label }, li) => (
          <text key={li} x={x} y={H + 16} fontSize={9} fill="#9ca3af" textAnchor="middle">
            {label}
          </text>
        ))}

        {/* Axes */}
        <line x1={0} y1={0} x2={0} y2={H} stroke="#d1d5db" />
        <line x1={0} y1={H} x2={W} y2={H} stroke="#d1d5db" />
      </g>

      {/* Legend */}
      <g transform={`translate(${PAD.left + 4}, ${height - 4})`}>
        <line x1={0} y1={0} x2={14} y2={0} stroke="#3b82f6" strokeWidth={1.5} />
        <text x={18} y={3} fontSize={8} fill="#6b7280">Lot yield</text>
        <circle cx={70} cy={0} r={3} fill="#ef4444" />
        <text x={76} y={3} fontSize={8} fill="#6b7280">Excursion</text>
        <line x1={120} y1={0} x2={134} y2={0} stroke="#6b7280" strokeWidth={1} strokeDasharray="4 2" />
        <text x={138} y={3} fontSize={8} fill="#6b7280">Fleet μ</text>
      </g>
    </svg>
  );
}


// ---------------------------------------------------------------------------
// MonitorScreen
// ---------------------------------------------------------------------------

export default function MonitorScreen() {
  const [fleet, setFleet] = useState<FleetYieldSummary | null>(null);
  const [lots, setLots] = useState<LotListResponse | null>(null);
  const [chambers, setChambers] = useState<ChamberRecurrenceResponse | null>(null);
  const [trend, setTrend] = useState<YieldTrendResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      api.fleetSummary(),
      api.lots({ page: 1, page_size: 20, excursion_only: false }),
      api.chamberRecurrence(),
      api.yieldTrend(150),
    ])
      .then(([f, l, c, t]) => {
        setFleet(f);
        setLots(l);
        setChambers(c);
        setTrend(t);
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
    // 30-second auto-refresh
    const id = setInterval(loadData, 30_000);
    return () => clearInterval(id);
  }, []);

  if (loading) return <Spinner />;
  if (error) return <ErrorMessage msg={error} />;

  const excursionLots = lots?.lots.filter(l => l.excursion) ?? [];
  const recurrentChambers = chambers?.chambers.filter(c => c.is_recurrent) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800">Fab Monitor — Fleet Overview</h1>
        <span className="text-xs text-gray-400">Auto-refreshes every 30 s</span>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <KpiTile
          label="Fleet Mean Yield"
          value={fleet ? `${(fleet.fleet_mean_yield * 100).toFixed(2)}%` : '—'}
          sub={fleet ? `σ = ${(fleet.fleet_std_yield * 100).toFixed(2)}%` : undefined}
          accent
        />
        <KpiTile
          label="Excursions (7d)"
          value={fleet?.excursion_count_7d ?? '—'}
        />
        <KpiTile
          label="Excursions (30d)"
          value={fleet?.excursion_count_30d ?? '—'}
        />
        <KpiTile
          label="Recurrent Chambers"
          value={recurrentChambers.length}
        />
        <KpiTile
          label="Lots Analysed"
          value={lots?.meta.total ?? '—'}
        />
      </div>

      {/* Yield Trend Chart */}
      <Card title={`Yield Trend (last ${trend?.points.length ?? 0} lots) — fleet μ ${trend ? (trend.fleet_mean * 100).toFixed(2) + '%' : ''}`}>
        {trend ? (
          <YieldTrendChart data={trend} height={190} />
        ) : (
          <Spinner />
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent excursion lots */}
        <Card title={`Yield Excursions (${excursionLots.length})`}>
          {excursionLots.length === 0 ? (
            <p className="text-sm text-gray-400">No excursions detected in loaded window.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400 border-b">
                    <th className="pb-2 pr-3">Lot</th>
                    <th className="pb-2 pr-3">Product</th>
                    <th className="pb-2 pr-3">Yield</th>
                    <th className="pb-2">Severity</th>
                  </tr>
                </thead>
                <tbody>
                  {excursionLots.map(lot => (
                    <tr key={lot.lot_id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="py-1.5 pr-3 font-mono text-xs text-blue-700">{lot.lot_id_str}</td>
                      <td className="py-1.5 pr-3 text-gray-600 truncate max-w-[120px]">{lot.product}</td>
                      <td className="py-1.5 pr-3 font-semibold text-red-600">
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

        {/* Chamber recurrence */}
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
                      <td className="py-1.5 pr-3 text-red-600 font-semibold">
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
                          <span className="text-xs font-mono">{(c.recurrence_score * 100).toFixed(0)}</span>
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

      {/* All lots table */}
      <Card title={`All Lots (showing ${lots?.lots.length ?? 0} of ${lots?.meta.total ?? 0})`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b">
                <th className="pb-2 pr-3">Lot ID</th>
                <th className="pb-2 pr-3">Product</th>
                <th className="pb-2 pr-3">Node</th>
                <th className="pb-2 pr-3">Priority</th>
                <th className="pb-2 pr-3">Start</th>
                <th className="pb-2 pr-3">Yield</th>
                <th className="pb-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {(lots?.lots ?? []).map(lot => (
                <tr key={lot.lot_id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-1.5 pr-3 font-mono text-xs text-blue-700">{lot.lot_id_str}</td>
                  <td className="py-1.5 pr-3 truncate max-w-[100px]">{lot.product}</td>
                  <td className="py-1.5 pr-3 text-gray-500 text-xs">{lot.technology_node}</td>
                  <td className="py-1.5 pr-3">
                    <Badge
                      label={lot.priority}
                      variant={lot.priority === 'high' ? 'red' : lot.priority === 'low' ? 'gray' : 'blue'}
                    />
                  </td>
                  <td className="py-1.5 pr-3 text-gray-400 text-xs">
                    {lot.actual_start_at ? new Date(lot.actual_start_at).toLocaleDateString() : '—'}
                  </td>
                  <td className={`py-1.5 pr-3 font-semibold text-xs ${lot.excursion ? 'text-red-600' : 'text-green-600'}`}>
                    {lot.mean_yield != null ? `${(lot.mean_yield * 100).toFixed(1)}%` : '—'}
                  </td>
                  <td className="py-1.5">
                    {lot.excursion
                      ? severityBadge(lot.excursion_severity)
                      : <Badge label="OK" variant="green" />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
