// components/charts/ParamDeviation.tsx — Recharts horizontal BarChart for z-scores
//
// Displays parameter anomaly z-scores as a horizontal bar chart.
// Data comes exclusively from the backend (ParameterAnomalySummary[]).
// No frontend-generated analytical values.

import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { ParameterAnomalySummary } from '../../types/api';

interface Props {
  anomalies: ParameterAnomalySummary[];
  height?: number;
}

interface TooltipPayloadEntry {
  payload: ParameterAnomalySummary & { absZ: number };
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const a = payload[0].payload;
  return (
    <div className="bg-white border border-gray-200 shadow-sm rounded p-2 text-xs">
      <p className="font-mono font-semibold text-gray-800">{a.param_name}</p>
      <p className="text-gray-600 mt-0.5">z-score: <span className="font-semibold">{a.z_score.toFixed(2)}</span></p>
      <p className="text-gray-500">Observed: {a.observed_value.toFixed(3)}</p>
      <p className="text-gray-500">Baseline μ: {a.baseline_mean.toFixed(3)}</p>
      <p className="text-gray-500">Direction: {a.direction}</p>
      <p className={`mt-0.5 font-medium ${a.severity === 'severe' ? 'text-red-600' : a.severity === 'moderate' ? 'text-orange-500' : 'text-yellow-600'}`}>
        {a.severity}
      </p>
    </div>
  );
}

function barColor(zScore: number): string {
  const abs = Math.abs(zScore);
  if (abs >= 5) return '#ef4444';    // severe — red
  if (abs >= 4) return '#f97316';    // moderate — orange
  return '#f59e0b';                   // mild — amber
}

export default function ParamDeviationChart({ anomalies, height = 200 }: Props) {
  if (!anomalies.length) {
    return (
      <p className="text-sm text-gray-400 py-4 text-center">No parameter anomalies detected.</p>
    );
  }

  // Show top 10 by |z-score|, sorted descending
  const chartData = anomalies
    .slice()
    .sort((a, b) => Math.abs(b.z_score) - Math.abs(a.z_score))
    .slice(0, 10)
    .map(a => ({ ...a, absZ: Math.abs(a.z_score) }));

  const maxZ = Math.max(...chartData.map(d => d.absZ), 1);

  return (
    <ResponsiveContainer width="100%" height={Math.max(height, chartData.length * 28 + 40)}>
      <BarChart
        layout="vertical"
        data={chartData}
        margin={{ top: 4, right: 24, bottom: 4, left: 16 }}
      >
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f3f4f6" />
        <XAxis
          type="number"
          domain={[0, Math.ceil(maxZ) + 1]}
          tickFormatter={v => `${(v as number).toFixed(0)}σ`}
          tick={{ fontSize: 10, fill: '#9ca3af' }}
        />
        <YAxis
          type="category"
          dataKey="param_name"
          tick={{ fontSize: 9, fill: '#6b7280' }}
          width={88}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine x={3} stroke="#6b7280" strokeDasharray="4 3" label={{ value: '3σ', position: 'top', fontSize: 9, fill: '#6b7280' }} />
        <Bar dataKey="absZ" name="|z-score|" isAnimationActive={false} radius={[0, 3, 3, 0]}>
          {chartData.map((entry, index) => (
            <Cell key={index} fill={barColor(entry.z_score)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
