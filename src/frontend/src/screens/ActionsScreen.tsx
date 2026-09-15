// screens/ActionsScreen.tsx — Screen 6: Actions & Engineer Review

import React, { useState } from 'react';
import { Card, Badge, DisclaimerBanner } from '../components/Shared';

// ---------------------------------------------------------------------------
// Static demo actions — in a full implementation these would be persisted to
// the actions / action_reviews tables via FastAPI endpoints.
// ---------------------------------------------------------------------------
interface DemoAction {
  id: number;
  lot_id_str: string;
  recommendation: string;
  action_type: 'hold' | 're-inspect' | 'expedite' | 'monitor' | 'disposition';
  priority: 'critical' | 'high' | 'medium' | 'low';
  evidence_ids: string[];
  status: 'pending' | 'acknowledged' | 'approved' | 'rejected' | 'completed';
  created_at: string;
  reviewed_by: string | null;
  review_notes: string | null;
  root_cause_id: string;
}

const DEMO_ACTIONS: DemoAction[] = [
  {
    id: 1,
    lot_id_str: 'L0305',
    recommendation:
      'Hold lot L0305 pending review. Etch chamber ETH-02 shows +12% rate drift across 15 consecutive lots. ' +
      'Recommend chamber qualification run before releasing affected lots.',
    action_type: 'hold',
    priority: 'high',
    evidence_ids: ['EVD-A1B2C3D4', 'EVD-E5F6G7H8'],
    status: 'pending',
    created_at: new Date(Date.now() - 3 * 3600000).toISOString(),
    reviewed_by: null,
    review_notes: null,
    root_cause_id: 'etch_chamber_drift',
  },
  {
    id: 2,
    lot_id_str: 'L0408',
    recommendation:
      'Re-inspect wafers from lot L0408. Particle excursion detected on CVD-03 with center-heavy ' +
      'spatial pattern (60–80 defects/wafer). 10–20% yield penalty expected.',
    action_type: 're-inspect',
    priority: 'critical',
    evidence_ids: ['EVD-C9D8E7F6', 'EVD-A4B3C2D1'],
    status: 'acknowledged',
    created_at: new Date(Date.now() - 1 * 3600000).toISOString(),
    reviewed_by: 'eng_patel',
    review_notes: 'Confirmed particle event. Scheduling re-inspection.',
    root_cause_id: 'particle_contamination',
  },
  {
    id: 3,
    lot_id_str: 'L0215',
    recommendation:
      'Monitor lot L0215. Overlay excursion detected on LIT-01 (3.5× nominal σ). ' +
      'Yield within spec currently but metrology trend warrants close watch.',
    action_type: 'monitor',
    priority: 'medium',
    evidence_ids: ['EVD-M1N2O3P4'],
    status: 'pending',
    created_at: new Date(Date.now() - 6 * 3600000).toISOString(),
    reviewed_by: null,
    review_notes: null,
    root_cause_id: 'overlay_excursion',
  },
  {
    id: 4,
    lot_id_str: 'L0420',
    recommendation:
      'Post-maintenance yield shift on ETH-02. 15 lots after unscheduled PM show ' +
      '4–8% yield deficit. Monitor until recovery trend established.',
    action_type: 'monitor',
    priority: 'high',
    evidence_ids: ['EVD-PM1X2Y3Z4'],
    status: 'approved',
    created_at: new Date(Date.now() - 48 * 3600000).toISOString(),
    reviewed_by: 'eng_smith',
    review_notes: 'Approved for enhanced monitoring. Review after 10 more lots.',
    root_cause_id: 'post_maintenance_shift',
  },
];

const PRIORITY_COLORS: Record<string, 'red' | 'orange' | 'yellow' | 'green'> = {
  critical: 'red', high: 'orange', medium: 'yellow', low: 'green',
};
const STATUS_COLORS: Record<string, 'red' | 'orange' | 'blue' | 'green' | 'gray'> = {
  pending: 'orange', acknowledged: 'blue', approved: 'green', rejected: 'red', completed: 'gray',
};

export default function ActionsScreen() {
  const [actions, setActions] = useState<DemoAction[]>(DEMO_ACTIONS);
  const [selectedAction, setSelectedAction] = useState<DemoAction | null>(null);
  const [reviewer, setReviewer] = useState('');
  const [notes, setNotes] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const filteredActions = filterStatus === 'all'
    ? actions
    : actions.filter(a => a.status === filterStatus);

  const handleReview = (decision: 'approved' | 'rejected') => {
    if (!selectedAction || !reviewer.trim()) return;
    setActions(prev => prev.map(a =>
      a.id === selectedAction.id
        ? { ...a, status: decision, reviewed_by: reviewer, review_notes: notes }
        : a
    ));
    setSelectedAction(null);
    setReviewer('');
    setNotes('');
  };

  const pendingCount = actions.filter(a => a.status === 'pending').length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800">Actions & Engineer Review</h1>
        {pendingCount > 0 && (
          <span className="bg-orange-100 text-orange-700 text-sm font-semibold px-3 py-1 rounded-full border border-orange-200">
            {pendingCount} pending review
          </span>
        )}
      </div>

      <DisclaimerBanner
        text="Engineering review is REQUIRED before any action is taken. Root-cause candidates are evidence-ranked, not confirmed causes. The engineer has full authority to override, approve, or reject any recommendation."
      />

      {/* Status filter */}
      <div className="flex gap-2">
        {['all', 'pending', 'acknowledged', 'approved', 'rejected'].map(s => (
          <button
            key={s}
            onClick={() => setFilterStatus(s)}
            className={`px-3 py-1 rounded text-sm capitalize ${
              filterStatus === s
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="flex gap-4">
        {/* Actions list */}
        <div className="flex-1 space-y-3">
          {filteredActions.length === 0 && (
            <p className="text-sm text-gray-400 p-4">No actions in this status.</p>
          )}
          {filteredActions.map(action => (
            <div
              key={action.id}
              className={`rounded-lg border p-4 cursor-pointer transition-all ${
                selectedAction?.id === action.id
                  ? 'border-blue-400 bg-blue-50 shadow-sm'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              }`}
              onClick={() => setSelectedAction(action)}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <code className="text-xs font-mono text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded">
                    {action.lot_id_str}
                  </code>
                  <Badge label={action.action_type.replace('-', ' ')} variant="gray" />
                  <Badge label={action.priority} variant={PRIORITY_COLORS[action.priority]} />
                </div>
                <Badge label={action.status} variant={STATUS_COLORS[action.status] ?? 'gray'} />
              </div>
              <p className="text-sm text-gray-700 leading-relaxed">{action.recommendation}</p>
              <div className="mt-2 flex items-center gap-3 text-xs text-gray-400">
                <span>Root cause: <span className="text-gray-600">{action.root_cause_id.replace(/_/g, ' ')}</span></span>
                <span>·</span>
                <span>{new Date(action.created_at).toLocaleString()}</span>
                {action.reviewed_by && (
                  <>
                    <span>·</span>
                    <span>Reviewed by: <span className="text-gray-600">{action.reviewed_by}</span></span>
                  </>
                )}
              </div>
              {action.review_notes && (
                <p className="mt-1.5 text-xs text-gray-500 bg-gray-50 rounded px-2 py-1.5 border border-gray-100">
                  Note: {action.review_notes}
                </p>
              )}
            </div>
          ))}
        </div>

        {/* Review panel */}
        {selectedAction && selectedAction.status === 'pending' && (
          <div className="w-80 flex-shrink-0">
            <Card title="Engineer Review">
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-gray-400 mb-1">Lot</p>
                  <code className="font-mono text-sm text-blue-700">{selectedAction.lot_id_str}</code>
                </div>
                <div>
                  <p className="text-xs text-gray-400 mb-1">Evidence IDs</p>
                  <div className="flex flex-wrap gap-1">
                    {selectedAction.evidence_ids.map(eid => (
                      <code key={eid} className="text-xs bg-gray-100 px-1.5 py-0.5 rounded font-mono text-gray-600">
                        {eid}
                      </code>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-1">Reviewer Name *</label>
                  <input
                    type="text"
                    value={reviewer}
                    onChange={e => setReviewer(e.target.value)}
                    placeholder="e.g. eng_jones"
                    className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-blue-400"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-1">Review Notes</label>
                  <textarea
                    value={notes}
                    onChange={e => setNotes(e.target.value)}
                    placeholder="Optional notes…"
                    rows={3}
                    className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-blue-400 resize-none"
                  />
                </div>
                <div className="flex gap-2 pt-1">
                  <button
                    disabled={!reviewer.trim()}
                    onClick={() => handleReview('approved')}
                    className="flex-1 py-2 bg-green-600 text-white rounded text-sm font-semibold hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    ✓ Approve
                  </button>
                  <button
                    disabled={!reviewer.trim()}
                    onClick={() => handleReview('rejected')}
                    className="flex-1 py-2 bg-red-600 text-white rounded text-sm font-semibold hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    ✗ Reject
                  </button>
                </div>
                <p className="text-xs text-gray-400 text-center">
                  Engineer name required before review decision.
                </p>
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
