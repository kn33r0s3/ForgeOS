import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { OverviewTab } from './components/OverviewTab';
import { SignalsTab } from './components/SignalsTab';
import { OpportunitiesTab } from './components/OpportunitiesTab';
import { BeliefsTab } from './components/BeliefsTab';
import { DecisionsTab } from './components/DecisionsTab';
import { WorkersTab } from './components/WorkersTab';
import { ApiExplorerTab } from './components/ApiExplorerTab';
import { 
  Signal, 
  Opportunity, 
  Belief, 
  Decision, 
  Execution, 
  WorkerTask, 
  SystemStats 
} from './types';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [beliefs, setBeliefs] = useState<Belief[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [workers, setWorkers] = useState<WorkerTask[]>([]);
  const [isCycling, setIsCycling] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);

  const showNotification = (msg: string) => {
    setNotification(msg);
    setTimeout(() => setNotification(null), 3000);
  };

  const fetchData = async () => {
    try {
      const [
        statsRes,
        signalsRes,
        oppsRes,
        beliefsRes,
        decisionsRes,
        executionsRes,
        workersRes,
      ] = await Promise.all([
        fetch('/api/stats').then(r => r.json()),
        fetch('/api/signals').then(r => r.json()),
        fetch('/api/opportunities').then(r => r.json()),
        fetch('/api/beliefs').then(r => r.json()),
        fetch('/api/decisions').then(r => r.json()),
        fetch('/api/executions').then(r => r.json()),
        fetch('/api/workers').then(r => r.json()),
      ]);

      setStats(statsRes);
      setSignals(signalsRes);
      setOpportunities(oppsRes);
      setBeliefs(beliefsRes);
      setDecisions(decisionsRes);
      setExecutions(executionsRes);
      setWorkers(workersRes);
    } catch (err) {
      console.error('Error fetching data:', err);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleTriggerCycle = async () => {
    setIsCycling(true);
    try {
      const res = await fetch('/api/workers/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          worker_type: 'intelligence_cycle',
          task_name: 'autonomous_evidence_pass',
        }),
      });
      const data = await res.json();
      showNotification(`Cycle #${data.task?.cycle_id || 'new'} completed cleanly!`);
      await fetchData();
    } catch (err) {
      showNotification('Cycle failed to trigger');
    } finally {
      setIsCycling(false);
    }
  };

  const handleAddSignal = async (signalData: Partial<Signal>) => {
    try {
      const res = await fetch('/api/signals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(signalData),
      });
      const created = await res.json();
      setSignals([created, ...signals]);
      showNotification('New signal ingested successfully');
      fetchData();
    } catch (err) {
      showNotification('Failed to add signal');
    }
  };

  const handleAddOpportunity = async (oppData: Partial<Opportunity>) => {
    try {
      const res = await fetch('/api/opportunities', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(oppData),
      });
      const created = await res.json();
      setOpportunities([created, ...opportunities]);
      showNotification('Opportunity formulated successfully');
      fetchData();
    } catch (err) {
      showNotification('Failed to create opportunity');
    }
  };

  const handleUpdateOpportunity = async (id: number, data: Partial<Opportunity>) => {
    try {
      const res = await fetch(`/api/opportunities/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const updated = await res.json();
      setOpportunities(opportunities.map(o => o.id === id ? updated : o));
      showNotification('Opportunity record updated');
      fetchData();
    } catch (err) {
      showNotification('Failed to update opportunity');
    }
  };

  const handleAddBelief = async (beliefData: Partial<Belief>) => {
    try {
      const res = await fetch('/api/beliefs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(beliefData),
      });
      const created = await res.json();
      setBeliefs([created, ...beliefs]);
      showNotification('Belief hypothesis recorded');
      fetchData();
    } catch (err) {
      showNotification('Failed to add belief');
    }
  };

  const handleAddDecision = async (decData: Partial<Decision>) => {
    try {
      const res = await fetch('/api/decisions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(decData),
      });
      const created = await res.json();
      setDecisions([created, ...decisions]);
      showNotification('Decision proposed successfully');
      fetchData();
    } catch (err) {
      showNotification('Failed to add decision');
    }
  };

  const handleAddExecution = async (execData: Partial<Execution>) => {
    try {
      const res = await fetch('/api/executions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(execData),
      });
      const created = await res.json();
      setExecutions([created, ...executions]);
      showNotification('Execution outcome logged');
      fetchData();
    } catch (err) {
      showNotification('Failed to log execution');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        stats={stats}
        onTriggerCycle={handleTriggerCycle}
        isCycling={isCycling}
      />

      {/* Notification Toast */}
      {notification && (
        <div className="fixed bottom-5 right-5 z-50 bg-slate-800 border border-amber-500/40 text-amber-300 text-xs px-4 py-2.5 rounded-lg shadow-xl animate-fade-in flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-amber-400"></span>
          {notification}
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'overview' && (
          <OverviewTab
            stats={stats}
            signals={signals}
            opportunities={opportunities}
            beliefs={beliefs}
            decisions={decisions}
            setActiveTab={setActiveTab}
            onTriggerCycle={handleTriggerCycle}
            isCycling={isCycling}
          />
        )}

        {activeTab === 'signals' && (
          <SignalsTab
            signals={signals}
            onAddSignal={handleAddSignal}
          />
        )}

        {activeTab === 'opportunities' && (
          <OpportunitiesTab
            opportunities={opportunities}
            onUpdateOpportunity={handleUpdateOpportunity}
            onAddOpportunity={handleAddOpportunity}
          />
        )}

        {activeTab === 'beliefs' && (
          <BeliefsTab
            beliefs={beliefs}
            onAddBelief={handleAddBelief}
          />
        )}

        {activeTab === 'decisions' && (
          <DecisionsTab
            decisions={decisions}
            executions={executions}
            onAddDecision={handleAddDecision}
            onAddExecution={handleAddExecution}
          />
        )}

        {activeTab === 'workers' && (
          <WorkersTab
            workers={workers}
            stats={stats}
            onTriggerCycle={handleTriggerCycle}
            isCycling={isCycling}
          />
        )}

        {activeTab === 'api' && <ApiExplorerTab />}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-4 bg-slate-950 text-slate-500 text-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>
            <span>ForgeOS / Hami Universal Substrate</span>
            <span className="mx-2">•</span>
            <span>Driver: Zero Owner Dependency</span>
          </div>
          <div className="text-[11px] font-mono text-slate-600">
            Port 3000 • Express + Vite React • Invariant Active
          </div>
        </div>
      </footer>
    </div>
  );
}
