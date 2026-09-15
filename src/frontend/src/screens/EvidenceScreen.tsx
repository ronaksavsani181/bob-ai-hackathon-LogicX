// screens/EvidenceScreen.tsx — Screen 5: Evidence viewer for a lot

import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { LotListResponse, RootCauseResponse } from '../types/api';
import { Card, Spinner, ErrorMessage, Badge, DisclaimerBanner, ScoreBar } from '../components/Shared';

export default function EvidenceScreen() {
  const [lots, setLots] = useState<LotListResponse | null>(null);
  const [selectedLot, setSelectedLot] = useState<string | null>(null);
  const [rootCause, setRootCause] = useState<RootCauseResponse | null>(null);
  const [loadingLots, setLoadingLots] = useState(true);
  const [loadingRC, setLoadingRC] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterText, setFilterText] = useState('');

  useEffect(() => {
    api.lots({ page: 1, page_size: 200, excursion_only: false })
      .then(setLots)
      .catch(e => setError(String(e)))
      .finally(() => setLoadingLots(false));
  }, []);

  const handleSelectLot = (lotIdStr: string) => {
    setSelectedLot(lotIdStr);
    setRootCause(null);
    setError(null);
    setLoadingRC(true);
    api.lotRootCause(lotIdStr)
      .then(setRootCause)
      .catch(e => setError(String(e)))
      .finally(() => setLoadingRC(false));
  };

  const filteredLots = (lots?.lots ?? []).filter(l =>
    !filterText || l.lot_id_str.includes(filterText) || l.product.includes(filterText)
  );

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-gray-800">Evidence Viewer</h1>

      <div className="flex gap-4">
        {/* Lot picker */}
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
                    <div className="flex justify-between">
                      <span className="font-mono text-xs">{lot.lot_id_str}</span>
                      {lot.excursion && <span className="text-red-500 text-xs">⚠</span>}
                    </div>
                    <div className="text-gray-400 text-xs">{lot.product}</div>
                  </button>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Evidence panel */}
        <div className="flex-1 space-y-4">
          {!selectedLot && (
            <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
              Select a lot to view root-cause evidence.
            </div>
          )}
          {loadingRC && <Spinner />}
          {error && <ErrorMessage msg={error} />}

          {rootCause && (
            <>
              <DisclaimerBanner text={rootCause.disclaimer} />

              {rootCause.insufficient_evidence ? (
                <Card title="Insufficient Evidence">
                  <p className="text-sm text-gray-500">
                    No evidence signal reached the minimum threshold for this lot.
                    The lot may require manual review or more process data.
                  </p>
                  <div className="mt-3 text-xs text-gray-400 space-y-1">
                    {Object.entries(rootCause.evidence_summary).map(([k, v]) => (
                      <div key={k} className="flex justify-between">
                        <span>{k.replace(/_/g, ' ')}</span>
                        <span className="font-mono">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                </Card>
              ) : (
                <>
                  <Card title={`Root-Cause Candidates — Lot ${rootCause.lot_id_str}`}>
                    <p className="text-xs text-gray-400 mb-4">
                      Model: {rootCause.model_version} · Generated: {new Date(rootCause.generated_at).toLocaleString()}
                    </p>
                    <div className="space-y-4">
                      {rootCause.candidates.map(c => (
                        <div key={c.rank} className={`rounded-lg border p-4 ${
                          c.rank === 1 ? 'border-blue-300 bg-blue-50' : 'border-gray-200 bg-white'
                        }`}>
                          <div className="flex items-start justify-between mb-2">
                            <div>
                              <span className="text-xs font-bold text-gray-400 mr-2">#{c.rank}</span>
                              <span className="font-semibold text-gray-800">{c.cause_description}</span>
                            </div>
                            <div className="flex gap-2 items-center">
                              <Badge label={c.cause_type} variant="blue" />
                              {c.temporal_precedence && (
                                <Badge label="⏱ temporal" variant="green" />
                              )}
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-3 mb-3">
                            <div>
                              <p className="text-xs text-gray-400 mb-1">Score</p>
                              <ScoreBar score={c.score} />
                            </div>
                            <div>
                              <p className="text-xs text-gray-400 mb-1">Confidence</p>
                              <ScoreBar score={c.confidence} />
                            </div>
                          </div>

                          {/* Supporting signals */}
                          {Object.keys(c.supporting_signals).length > 0 && (
                            <div className="mb-2">
                              <p className="text-xs font-medium text-green-700 mb-1">Supporting signals</p>
                              <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
                                {Object.entries(c.supporting_signals).map(([sig, val]) => (
                                  <div key={sig} className="flex justify-between text-xs">
                                    <span className="text-gray-500">{sig.replace(/_/g, ' ')}</span>
                                    <span className="font-mono text-green-600">{(val * 100).toFixed(0)}%</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Contradicting signals */}
                          {Object.keys(c.contradicting_signals).length > 0 && (
                            <div className="mb-2">
                              <p className="text-xs font-medium text-red-700 mb-1">Contradicting signals</p>
                              <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
                                {Object.entries(c.contradicting_signals).map(([sig, val]) => (
                                  <div key={sig} className="flex justify-between text-xs">
                                    <span className="text-gray-500">{sig.replace(/_/g, ' ')}</span>
                                    <span className="font-mono text-red-500">{(val * 100).toFixed(0)}%</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Evidence IDs */}
                          <div className="mt-2 pt-2 border-t border-gray-100">
                            <p className="text-xs text-gray-400 mb-1">Evidence IDs</p>
                            <div className="flex flex-wrap gap-1">
                              {c.evidence_ids.slice(0, 8).map(eid => (
                                <code key={eid} className="text-xs bg-gray-100 px-1.5 py-0.5 rounded font-mono text-gray-600">
                                  {eid}
                                </code>
                              ))}
                              {c.evidence_ids.length > 8 && (
                                <span className="text-xs text-gray-400">+{c.evidence_ids.length - 8} more</span>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>

                  {/* Evidence summary */}
                  <Card title="Evidence Summary">
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                      {Object.entries(rootCause.evidence_summary).map(([k, v]) => (
                        <div key={k}>
                          <p className="text-xs text-gray-400">{k.replace(/_/g, ' ')}</p>
                          <p className="font-semibold text-gray-700">{String(v)}</p>
                        </div>
                      ))}
                    </div>
                  </Card>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
