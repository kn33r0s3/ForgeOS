import React, { useCallback, useEffect, useState } from 'react';
import { Navbar } from './components/Navbar';
import { OverviewTab } from './components/OverviewTab';
import { SignalsTab } from './components/SignalsTab';
import { OpportunitiesTab } from './components/OpportunitiesTab';
import { BeliefsTab } from './components/BeliefsTab';
import { DecisionsTab } from './components/DecisionsTab';
import { WorkersTab } from './components/WorkersTab';
import { ApiExplorerTab } from './components/ApiExplorerTab';
import { loadForgeDashboard, recordObservation } from './lib/forgeApi';
import type { ForgeDashboardData } from './types';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [dashboard, setDashboard] = useState<ForgeDashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notification, setNotification] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      setDashboard(await loadForgeDashboard());
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Unable to load canonical ForgeOS data');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleAddSignal = async (observation: { content: string; source: string }) => {
    const created = await recordObservation(observation.content, observation.source);
    setDashboard((current) => current
      ? { ...current, signals: [created, ...current.signals] }
      : current);
    setNotification('Observation recorded by the canonical signal service');
    window.setTimeout(() => setNotification(null), 3000);
  };

  const latestCycle = dashboard?.cycles[0] ?? null;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        health={dashboard?.health ?? null}
        latestCycle={latestCycle}
      />

      {notification && (
        <div role="status" className="fixed bottom-5 right-5 z-50 bg-slate-800 border border-emerald-500/40 text-emerald-300 text-xs px-4 py-2.5 rounded-lg shadow-xl animate-fade-in">
          {notification}
        </div>
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {loadError && (
          <div role="alert" className="mb-5 rounded-lg border border-rose-800 bg-rose-950/50 px-4 py-3 text-xs text-rose-200">
            <strong className="font-semibold">Canonical data unavailable:</strong> {loadError}
            {dashboard && <span className="block mt-1 text-rose-300/80">The last successfully loaded data remains visible.</span>}
          </div>
        )}

        {!dashboard && isLoading && (
          <div role="status" className="rounded-xl border border-slate-800 bg-slate-900 p-8 text-center text-sm text-slate-400">
            Loading live ForgeOS data…
          </div>
        )}

        {!dashboard && !isLoading && loadError && (
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-8 text-center text-sm text-slate-400">
            No dashboard data is shown until the canonical backend responds successfully.
          </div>
        )}

        {dashboard && activeTab === 'overview' && (
          <OverviewTab
            stats={dashboard.stats}
            observerStats={dashboard.observerStats}
            latestCycle={latestCycle}
            recentSignals={dashboard.recentSignals}
            opportunities={dashboard.opportunities}
            beliefs={dashboard.beliefs}
            setActiveTab={setActiveTab}
          />
        )}

        {dashboard && activeTab === 'signals' && (
          <SignalsTab
            signals={dashboard.signals}
            totalSignals={dashboard.stats.total_signals}
            onAddSignal={handleAddSignal}
          />
        )}

        {dashboard && activeTab === 'opportunities' && (
          <OpportunitiesTab opportunities={dashboard.opportunities} />
        )}

        {dashboard && activeTab === 'beliefs' && (
          <BeliefsTab beliefs={dashboard.beliefs} />
        )}

        {dashboard && activeTab === 'decisions' && (
          <DecisionsTab
            decisions={dashboard.decisions}
            actions={dashboard.actions}
            outcomes={dashboard.outcomes}
          />
        )}

        {dashboard && activeTab === 'workers' && (
          <WorkersTab workers={dashboard.workers} cycles={dashboard.cycles} />
        )}

        {activeTab === 'api' && <ApiExplorerTab />}
      </main>

      <footer className="border-t border-slate-800/80 py-4 bg-slate-950 text-slate-500 text-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>
            <span>ForgeOS / Hami</span>
            <span className="mx-2">•</span>
            <span>Canonical backend projection</span>
          </div>
          <div className="text-[11px] font-mono text-slate-600">
            REAL, TEST, MOCK, and HYPOTHESIS records remain distinct
          </div>
        </div>
      </footer>
    </div>
  );
}
