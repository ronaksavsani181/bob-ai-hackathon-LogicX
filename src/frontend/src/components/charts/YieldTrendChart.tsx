// components/charts/YieldTrendChart.tsx — Recharts LineChart for yield trend
//
// Displays per-lot yield trend with:
//   - Blue line for lot yield
//   - Red dots for excursion lots
//   - Dashed reference lines for fleet mean and excursion threshold
//   - Chamber-aware colouring via scenario_hint (demo only — never used in analytics)
//   - Tooltip showing lot ID, yield, and excursion flag

import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Dot,
} from 'recharts';
import type { YieldTrendResponse, YieldTrendPoint } from '../../types/api';

interface Props {
  data: YieldTrendResponse;
  height?: number;
}

interface ChartPoint extends YieldTrendPoint {
  yieldPct: number;
  dateLabel: string;
}

interface CustomDotProps {
  cx?: number;
  cy?: number;
  payload?: ChartPoint;
}

function ExcursionDot({ cx, cy, payload }: CustomDotProps) {
  if (!payload?.is_excursion || cx == null || cy == null) return null;
  return <circle cx={cx} cy={cy} r={5} fill="#ef4444" stroke="#fff" strokeWidth={1.5} />;
}

interface TooltipPayloadEntry {
  payload: ChartPoint;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const pt = payload[0].payload;
  return (
    <div className="bg-white border border-gray-200 shadow-sm rounded p-2 text-xs">
      <p className="font-mono font-semibold text-gray-800">{pt.lot_id_str}</p>
      <p className="text-gray-500">{pt.dateLabel}</p>
      <p className={`font-semibold mt-0.5 ${pt.is_excursion ? 'text-red-600' : 'text-green-600'}`}>
        Yield: {pt.yieldPct.toFixed(2)}%
      </p>
      {pt.is_excursion && (
        <p className="text-red-500 mt-0.5">⚠ Excursion detected</p>
      )}
      {pt.scenario_hint && (
        <p className="text-gray-400 mt-0.5">{pt.scenario_hint}</p>
      )}
    </div>
  );
}

export default function YieldTrendChart({ data, height = 240 }: Props) {
  if (!data.points.length) {
    return (
      <p className="text-sm text-gray-400 py-4 text-center">No trend data available.</p>
    );
  }

  const chartData: ChartPoint[] = data.points.map(p => ({
    ...p,
    yieldPct: p.mean_yield * 100,
    dateLabel: new Date(p.actual_start_at).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    }),
  }));

  const fleetPct = data.fleet_mean * 100;
  const threshPct = data.excursion_threshold * 100;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 8, right: 24, bottom: 4, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis
          dataKey="dateLabel"
          tick={{ fontSize: 10, fill: '#9ca3af' }}
          interval="preserveStartEnd"
        />
        <YAxis
          tickFormatter={v => `${(v as number).toFixed(0)}%`}
          tick={{ fontSize: 10, fill: '#9ca3af' }}
          domain={['auto', 'auto']}
          width={44}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 10, paddingTop: 4 }}
          formatter={value => (value === 'yieldPct' ? 'Lot yield' : String(value))}
        />
        <ReferenceLine y={fleetPct} stroke="#6b7280" strokeDasharray="6 3" label={{ value: 'Fleet μ', position: 'insideTopRight', fontSize: 9, fill: '#6b7280' }} />
        <ReferenceLine y={threshPct} stroke="#f87171" strokeDasharray="4 3" label={{ value: 'Threshold', position: 'insideBottomRight', fontSize: 9, fill: '#f87171' }} />
        <Line
          type="monotone"
          dataKey="yieldPct"
          stroke="#3b82f6"
          strokeWidth={1.5}
          dot={<ExcursionDot />}
          activeDot={{ r: 4, fill: '#3b82f6' }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
