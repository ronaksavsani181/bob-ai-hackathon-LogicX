// screens/InvestigateScreen.tsx — Screen 2: Lot investigation detail

import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { LotListResponse, LotDetailResponse } from '../types/api';
import {
  Card, Spinner, ErrorMessage, Badge, severityBadge, DisclaimerBanner, ScoreBar,
} from '../components/Shared';

export default function InvestigateScreen() {
  const [lots, setLots] = useState<LotListResponse | null>(null);
  const [selectedLot, setSelectedLot] = useState<string | null>(null);
  const [detail, setDetail] = useState<LotDetailResponse | null>(null);
  const [loadingLots, setLoadingLots] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterText, setFilterText] = useState('');
  const [excursionOnly, setExcursionOnly] = useState(false);

  useEffect(() => {
    api.lots({ page: 1, page_size: 100 })
      .then(setLots)
      .catch(e => setError(String(e)))
      .finally(() => setLoadingLots(false));
  }, []);

  const handleSelectLot = (lotIdStr: string) => {
    setSelectedLot(lotIdStr);
    setDetail(null);
    setLoadingDetail(true);
    api.lotDetail(lotIdStr)
      .then(setDetail)
      .catch(e => setError(String(e)))
      .finally(() => setLoadingDetail(false));
  };

  const filteredLots = (lots?.lots ?? []).filter(l => {
    const matchText = !filterText || l.lot_id_str.includes(filterText) || l.product.includes(filterText);
    const matchExc = !excursionOnly || l.excursion;
    return matchText && matchExc;
  });

  return (
    <div className="flex gap-4 h-full">
      {/* Left panel — lot selector */}
      <div className="w-72 flex-shrink-0">
        <Card title="Select Lot">
          <div className="space-y-2 mb-3">
            <input
              type="text"
              placeholder="Filter by lot ID or product…"
              value={filterText}
              onChange={e => setFilterText(e.target.value)}
              className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-blue-400"
            />
            <label className="flex items-center gap-2 text-xs text-gray-500 cursor-pointer">
              <input type="checkbox" checked={excursionOnly} onChange={e => setExcursionOnly(e.target.checked)} />
              Excursions only
            </label>
          </div>
          {loadingLots ? <Spinner /> : (
            <div className="max-h-[60vh] overflow-y-auto space-y-0.5">
              {filteredLots.map(lot => (
                <button
                  key={lot.lot_id}
                  onClick={() => handleSelectLot(lot.lot_id_str)}
                  className={`w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                    selectedLot === lot.lot_id_str
                      ? 'bg-blue-100 text-blue-800 font-semibold'
                      : 'hover:bg-gray-50 text-gray-700'
                  }`}
                >
                  <div className="flex justify-between items-center">
                    <span className="font-mono text-xs">{lot.lot_id_str}</span>
                    {lot.excursion && (
                      <span className="text-red-500 text-xs">⚠</span>
                    )}
                  </div>
                  <div className="text-gray-400 text-xs">{lot.product}</div>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Right panel — lot detail */}
      <div className="flex-1 space-y-4">
        {!selectedLot && (
          <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
            Select a lot from the left panel to investigate.
          </div>
        )}
        {loadingDetail && <Spinner />}
        {error && <ErrorMessage msg={error} />}

        {detail && (
          <>
            {/* Lot header */}
            <Card>
              <div className="flex flex-wrap gap-6 items-start">
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
                  <Badge label={detail.priority}
                    variant={detail.priority === 'high' ? 'red' : detail.priority === 'low' ? 'gray' : 'blue'} />
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase">Status</p>
                  <Badge label={detail.status} variant="gray" />
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase">Mean Yield</p>
                  <p className={`font-bold text-lg ${detail.yield_excursion?.is_excursion ? 'text-red-600' : 'text-green-600'}`}>
                    {detail.mean_yield != null ? `${(detail.mean_yield * 100).toFixed(2)}%` : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase">Wafers</p>
                  <p className="text-gray-700">{detail.wafer_count}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase">Queue Time</p>
                  <p className="text-gray-700">{detail.queue_time_h != null ? `${detail.queue_time_h.toFixed(1)}h` : '—'}</p>
                </div>
              </div>
            </Card>

            {/* Yield excursion */}
            {detail.yield_excursion && (
              <Card title="Yield Excursion Detection">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <p className="text-xs text-gray-400">Observed Yield</p>
                    <p className="font-semibold text-red-600">
                      {(detail.yield_excursion.observed_yield * 100).toFixed(2)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400">Baseline Yield</p>
                    <p className="font-semibold">
                      {(detail.yield_excursion.baseline_yield * 100).toFixed(2)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400">Deviation (σ)</p>
                    <p className="font-semibold text-red-600">
                      {detail.yield_excursion.deviation_sigma.toFixed(2)}σ
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400">Severity</p>
                    {severityBadge(detail.yield_excursion.severity)}
                  </div>
                </div>
                <p className="text-xs text-gray-400 mt-3">Method: {detail.yield_excursion.method}</p>
                <p className="text-xs text-gray-300 mt-0.5 font-mono">EID: {detail.yield_excursion.evidence_id}</p>
              </Card>
            )}

            {/* Parameter anomalies */}
            <Card title={`Process Parameter Anomalies (${detail.parameter_anomalies.length})`}>
              {detail.parameter_anomalies.length === 0 ? (
                <p className="text-sm text-gray-400">No parameter anomalies detected (|z| &lt; 3.0).</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-400 border-b">
                      <th className="pb-2 pr-3">Parameter</th>
                      <th className="pb-2 pr-3">Observed</th>
                      <th className="pb-2 pr-3">Baseline μ</th>
                      <th className="pb-2 pr-3">z-score</th>
                      <th className="pb-2 pr-3">Direction</th>
                      <th className="pb-2">Severity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.parameter_anomalies.map((a, i) => (
                      <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-1.5 pr-3 font-mono text-xs">{a.param_name}</td>
                        <td className="py-1.5 pr-3">{a.observed_value.toFixed(3)}</td>
                        <td className="py-1.5 pr-3 text-gray-400">{a.baseline_mean.toFixed(3)}</td>
                        <td className={`py-1.5 pr-3 font-semibold ${Math.abs(a.z_score) > 4 ? 'text-red-600' : 'text-orange-500'}`}>
                          {a.z_score.toFixed(2)}
                        </td>
                        <td className="py-1.5 pr-3">
                          <Badge label={a.direction} variant={a.direction === 'high' ? 'orange' : 'blue'} />
                        </td>
                        <td className="py-1.5">{severityBadge(a.severity)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
