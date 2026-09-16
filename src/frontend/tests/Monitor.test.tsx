// tests/Monitor.test.tsx — Component tests for the Monitor page
//
// Tests verify rendering logic, KPI display, and error states.
// Uses vitest + @testing-library/react.  API calls are mocked.

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

// ---------------------------------------------------------------------------
// Mock the api module
// ---------------------------------------------------------------------------
vi.mock('../src/api/client', () => ({
  api: {
    fleetSummary: vi.fn(),
    lots: vi.fn(),
    chamberRecurrence: vi.fn(),
    yieldTrend: vi.fn(),
  },
}));

import { api } from '../src/api/client';
import MonitorPage from '../src/pages/Monitor';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const FLEET_FIXTURE = {
  fleet_mean_yield: 0.934,
  fleet_std_yield: 0.028,
  excursion_count_7d: 2,
  excursion_count_30d: 7,
  high_risk_lots_pending: 3,
  generated_at: new Date().toISOString(),
};

const LOTS_FIXTURE = {
  lots: [
    {
      lot_id: 1,
      lot_id_str: 'L0001',
      product: 'P-28nm-A',
      technology_node: '28nm',
      priority: 'normal',
      status: 'completed',
      actual_start_at: '2024-01-10T08:00:00Z',
      mean_yield: 0.95,
      excursion: false,
      excursion_severity: 'none',
      risk_score: null,
      risk_class: null,
    },
    {
      lot_id: 2,
      lot_id_str: 'L0002',
      product: 'P-28nm-B',
      technology_node: '28nm',
      priority: 'high',
      status: 'completed',
      actual_start_at: '2024-01-11T08:00:00Z',
      mean_yield: 0.72,
      excursion: true,
      excursion_severity: 'severe',
      risk_score: 0.85,
      risk_class: 'high',
    },
  ],
  meta: { total: 2, page: 1, page_size: 50, pages: 1 },
};

const EXCURSION_LOTS_FIXTURE = {
  lots: [
    {
      lot_id: 2,
      lot_id_str: 'L0002',
      product: 'P-28nm-B',
      technology_node: '28nm',
      priority: 'high',
      status: 'completed',
      actual_start_at: '2024-01-11T08:00:00Z',
      mean_yield: 0.72,
      excursion: true,
      excursion_severity: 'severe',
      risk_score: 0.85,
      risk_class: 'high',
    },
  ],
  meta: { total: 1, page: 1, page_size: 50, pages: 1 },
};

const INFLIGHT_FIXTURE = {
  lots: [],
  meta: { total: 0, page: 1, page_size: 20, pages: 1 },
};

const CHAMBERS_FIXTURE = {
  chambers: [
    {
      chamber_id: 1,
      chamber_name: 'CHA-1',
      tool_name: 'ETCH-A',
      affected_lot_count: 8,
      chamber_mean_yield: 0.88,
      fleet_mean_yield: 0.934,
      yield_gap: 0.054,
      recurrence_score: 0.81,
      is_recurrent: true,
      algorithm_version: 'recurrence_v1',
    },
  ],
  generated_at: new Date().toISOString(),
};

const TREND_FIXTURE = {
  points: [
    { lot_id_str: 'L0001', actual_start_at: '2024-01-10T08:00:00Z', mean_yield: 0.95, is_excursion: false, scenario_hint: null },
    { lot_id_str: 'L0002', actual_start_at: '2024-01-11T08:00:00Z', mean_yield: 0.72, is_excursion: true, scenario_hint: null },
  ],
  fleet_mean: 0.934,
  excursion_threshold: 0.86,
  generated_at: new Date().toISOString(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Monitor page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.fleetSummary as ReturnType<typeof vi.fn>).mockResolvedValue(FLEET_FIXTURE);
    // lots is called twice: once for excursion_only=true, once for status=in_progress
    (api.lots as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce(EXCURSION_LOTS_FIXTURE)
      .mockResolvedValueOnce(INFLIGHT_FIXTURE);
    (api.chamberRecurrence as ReturnType<typeof vi.fn>).mockResolvedValue(CHAMBERS_FIXTURE);
    (api.yieldTrend as ReturnType<typeof vi.fn>).mockResolvedValue(TREND_FIXTURE);
  });

  it('renders heading', async () => {
    render(<MonitorPage />);
    await waitFor(() => {
      expect(screen.getByText(/Fab Monitor/i)).toBeTruthy();
    });
  });

  it('shows fleet mean yield KPI (Avg Yield 7d)', async () => {
    render(<MonitorPage />);
    await waitFor(() => {
      // Multiple elements may show 93.40% — use getAllByText
      const elements = screen.getAllByText(/93\.40%/);
      expect(elements.length).toBeGreaterThan(0);
    });
  });

  it('shows excursion count KPI tile label', async () => {
    render(<MonitorPage />);
    await waitFor(() => {
      expect(screen.getByText('Open Excursions (7d)')).toBeTruthy();
      // The value "2" should be present in the KPI tile
      const elements = screen.getAllByText('2');
      expect(elements.length).toBeGreaterThan(0);
    });
  });

  it('shows recurrent chamber in chamber table', async () => {
    render(<MonitorPage />);
    await waitFor(() => {
      expect(screen.getByText('CHA-1')).toBeTruthy();
      expect(screen.getByText('ETCH-A')).toBeTruthy();
    });
  });

  it('shows excursion lot in excursion table', async () => {
    render(<MonitorPage />);
    await waitFor(() => {
      // L0002 is the excursion lot — appears in excursion table
      const matches = screen.getAllByText('L0002');
      expect(matches.length).toBeGreaterThan(0);
    });
  });

  it('shows auto-refresh notice', async () => {
    render(<MonitorPage />);
    await waitFor(() => {
      expect(screen.getByText(/Auto-refreshes/i)).toBeTruthy();
    });
  });

  it('renders fleet std in KPI sub-label', async () => {
    render(<MonitorPage />);
    await waitFor(() => {
      expect(screen.getByText(/σ = 2\.80%/i)).toBeTruthy();
    });
  });

  it('shows "High-Risk Pending" KPI', async () => {
    render(<MonitorPage />);
    await waitFor(() => {
      expect(screen.getByText(/High-Risk Pending/i)).toBeTruthy();
    });
  });

  it('shows error message on API failure', async () => {
    (api.fleetSummary as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));
    render(<MonitorPage />);
    await waitFor(() => {
      const errorDivs = document.querySelectorAll('.bg-red-50');
      expect(errorDivs.length).toBeGreaterThan(0);
    });
  });
});
