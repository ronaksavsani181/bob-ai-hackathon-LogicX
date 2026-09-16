// screens/ActionsScreen.tsx — Screen 6: Engineer review & corrective actions
//
// HUMAN APPROVAL BOUNDARY:
//   All recommendations are advisory.  An engineer MUST explicitly approve or
//   reject each action here.  The system never auto-approves.
//   Reviews are recorded with engineer ID, timestamp, and notes.

import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { ActionRecommendation, ActionListResponse } from '../types/api';
import { Card, Badge, Spinner, ErrorMessage, DisclaimerBanner } from '../components/Shared';

type BadgeVariant = 'red' | 'orange' | 'blue' | 'green' | 'gray';

function priorityBadge(priority: string) {
  const map: Record<string, BadgeVariant> = {
    critical: 'red',
    high: 'orange',
    medium: 'blue',
    low: 'gray',
  };
  return <Badge label={priority} variant={map[priority] ?? 'gray'} />;
}

function statusBadge(status: string) {
  const map: Record<string, BadgeVariant> = {
    pending: 'orange',
    acknowledged: 'blue',
    approved: 'green',
    rejected: 'gray',
    completed: 'green',
  };
  return <Badge label={status} variant={map[status] ?? 'gray'} />;
}

function actionTypeBadge(actionType: string) {
  const map: Record<string, BadgeVariant> = {
    hold: 'red',
    expedite: 'orange',
    monitor: 'blue',
    're-inspect': 'orange',
    disposition: 'gray',
  };
  return <Badge label={actionType} variant={map[actionType] ?? 'gray'} />;
}

// ---------------------------------------------------------------------------
// Review modal
// ---------------------------------------------------------------------------

interface ReviewModalProps {
  action: ActionRecommendation;
  onClose: () => void;
  onSubmit: (actionId: number, decision: 'approved' | 'rejected', reviewer: string, notes: string) => Promise<void>;
}

function ReviewModal({ action, onClose, onSubmit }: ReviewModalProps) {
  const [decision, setDecision] = useState<'approved' | 'rejected'>('approved');
  const [reviewer, setReviewer] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!reviewer.trim()) { setErr('Reviewer ID is required.'); return; }
    setSubmitting(true);
    setErr(null);
    try {
      await onSubmit(action.action_id as number, decision, reviewer.trim(), notes.trim());
      onClose();
    } catch (e) {
      setErr(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">Engineer Review — Action #{action.action_id}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>
        <div className="px-6 py-4 space-y-4">
          {/* Recommendation summary */}
          <div className="bg-gray-50 rounded p-3 text-sm text-gray-700 border border-gray-200">
            <p className="font-medium text-xs text-gray-400 mb-1 uppercase tracking-wide">Recommendation</p>
            <p>{action.recommendation}</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Lot</p>
              <p className="font-mono font-semibold text-sm">{action.lot_id_str}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Priority</p>
              {priorityBadge(action.priority)}
            </div>
          </div>

          {/* Decision */}
          <div>
            <p className="text-xs text-gray-400 mb-1 uppercase tracking-wide">Decision *</p>
            <div className="flex gap-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  value="approved"
                  checked={decision === 'approved'}
                  onChange={() => setDecision('approved')}
                />
                <span className="text-sm text-green-700 font-medium">Approve</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  value="rejected"
                  checked={decision === 'rejected'}
                  onChange={() => setDecision('rejected')}
                />
                <span className="text-sm text-red-700 font-medium">Reject</span>
              </label>
            </div>
          </div>

          {/* Reviewer ID */}
          <div>
            <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wide">
              Reviewer ID / Badge *
            </label>
            <input
              type="text"
              value={reviewer}
              onChange={e => setReviewer(e.target.value)}
              placeholder="e.g. eng_chen"
              className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400"
            />
          </div>

          {/* Notes */}
          <div>
            <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wide">
              Notes / Rationale (optional)
            </label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={3}
              placeholder="Provide engineering rationale for the decision…"
              className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400 resize-none"
            />
          </div>

          {err && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{err}</p>
          )}

          <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs text-amber-700">
            ⚠ This review will be logged with your engineer ID and timestamp for audit purposes.
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className={`px-4 py-1.5 text-sm font-medium rounded transition-colors ${
              decision === 'approved'
                ? 'bg-green-600 text-white hover:bg-green-700 disabled:opacity-50'
                : 'bg-red-600 text-white hover:bg-red-700 disabled:opacity-50'
            }`}
          >
            {submitting ? 'Submitting…' : `Submit ${decision === 'approved' ? 'Approval' : 'Rejection'}`}
          </button>
        </div>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// ActionsScreen
// ---------------------------------------------------------------------------

export default function ActionsScreen() {
  const [data, setData] = useState<ActionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewTarget, setReviewTarget] = useState<ActionRecommendation | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadActions = useCallback(() => {
    setLoading(true);
    api.listActions()
      .then(setData)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadActions(); }, [loadActions]);

  const handleReviewSubmit = async (
    actionId: number,
    decision: 'approved' | 'rejected',
    reviewer: string,
    notes: string,
  ) => {
    const result = await api.submitReview({ action_id: actionId, decision, reviewer, notes });
    setSuccessMsg(`Action #${result.action_id} ${result.decision} by ${result.reviewer} — logged.`);
    loadActions(); // refresh
    setTimeout(() => setSuccessMsg(null), 5000);
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorMessage msg={error} />;

  const pending = data?.actions.filter(a => a.status === 'pending') ?? [];
  const reviewed = data?.actions.filter(a => a.status !== 'pending') ?? [];

  return (
    <>
      {reviewTarget && (
        <ReviewModal
          action={reviewTarget}
          onClose={() => setReviewTarget(null)}
          onSubmit={handleReviewSubmit}
        />
      )}

      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-800">Actions / Engineer Review</h1>
          <button
            onClick={loadActions}
            className="text-xs border border-gray-300 rounded px-3 py-1.5 text-gray-600 hover:bg-gray-50"
          >
            Refresh
          </button>
        </div>

        <DisclaimerBanner text="All recommendations are advisory. An engineer must explicitly approve or reject each action. No action is auto-approved." />

        {successMsg && (
          <div className="bg-green-50 border border-green-200 rounded px-4 py-2.5 text-sm text-green-700">
            ✓ {successMsg}
          </div>
        )}

        {/* Human approval boundary callout */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-800">
          <p className="font-semibold mb-0.5">Human Approval Boundary</p>
          <p className="text-xs text-blue-600">
            The analytics engine surfaces candidates. All final decisions require explicit sign-off
            by a qualified process or yield engineer. Reviews are persisted with engineer ID,
            timestamp, and rationale for full auditability.
          </p>
        </div>

        {/* Pending actions */}
        <Card title={`Pending Review (${pending.length})`}>
          {pending.length === 0 ? (
            <p className="text-sm text-gray-400">No actions awaiting review.</p>
          ) : (
            <div className="space-y-3">
              {pending.map(action => (
                <div
                  key={action.action_id}
                  className="border border-gray-200 rounded-lg p-4 bg-white hover:border-blue-300 transition-colors"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="font-mono text-xs text-blue-700 font-semibold">
                          {action.lot_id_str}
                        </span>
                        {actionTypeBadge(action.action_type)}
                        {priorityBadge(action.priority)}
                        {statusBadge(action.status)}
                      </div>
                      <p className="text-sm text-gray-700 leading-snug">{action.recommendation}</p>
                      <p className="text-xs text-gray-400 mt-1.5">
                        Evidence IDs: {action.evidence_ids.join(', ')}
                      </p>
                      <p className="text-xs text-gray-300 mt-0.5">
                        Created: {new Date(action.created_at).toLocaleString()}
                      </p>
                    </div>
                    <button
                      onClick={() => setReviewTarget(action)}
                      className="flex-shrink-0 bg-blue-600 text-white text-xs font-medium px-3 py-1.5 rounded hover:bg-blue-700 transition-colors"
                    >
                      Review
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Reviewed actions */}
        <Card title={`Reviewed / Acknowledged (${reviewed.length})`}>
          {reviewed.length === 0 ? (
            <p className="text-sm text-gray-400">No completed reviews.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400 border-b">
                    <th className="pb-2 pr-3">Lot</th>
                    <th className="pb-2 pr-3">Type</th>
                    <th className="pb-2 pr-3">Priority</th>
                    <th className="pb-2 pr-3">Status</th>
                    <th className="pb-2 pr-3">Reviewer</th>
                    <th className="pb-2">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {reviewed.map(action => (
                    <tr key={action.action_id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="py-1.5 pr-3 font-mono text-xs text-blue-700">{action.lot_id_str}</td>
                      <td className="py-1.5 pr-3">{actionTypeBadge(action.action_type)}</td>
                      <td className="py-1.5 pr-3">{priorityBadge(action.priority)}</td>
                      <td className="py-1.5 pr-3">{statusBadge(action.status)}</td>
                      <td className="py-1.5 pr-3 text-xs text-gray-600">{action.reviewed_by ?? '—'}</td>
                      <td className="py-1.5 text-xs text-gray-500 max-w-[200px] truncate">
                        {action.review_notes ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
