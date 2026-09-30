import React from 'react';
import { Activity, Cpu, Database, Play, ShieldAlert, Sparkles } from 'lucide-react';
import { SystemStats } from '../types';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  stats: SystemStats | null;
  onTriggerCycle: () => void;
  isCycling: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  stats,
  onTriggerCycle,
  isCycling,
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
                  ForgeOS Substrate v2.4
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">Universal Economic Intelligence &amp; Action System</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-2 text-xs text-slate-300 bg-slate-800/80 px-3 py-1.5 rounded-md border border-slate-700">
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="font-mono text-emerald-400">WAL Active</span>
              <span className="text-slate-600">|</span>
              <span className="text-slate-400">Cycle:</span>
              <span className="font-mono text-amber-400">#{stats?.latest_cycle_id || 308}</span>
            </div>

            <button
              onClick={onTriggerCycle}
              disabled={isCycling}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-semibold shadow-sm transition-all ${
                isCycling
                  ? 'bg-amber-600/50 text-amber-200 cursor-wait'
                  : 'bg-gradient-to-r from-amber-500 to-orange-600 text-white hover:from-amber-400 hover:to-orange-500 active:scale-95'
              }`}
            >
              <Play className={`w-3.5 h-3.5 ${isCycling ? 'animate-spin' : ''}`} />
              {isCycling ? 'Running Cycle...' : 'Run Cycle'}
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
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
