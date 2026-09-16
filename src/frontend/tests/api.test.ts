// tests/api.test.ts — Unit tests for the typed API client
//
// Tests verify that api.* methods build the correct URLs and handle errors.
// Uses vitest with vi.fn() mocks — does NOT hit any real network.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ---------------------------------------------------------------------------
// Mock global fetch before importing the module under test
// ---------------------------------------------------------------------------
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

// Re-import after stubbing (vite/vitest resolves ESM statically so we use
// a dynamic import inside each test where needed)
const BASE = '';

function mockOk(body: unknown): Response {
  return {
    ok: true,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
    status: 200,
    statusText: 'OK',
  } as unknown as Response;
}

function mockError(status: number, text: string): Response {
  return {
    ok: false,
    json: () => Promise.resolve({}),
    text: () => Promise.resolve(text),
    status,
    statusText: 'Error',
  } as unknown as Response;
}

describe('API client URL construction', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('fleetSummary calls correct URL', async () => {
    mockFetch.mockResolvedValueOnce(mockOk({ fleet_mean_yield: 0.93 }));
    const { api } = await import('../src/api/client');
    await api.fleetSummary();
    expect(mockFetch).toHaveBeenCalledWith(
      `${BASE}/api/monitor/fleet-summary`,
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it('yieldTrend builds URL with last_n param', async () => {
    mockFetch.mockResolvedValueOnce(mockOk({ points: [], fleet_mean: 0.93, excursion_threshold: 0.85 }));
    const { api } = await import('../src/api/client');
    await api.yieldTrend(80);
    const calledUrl = (mockFetch.mock.calls[0] as [string, ...unknown[]])[0];
    expect(calledUrl).toContain('/api/monitor/yield-trend');
    expect(calledUrl).toContain('last_n=80');
  });

  it('lots builds URL with pagination params', async () => {
    mockFetch.mockResolvedValueOnce(mockOk({ lots: [], meta: { total: 0, page: 1, page_size: 10, pages: 1 } }));
    const { api } = await import('../src/api/client');
    await api.lots({ page: 2, page_size: 25, excursion_only: true });
    const calledUrl = (mockFetch.mock.calls[0] as [string, ...unknown[]])[0];
    expect(calledUrl).toContain('page=2');
    expect(calledUrl).toContain('page_size=25');
    expect(calledUrl).toContain('excursion_only=true');
  });

  it('lotDetail builds URL with lot_id_str', async () => {
    mockFetch.mockResolvedValueOnce(mockOk({ lot_id_str: 'L0042' }));
    const { api } = await import('../src/api/client');
    await api.lotDetail('L0042');
    const calledUrl = (mockFetch.mock.calls[0] as [string, ...unknown[]])[0];
    expect(calledUrl).toBe(`${BASE}/api/lots/L0042`);
  });

  it('lotPatterns appends sample_wafers', async () => {
    mockFetch.mockResolvedValueOnce(mockOk({ lot_id_str: 'L0042', patterns: [] }));
    const { api } = await import('../src/api/client');
    await api.lotPatterns('L0042', 7);
    const calledUrl = (mockFetch.mock.calls[0] as [string, ...unknown[]])[0];
    expect(calledUrl).toContain('sample_wafers=7');
  });

  it('lotRootCause builds root-cause URL', async () => {
    mockFetch.mockResolvedValueOnce(mockOk({ candidates: [] }));
    const { api } = await import('../src/api/client');
    await api.lotRootCause('L0042');
    const calledUrl = (mockFetch.mock.calls[0] as [string, ...unknown[]])[0];
    expect(calledUrl).toBe(`${BASE}/api/lots/L0042/root-cause`);
  });

  it('preRunRisk builds URL with top_n', async () => {
    mockFetch.mockResolvedValueOnce(mockOk({ assessments: [], model_version: 'v1' }));
    const { api } = await import('../src/api/client');
    await api.preRunRisk(30);
    const calledUrl = (mockFetch.mock.calls[0] as [string, ...unknown[]])[0];
    expect(calledUrl).toContain('top_n=30');
  });

  it('listActions builds URL without status filter', async () => {
    mockFetch.mockResolvedValueOnce(mockOk({ actions: [], total: 0 }));
    const { api } = await import('../src/api/client');
    await api.listActions();
    const calledUrl = (mockFetch.mock.calls[0] as [string, ...unknown[]])[0];
    expect(calledUrl).toBe(`${BASE}/api/actions`);
  });

  it('listActions builds URL with status filter', async () => {
    mockFetch.mockResolvedValueOnce(mockOk({ actions: [], total: 0 }));
    const { api } = await import('../src/api/client');
    await api.listActions('pending');
    const calledUrl = (mockFetch.mock.calls[0] as [string, ...unknown[]])[0];
    expect(calledUrl).toContain('status=pending');
  });

  it('submitReview POSTs to /api/actions/review', async () => {
    const reviewResponse = {
      action_id: 1,
      decision: 'approved',
      reviewer: 'eng_test',
      reviewed_at: new Date().toISOString(),
      message: 'approved',
    };
    mockFetch.mockResolvedValueOnce(mockOk(reviewResponse));
    const { api } = await import('../src/api/client');
    const result = await api.submitReview({
      action_id: 1,
      decision: 'approved',
      reviewer: 'eng_test',
    });
    const [calledUrl, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(calledUrl).toBe(`${BASE}/api/actions/review`);
    expect(opts.method).toBe('POST');
    expect(result.decision).toBe('approved');
  });

  it('throws on non-OK response', async () => {
    mockFetch.mockResolvedValueOnce(mockError(404, 'Not found'));
    const { api } = await import('../src/api/client');
    await expect(api.lotDetail('INVALID')).rejects.toThrow('404');
  });

  it('chamberRecurrence calls correct URL', async () => {
    mockFetch.mockResolvedValueOnce(mockOk({ chambers: [] }));
    const { api } = await import('../src/api/client');
    await api.chamberRecurrence();
    const calledUrl = (mockFetch.mock.calls[0] as [string, ...unknown[]])[0];
    expect(calledUrl).toBe(`${BASE}/api/monitor/chambers`);
  });

  it('lotEvidence builds evidence URL', async () => {
    mockFetch.mockResolvedValueOnce(mockOk({ lot_id_str: 'L0010', items: [], total: 0 }));
    const { api } = await import('../src/api/client');
    await api.lotEvidence('L0010');
    const calledUrl = (mockFetch.mock.calls[0] as [string, ...unknown[]])[0];
    expect(calledUrl).toBe(`${BASE}/api/lots/L0010/evidence`);
  });
});
