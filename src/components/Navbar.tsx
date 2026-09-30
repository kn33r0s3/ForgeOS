import React from 'react';
import { Activity } from 'lucide-react';
import type { ApiHealth, Cycle } from '../types';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  health: ApiHealth | null;
  latestCycle: Cycle | null;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  health,
  latestCycle,
}) => {
  const tabs = [
    { id: 'overview', label: 'Command Center' },
    { id: 'signals', label: 'Signals & Demand' },
    { id: 'opportunities', label: 'Opportunities' },
    { id: 'beliefs', label: 'Hypotheses' },
    { id: 'decisions', label: 'Decisions & Executions' },
    { id: 'workers', label: 'Workers & Cycles' },
    { id: 'api', label: 'API Explorer' },
  ];
  const backendReady = health?.status === 'ok' && health.database.available;

  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center font-bold text-white shadow-lg shadow-orange-500/20">
              H
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg text-slate-100 tracking-tight">Hami</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono border border-slate-700">
                  ForgeOS
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">Universal Economic Intelligence &amp; Action System</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-2 text-xs text-slate-300 bg-slate-800/80 px-3 py-1.5 rounded-md border border-slate-700">
              <Activity className={`w-3.5 h-3.5 ${backendReady ? 'text-emerald-400' : 'text-rose-400'}`} />
              <span className={`font-mono ${backendReady ? 'text-emerald-400' : 'text-rose-400'}`}>
                {health ? (backendReady ? 'API connected' : 'API not ready') : 'API loading'}
              </span>
              <span className="text-slate-600">|</span>
              <span className="text-slate-400">Cycle:</span>
              <span className="font-mono text-amber-400">
                {latestCycle ? `#${latestCycle.id}` : 'Not recorded'}
              </span>
            </div>
          </div>
        </div>

        <nav className="flex space-x-1 overflow-x-auto pb-2 scrollbar-none">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? 'bg-slate-800 text-amber-400 border border-slate-700 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>
    </header>
  );
};
