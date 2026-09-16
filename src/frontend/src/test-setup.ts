// Vitest / @testing-library setup
import '@testing-library/jest-dom'

// Recharts uses ResizeObserver internally via ResponsiveContainer.
// jsdom does not implement it, so provide a minimal stub.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Cast to unknown then to Window to avoid TS strict type mismatch
(window as unknown as Record<string, unknown>)['ResizeObserver'] = ResizeObserverStub;
