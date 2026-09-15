// screens/WaferPatternScreen.tsx — Screen 3: Wafer Defect Pattern Lab

import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { LotListResponse, WaferPatternResponse } from '../types/api';
import { Card, Spinner, ErrorMessage, Badge, WaferMap, DisclaimerBanner } from '../components/Shared';

const PATTERN_COLORS: Record<string, string> = {
  center_heavy:      'bg-red-100 text-red-700 border-red-200',
  edge_ring:         'bg-orange-100 text-orange-700 border-orange-200',
  localized_hotspot: 'bg-purple-100 text-purple-700 border-purple-200',
  radial:            'bg-blue-100 text-blue-700 border-blue-200',
  scratch_line:      'bg-pink-100 text-pink-700 border-pink-200',
  uniform:           'bg-gray-100 text-gray-600 border-gray-200',
  insufficient_data: 'bg-gray-50 text-gray-400 border-gray-100',
};

function patternBadge(type: string) {
  const cls = PATTERN_COLORS[type] ?? 'bg-gray-100 text-gray-500 border-gray-200';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium ${cls}`}>
      {type.replace('_', ' ')}
    </span>
  );
}

// Synthetic defect coords for display: real defects not stored in frontend —
// we render a placeholder pattern based on pattern_type + count
function syntheticDefects(patternType: string, count: number): Array<{ x: number; y: number }> {
  const rng = (seed: number) => {
    let s = seed;
    return () => { s = (s * 1664525 + 1013904223) & 0xffffffff; return (s >>> 0) / 0xffffffff; };
  };
  const rand = rng(count * 31 + patternType.charCodeAt(0));
  const pts: Array<{ x: number; y: number }> = [];
  const n = Math.min(count, 120);
  for (let i = 0; i < n; i++) {
    let x = 0; let y = 0;
    if (patternType === 'center_heavy') {
      const r = rand() * 38; const t = rand() * 2 * Math.PI;
      x = r * Math.cos(t); y = r * Math.sin(t);
    } else if (patternType === 'edge_ring') {
      const r = 122 + rand() * 26; const t = rand() * 2 * Math.PI;
      x = r * Math.cos(t); y = r * Math.sin(t);
    } else if (patternType === 'scratch_line') {
      x = rand() * 240 - 120; y = (rand() - 0.5) * 8;
    } else if (patternType === 'radial') {
      const spoke = Math.floor(rand() * 6);
      const angle = (spoke * Math.PI) / 3 + (rand() - 0.5) * 0.15;
      const r = rand() * 130;
      x = r * Math.cos(angle); y = r * Math.sin(angle);
    } else if (patternType === 'localized_hotspot') {
      const cx = 60; const cy = 40;
      x = cx + (rand() - 0.5) * 30; y = cy + (rand() - 0.5) * 30;
    } else {
      const r = rand() * 140; const t = rand() * 2 * Math.PI;
      x = r * Math.cos(t); y = r * Math.sin(t);
    }
    pts.push({ x, y });
  }
  return pts;
}

export default function WaferPatternScreen() {
  const [lots, setLots] = useState<LotListResponse | null>(null);
  const [selectedLot, setSelectedLot] = useState<string | null>(null);
  const [patterns, setPatterns] = useState<WaferPatternResponse | null>(null);
  const [loadingLots, setLoadingLots] = useState(true);
  const [loadingPatterns, setLoadingPatterns] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterText, setFilterText] = useState('');

  useEffect(() => {
    api.lots({ page: 1, page_size: 200 })
      .then(setLots)
      .catch(e => setError(String(e)))
      .finally(() => setLoadingLots(false));
  }, []);

  const handleSelectLot = (lotIdStr: string) => {
    setSelectedLot(lotIdStr);
    setPatterns(null);
    setLoadingPatterns(true);
    api.lotPatterns(lotIdStr, 5)
      .then(setPatterns)
      .catch(e => setError(String(e)))
      .finally(() => setLoadingPatterns(false));
  };

  const filteredLots = (lots?.lots ?? []).filter(l =>
    !filterText || l.lot_id_str.includes(filterText) || l.product.includes(filterText)
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800">Wafer Pattern Lab</h1>
        <DisclaimerBanner
          text="Pattern heuristics are for demonstration only. Not production-certified defect classification."
        />
      </div>

      <div className="flex gap-4">
        {/* Lot selector */}
        <div className="w-64 flex-shrink-0">
          <Card title="Select Lot">
            <input
              type="text"
              placeholder="Filter lots…"
              value={filterText}
              onChange={e => setFilterText(e.target.value)}
              className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm mb-2 focus:outline-none focus:border-blue-400"
            />
            {loadingLots ? <Spinner /> : (
              <div className="max-h-[65vh] overflow-y-auto space-y-0.5">
                {filteredLots.map(lot => (
                  <button
                    key={lot.lot_id}
                    onClick={() => handleSelectLot(lot.lot_id_str)}
                    className={`w-full text-left px-3 py-2 rounded text-sm ${
                      selectedLot === lot.lot_id_str
                        ? 'bg-blue-100 text-blue-800 font-semibold'
                        : 'hover:bg-gray-50 text-gray-700'
                    }`}
                  >
                    <span className="font-mono text-xs">{lot.lot_id_str}</span>
                    <span className="text-gray-400 text-xs ml-2">{lot.product}</span>
                  </button>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Pattern display */}
        <div className="flex-1">
          {!selectedLot && (
            <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
              Select a lot to inspect wafer defect patterns.
            </div>
          )}
          {loadingPatterns && <Spinner />}
          {error && <ErrorMessage msg={error} />}

          {patterns && (
            <Card title={`Defect Patterns — ${patterns.lot_id_str} (${patterns.patterns.length} wafers sampled)`}>
              {patterns.patterns.length === 0 ? (
                <p className="text-sm text-gray-400">No wafer patterns returned.</p>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6">
                  {patterns.patterns.map(p => {
                    const defectPts = syntheticDefects(p.pattern_type, p.defect_count);
                    return (
                      <div key={p.wafer_id} className="flex flex-col items-center gap-2">
                        <p className="text-xs text-gray-400">Wafer #{p.wafer_id}</p>
                        <WaferMap
                          defects={defectPts}
                          patternType={p.pattern_type}
                          size={140}
                        />
                        <div className="text-center space-y-1">
                          {patternBadge(p.pattern_type)}
                          <p className="text-xs text-gray-400">
                            Score: {(p.pattern_score * 100).toFixed(0)}% · {p.defect_count} defects
                          </p>
                        </div>
                        {/* Spatial stats */}
                        <div className="w-full text-xs text-gray-400 space-y-0.5">
                          {Object.entries(p.spatial_statistics)
                            .filter(([k]) => ['center_ratio', 'edge_ratio', 'cluster_fraction'].includes(k))
                            .map(([k, v]) => (
                              <div key={k} className="flex justify-between">
                                <span>{k.replace('_', ' ')}</span>
                                <span className="font-mono">{(v * 100).toFixed(0)}%</span>
                              </div>
                            ))
                          }
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Pattern legend */}
              <div className="mt-6 pt-4 border-t border-gray-100">
                <p className="text-xs text-gray-400 mb-2 font-medium uppercase">Pattern Legend</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(PATTERN_COLORS).map(([pt]) => (
                    <span key={pt}>{patternBadge(pt)}</span>
                  ))}
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
