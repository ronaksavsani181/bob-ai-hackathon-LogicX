// App.tsx — Main application shell with tab navigation
// 
// S1 — Wafer Yield Root Cause & Defect Pattern Analyser
// Team LogicX
//
// This is a semiconductor manufacturing analytics dashboard, NOT a chatbot.
// All root-cause ranking is deterministic evidence fusion.

import React, { useState, Suspense } from 'react';
import { Spinner } from './components/Shared';

const MonitorScreen     = React.lazy(() => import('./pages/Monitor'));
const InvestigateScreen = React.lazy(() => import('./pages/Investigate'));
const WaferPatternScreen= React.lazy(() => import('./screens/WaferPatternScreen'));
const PreRunScreen      = React.lazy(() => import('./screens/PreRunScreen'));
const EvidenceScreen    = React.lazy(() => import('./screens/EvidenceScreen'));
const ActionsScreen     = React.lazy(() => import('./screens/ActionsScreen'));

type TabId = 'monitor' | 'investigate' | 'wafer-pattern' | 'pre-run' | 'evidence' | 'actions';

interface Tab {
  id: TabId;
  label: string;
  icon: string;
  description: string;
}

const TABS: Tab[] = [
  { id: 'monitor',       label: 'Monitor',         icon: '📊', description: 'Fleet yield overview & chamber recurrence' },
  { id: 'investigate',   label: 'Investigate',     icon: '🔍', description: 'Lot detail, yield excursion & parameter anomalies' },
  { id: 'wafer-pattern', label: 'Wafer Pattern Lab',icon: '🔬', description: 'Defect spatial pattern classification' },
  { id: 'pre-run',       label: 'Pre-Run Risk',    icon: '⚡', description: 'Pre-run risk model for upcoming lots' },
  { id: 'evidence',      label: 'Evidence',        icon: '📋', description: 'Evidence-based root-cause ranking' },
  { id: 'actions',       label: 'Actions / Review',icon: '✅', description: 'Engineer review & corrective actions' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('monitor');

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="max-w-screen-2xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="font-bold text-gray-800 text-base leading-tight">
              Wafer Yield Root Cause &amp; Defect Pattern Analyser
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">
              Team LogicX · Challenge S1 · Semiconductor Manufacturing Analytics
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs bg-green-100 text-green-700 border border-green-200 px-2 py-0.5 rounded">
              ● Live
            </span>
            <span className="text-xs text-gray-400 font-mono">v0.1.0</span>
          </div>
        </div>
      </header>

      {/* Tab navigation */}
      <nav className="bg-white border-b border-gray-200 px-6">
        <div className="max-w-screen-2xl mx-auto flex gap-0">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              title={tab.description}
              className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-700'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <span className="text-base">{tab.icon}</span>
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          ))}
        </div>
      </nav>

      {/* Screen content */}
      <main className="max-w-screen-2xl mx-auto px-6 py-6">
        <Suspense fallback={<Spinner />}>
          {activeTab === 'monitor'        && <MonitorScreen />}
          {activeTab === 'investigate'    && <InvestigateScreen />}
          {activeTab === 'wafer-pattern'  && <WaferPatternScreen />}
          {activeTab === 'pre-run'        && <PreRunScreen />}
          {activeTab === 'evidence'       && <EvidenceScreen />}
          {activeTab === 'actions'        && <ActionsScreen />}
        </Suspense>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white mt-auto px-6 py-3">
        <div className="max-w-screen-2xl mx-auto flex items-center justify-between text-xs text-gray-400">
          <span>
            Synthetic demonstration data only — does not represent any real fabrication facility.
          </span>
          <span>
            All root-cause ranking is deterministic evidence fusion — no LLM inference.
          </span>
        </div>
      </footer>
    </div>
  );
}
