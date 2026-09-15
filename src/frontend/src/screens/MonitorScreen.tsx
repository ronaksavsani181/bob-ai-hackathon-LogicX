// screens/MonitorScreen.tsx — Screen 1: Fleet monitoring dashboard

import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { FleetYieldSummary, LotListResponse, ChamberRecurrenceResponse } from '../types/api';
import { KpiTile, Card, Badge, severityBadge, Spinner, ErrorMessage } from '../components/Shared';

export default function MonitorScreen() {
  const [fleet, setFleet] = useState<FleetYieldSummary | null>(null);
  const [lots, setLots] = useState<LotListResponse | null>(null);
  const [chambers, setChambers] = useState<ChamberRecurrenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.fleetSummary(),
      api.lots({ page: 1, page_size: 20 }),
      api.chamberRecurrence(),
    ])
      .then(([f, l, c]) => {
        setFleet(f);
        setLots(l);
        setChambers(c);
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;
  if (error) return <ErrorMessage msg={error} />;

  const excursionLots = lots?.lots.filter(l => l.excursion) ?? [];
  const recurrentChambers = chambers?.chambers.filter(c => c.is_recurrent) ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-gray-800">Fab Monitor — Fleet Overview</h1>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent excursion lots */}
        <Card title="Recent Yield Excursions">
          {excursionLots.length === 0 ? (
            <p className="text-sm text-gray-400">No excursions detected in loaded window.</p>
          ) : (
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
                    <td className="py-1.5 pr-3 font-mono text-xs">{lot.lot_id_str}</td>
                    <td className="py-1.5 pr-3 text-gray-600">{lot.product}</td>
                    <td className="py-1.5 pr-3 font-semibold text-red-600">
                      {lot.mean_yield != null ? `${(lot.mean_yield * 100).toFixed(1)}%` : '—'}
                    </td>
                    <td className="py-1.5">{severityBadge(lot.excursion_severity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {/* Chamber recurrence */}
        <Card title="Chamber Recurrence Analysis">
          {recurrentChambers.length === 0 ? (
            <p className="text-sm text-gray-400">No recurrent chambers detected.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b">
                  <th className="pb-2 pr-3">Chamber</th>
                  <th className="pb-2 pr-3">Tool</th>
                  <th className="pb-2 pr-3">Yield Gap</th>
                  <th className="pb-2">Score</th>
                </tr>
              </thead>
              <tbody>
                {recurrentChambers.map(c => (
                  <tr key={c.chamber_id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-1.5 pr-3 font-mono text-xs">{c.chamber_name}</td>
                    <td className="py-1.5 pr-3 text-gray-500">{c.tool_name}</td>
                    <td className="py-1.5 pr-3 text-red-600 font-semibold">
                      -{(c.yield_gap * 100).toFixed(1)}pp
                    </td>
                    <td className="py-1.5">
                      <span className="text-xs font-mono">{(c.recurrence_score * 100).toFixed(0)}%</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
                <th className="pb-2">Excursion</th>
              </tr>
            </thead>
            <tbody>
              {(lots?.lots ?? []).map(lot => (
                <tr key={lot.lot_id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-1.5 pr-3 font-mono text-xs text-blue-700">{lot.lot_id_str}</td>
                  <td className="py-1.5 pr-3">{lot.product}</td>
                  <td className="py-1.5 pr-3 text-gray-500">{lot.technology_node}</td>
                  <td className="py-1.5 pr-3">
                    <Badge label={lot.priority}
                      variant={lot.priority === 'high' ? 'red' : lot.priority === 'low' ? 'gray' : 'blue'} />
                  </td>
                  <td className="py-1.5 pr-3 text-gray-400 text-xs">
                    {lot.actual_start_at ? new Date(lot.actual_start_at).toLocaleDateString() : '—'}
                  </td>
                  <td className={`py-1.5 pr-3 font-semibold ${lot.excursion ? 'text-red-600' : 'text-green-600'}`}>
                    {lot.mean_yield != null ? `${(lot.mean_yield * 100).toFixed(1)}%` : '—'}
                  </td>
                  <td className="py-1.5">
                    {lot.excursion ? severityBadge(lot.excursion_severity) : <Badge label="OK" variant="green" />}
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
