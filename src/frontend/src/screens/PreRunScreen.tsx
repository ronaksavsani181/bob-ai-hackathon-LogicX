// screens/PreRunScreen.tsx — Screen 4: Pre-run risk assessment

import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { PreRunRiskListResponse } from '../types/api';
import { Card, Spinner, ErrorMessage, KpiTile, Badge, ScoreBar, DisclaimerBanner } from '../components/Shared';

export default function PreRunScreen() {
  const [data, setData] = useState<PreRunRiskListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterClass, setFilterClass] = useState<string>('all');

  const load = () => {
    setLoading(true);
    setError(null);
    api.preRunRisk(100)
      .then(setData)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const assessments = data?.assessments ?? [];
  const filtered = filterClass === 'all'
    ? assessments
    : assessments.filter(a => a.risk_class === filterClass);

  const highCount    = assessments.filter(a => a.risk_class === 'high').length;
  const mediumCount  = assessments.filter(a => a.risk_class === 'medium').length;
  const lowCount     = assessments.filter(a => a.risk_class === 'low').length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800">Pre-Run Risk Assessment</h1>
        <button
          onClick={load}
          className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 transition-colors"
        >
          Refresh Model
        </button>
      </div>

      <DisclaimerBanner text="PRE-RUN SAFETY RULE: This model uses ONLY information available before the lot starts. No future yield, defect, or metrology data is used as input. Predictions are probabilistic and require engineering review before action." />

      {loading && <Spinner />}
      {error && <ErrorMessage msg={error} />}

      {data && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KpiTile label="Total Assessed" value={assessments.length} />
            <KpiTile label="High Risk" value={highCount} accent />
            <KpiTile label="Medium Risk" value={mediumCount} />
            <KpiTile label="Low Risk" value={lowCount} />
          </div>

          {/* Model info */}
          <div className="text-xs text-gray-400">
            Model: <code className="font-mono">{data.model_version}</code> · Generated: {new Date(data.generated_at).toLocaleString()}
          </div>

          {/* Filter buttons */}
          <div className="flex gap-2">
            {['all', 'high', 'medium', 'low'].map(cls => (
              <button
                key={cls}
                onClick={() => setFilterClass(cls)}
                className={`px-3 py-1 rounded text-sm ${
                  filterClass === cls
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {cls === 'all' ? 'All' : cls.charAt(0).toUpperCase() + cls.slice(1)}
                {cls !== 'all' && (
                  <span className="ml-1 text-xs opacity-75">
                    ({cls === 'high' ? highCount : cls === 'medium' ? mediumCount : lowCount})
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Risk table */}
          <Card title={`Risk Assessments (${filtered.length})`}>
            {filtered.length === 0 ? (
              <p className="text-sm text-gray-400">No assessments in this risk class.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-400 border-b">
                      <th className="pb-2 pr-4">Lot ID</th>
                      <th className="pb-2 pr-4">Risk Class</th>
                      <th className="pb-2 pr-4 w-40">Risk Score</th>
                      <th className="pb-2 pr-4">Planned Start</th>
                      <th className="pb-2">Top Risk Factors</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(a => (
                      <tr key={a.lot_id_str} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-2 pr-4 font-mono text-xs text-blue-700">{a.lot_id_str}</td>
                        <td className="py-2 pr-4">
                          <Badge
                            label={a.risk_class}
                            variant={a.risk_class === 'high' ? 'red' : a.risk_class === 'medium' ? 'orange' : 'green'}
                          />
                        </td>
                        <td className="py-2 pr-4 w-40">
                          <ScoreBar score={a.risk_score} />
                        </td>
                        <td className="py-2 pr-4 text-gray-400 text-xs">
                          {a.planned_start_at ? new Date(a.planned_start_at).toLocaleDateString() : '—'}
                        </td>
                        <td className="py-2">
                          <div className="flex flex-wrap gap-1">
                            {Object.entries(a.top_features)
                              .sort(([, a], [, b]) => b - a)
                              .map(([feat, imp]) => (
                                <span key={feat} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                                  {feat.replace(/_/g, ' ')}: {(imp * 100).toFixed(0)}%
                                </span>
                              ))
                            }
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
