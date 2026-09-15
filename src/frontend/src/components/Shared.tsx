// src/components/Shared.tsx — Shared UI primitives

import React from 'react';

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------
interface BadgeProps { label: string; variant: 'red' | 'orange' | 'yellow' | 'green' | 'blue' | 'gray' }
export function Badge({ label, variant }: BadgeProps) {
  const colors: Record<string, string> = {
    red:    'bg-red-100 text-red-800 border border-red-200',
    orange: 'bg-orange-100 text-orange-800 border border-orange-200',
    yellow: 'bg-yellow-100 text-yellow-800 border border-yellow-200',
    green:  'bg-green-100 text-green-800 border border-green-200',
    blue:   'bg-blue-100 text-blue-800 border border-blue-200',
    gray:   'bg-gray-100 text-gray-700 border border-gray-200',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors[variant]}`}>
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Severity badge helpers
// ---------------------------------------------------------------------------
export function severityBadge(sev: string) {
  const map: Record<string, 'red' | 'orange' | 'yellow' | 'green' | 'gray'> = {
    severe: 'red', moderate: 'orange', mild: 'yellow', none: 'green',
  };
  return <Badge label={sev} variant={map[sev] ?? 'gray'} />;
}

export function riskBadge(cls: string | null) {
  if (!cls) return <Badge label="—" variant="gray" />;
  const map: Record<string, 'red' | 'orange' | 'green'> = { high: 'red', medium: 'orange', low: 'green' };
  return <Badge label={cls} variant={map[cls] ?? 'gray'} />;
}

// ---------------------------------------------------------------------------
// Spinner
// ---------------------------------------------------------------------------
export function Spinner() {
  return (
    <div className="flex items-center justify-center p-10">
      <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// ErrorMessage
// ---------------------------------------------------------------------------
export function ErrorMessage({ msg }: { msg: string }) {
  return (
    <div className="rounded border border-red-200 bg-red-50 p-4 text-red-700 text-sm">
      <strong>Error:</strong> {msg}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------
export function Card({ title, children, className = '' }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white border border-gray-200 rounded-lg shadow-sm ${className}`}>
      {title && (
        <div className="px-4 py-3 border-b border-gray-100">
          <h3 className="font-semibold text-gray-700 text-sm uppercase tracking-wide">{title}</h3>
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// KPI tile
// ---------------------------------------------------------------------------
export function KpiTile({ label, value, sub, accent = false }: { label: string; value: string | number; sub?: string; accent?: boolean }) {
  return (
    <div className={`rounded-lg border p-4 ${accent ? 'bg-blue-50 border-blue-200' : 'bg-white border-gray-200'}`}>
      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-2xl font-bold ${accent ? 'text-blue-700' : 'text-gray-800'}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Disclaimer banner — used on root-cause and pre-run screens
// ---------------------------------------------------------------------------
export function DisclaimerBanner({ text }: { text: string }) {
  return (
    <div className="rounded border border-amber-200 bg-amber-50 px-4 py-2 text-amber-700 text-xs flex gap-2 items-start">
      <span className="text-amber-500 font-bold mt-0.5">⚠</span>
      <span>{text}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// WaferMap — SVG defect map for a single wafer
// ---------------------------------------------------------------------------
interface WaferMapProps {
  defects: Array<{ x: number; y: number }>;
  patternType: string;
  size?: number;
}
export function WaferMap({ defects, patternType, size = 140 }: WaferMapProps) {
  const R = 150; // wafer radius in mm
  const s = size / 2 / R; // scale mm → px

  const patternColors: Record<string, string> = {
    center_heavy:     '#ef4444',
    edge_ring:        '#f97316',
    localized_hotspot:'#a855f7',
    radial:           '#3b82f6',
    scratch_line:     '#ec4899',
    uniform:          '#6b7280',
    insufficient_data:'#d1d5db',
  };
  const dotColor = patternColors[patternType] ?? '#6b7280';

  return (
    <svg width={size} height={size} viewBox={`${-size/2} ${-size/2} ${size} ${size}`}>
      {/* Wafer outline */}
      <circle cx={0} cy={0} r={size / 2 - 2} fill="#f8fafc" stroke="#94a3b8" strokeWidth={1.5} />
      {/* Exclusion zone ring */}
      <circle cx={0} cy={0} r={(size / 2 - 2) * 0.93} fill="none" stroke="#cbd5e1" strokeWidth={0.5} strokeDasharray="3,3" />
      {/* Defect dots */}
      {defects.map((d, i) => (
        <circle
          key={i}
          cx={d.x * s}
          cy={d.y * s}
          r={1.8}
          fill={dotColor}
          opacity={0.75}
        />
      ))}
      {/* Centre cross */}
      <line x1={-4} y1={0} x2={4} y2={0} stroke="#94a3b8" strokeWidth={0.5} />
      <line x1={0} y1={-4} x2={0} y2={4} stroke="#94a3b8" strokeWidth={0.5} />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Score bar
// ---------------------------------------------------------------------------
export function ScoreBar({ score, max = 1.0 }: { score: number; max?: number }) {
  const pct = Math.min(100, (score / max) * 100);
  const color = pct > 65 ? 'bg-red-500' : pct > 35 ? 'bg-orange-400' : 'bg-green-500';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-600 w-10 text-right">{(score * 100).toFixed(0)}%</span>
    </div>
  );
}
