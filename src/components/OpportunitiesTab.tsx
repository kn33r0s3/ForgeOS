import React, { useState } from 'react';
import { 
  Lightbulb, 
  Search, 
  Filter, 
  Plus, 
  CheckSquare, 
  Square, 
  DollarSign, 
  Users, 
  Briefcase, 
  FileText,
  AlertCircle,
  Save
} from 'lucide-react';
import { Opportunity, ActionChecklistItem } from '../types';

interface OpportunitiesTabProps {
  opportunities: Opportunity[];
  onUpdateOpportunity: (id: number, data: Partial<Opportunity>) => Promise<void>;
  onAddOpportunity: (oppData: Partial<Opportunity>) => Promise<void>;
}

export const OpportunitiesTab: React.FC<OpportunitiesTabProps> = ({
  opportunities,
  onUpdateOpportunity,
  onAddOpportunity,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingNotesId, setEditingNotesId] = useState<number | null>(null);
  const [tempNotes, setTempNotes] = useState('');

  // New Opportunity Form
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newConfidence, setNewConfidence] = useState(75);
  const [newRevenue, setNewRevenue] = useState('150000');
  const [newCost, setNewCost] = useState('40000');
  const [newCustomer, setNewCustomer] = useState('');
  const [newModel, setNewModel] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const statuses = ['draft', 'customer_confirmed', 'in_progress', 'paid', 'no_sale', 'abandoned'];

  const filteredOpportunities = opportunities.filter(opp => {
    const matchesSearch = opp.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      opp.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (opp.target_customer && opp.target_customer.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesStatus = selectedStatus === 'all' || opp.status === selectedStatus;
    return matchesSearch && matchesStatus;
  });

  const handleToggleChecklist = async (opp: Opportunity, itemIndex: number) => {
    const updatedChecklist = opp.action_checklist.map((item, idx) => 
      idx === itemIndex ? { ...item, done: !item.done } : item
    );
    await onUpdateOpportunity(opp.id, { action_checklist: updatedChecklist });
  };

  const handleStatusChange = async (opp: Opportunity, newStatus: any) => {
    await onUpdateOpportunity(opp.id, { status: newStatus });
  };

  const handleSaveNotes = async (oppId: number) => {
    await onUpdateOpportunity(oppId, { honest_outcome_notes: tempNotes });
    setEditingNotesId(null);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    setIsSubmitting(true);
    try {
      await onAddOpportunity({
        title: newTitle,
        description: newDescription,
        confidence_score: newConfidence,
        estimated_revenue: newRevenue ? parseInt(newRevenue, 10) : null,
        estimated_cost: newCost ? parseInt(newCost, 10) : null,
        target_customer: newCustomer || null,
        business_model: newModel || null,
        status: 'draft',
        action_checklist: [
          { task: 'Initial market validation interview with 5 agency owners', done: false },
          { task: 'Assess legal & regulatory compliance (Nepal MoEST)', done: false },
          { task: 'Obtain explicit standing authorization before outbound pilot', done: false }
        ],
        honest_outcome_notes: 'Initial hypothesis awaiting discovery findings.'
      });
      setNewTitle('');
      setNewDescription('');
      setNewCustomer('');
      setNewModel('');
      setShowAddModal(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Top Header & Actions */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <Lightbulb className="w-5 h-5 text-amber-400" />
            Qualified Opportunities &amp; Pilot Funnel
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Strict evidence progression: <span className="font-mono text-amber-300">draft → customer_confirmed → in_progress → paid / no_sale / abandoned</span>.
          </p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold rounded-lg shadow-sm transition"
        >
          <Plus className="w-4 h-4" />
          New Opportunity
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search opportunity title, description, customer..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-amber-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-500" />
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-2.5 py-2 focus:outline-none focus:border-amber-500 capitalize"
          >
            <option value="all">All Statuses ({opportunities.length})</option>
            {statuses.map(st => (
              <option key={st} value={st}>{st.replace('_', ' ')}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Opportunities Cards */}
      <div className="space-y-4">
        {filteredOpportunities.map((opp) => {
          const completedCount = opp.action_checklist.filter(c => c.done).length;
          const progressPercent = opp.action_checklist.length > 0 
            ? Math.round((completedCount / opp.action_checklist.length) * 100) 
            : 0;

          return (
            <div 
              key={opp.id} 
              className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700/80 transition space-y-4 shadow-sm"
            >
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-slate-500">OPP #{opp.id}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-mono font-medium border bg-amber-500/10 text-amber-400 border-amber-500/30">
                      {opp.confidence_score}% Confidence
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-slate-100">{opp.title}</h3>
                  <p className="text-xs text-slate-300 leading-relaxed max-w-4xl">{opp.description}</p>
                </div>

                <div className="flex items-center gap-2 self-start">
                  <label className="text-[11px] text-slate-500">Status:</label>
                  <select
                    value={opp.status}
                    onChange={(e) => handleStatusChange(opp, e.target.value)}
                    className={`text-xs font-semibold px-2.5 py-1 rounded-md border capitalize focus:outline-none ${
                      opp.status === 'in_progress'
                        ? 'bg-blue-950/80 text-blue-400 border-blue-800'
                        : opp.status === 'customer_confirmed'
                        ? 'bg-emerald-950/80 text-emerald-400 border-emerald-800'
                        : opp.status === 'paid'
                        ? 'bg-green-950/80 text-green-300 border-green-700'
                        : opp.status === 'abandoned' || opp.status === 'no_sale'
                        ? 'bg-rose-950/80 text-rose-400 border-rose-800'
                        : 'bg-slate-800 text-slate-300 border-slate-700'
                    }`}
                  >
                    {statuses.map(st => (
                      <option key={st} value={st}>{st.replace('_', ' ')}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Economic & Customer Details */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-slate-950/60 p-3 rounded-lg border border-slate-800/60 text-xs">
                <div>
                  <span className="text-[10px] text-slate-500 block uppercase font-medium">Target Customer</span>
                  <span className="text-slate-200 font-medium">{opp.target_customer || 'Not yet identified from evidence'}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block uppercase font-medium">Business Model</span>
                  <span className="text-slate-200 font-medium">{opp.business_model || 'Direct verified outcome fee'}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block uppercase font-medium">Est. Potential &amp; Cost</span>
                  <span className="text-slate-200 font-mono font-medium">
                    {opp.estimated_revenue ? `NPR ${opp.estimated_revenue.toLocaleString()}` : 'Null'}
                    <span className="text-slate-500 text-[11px] ml-1">
                      (Cost: {opp.estimated_cost ? `NPR ${opp.estimated_cost.toLocaleString()}` : '0'})
                    </span>
                  </span>
                </div>
              </div>

              {/* Action Checklist */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-400 flex items-center gap-1.5">
                    <CheckSquare className="w-3.5 h-3.5 text-amber-400" />
                    Validation Action Checklist
                  </span>
                  <span className="text-slate-500 font-mono text-[11px]">
                    {completedCount} of {opp.action_checklist.length} done ({progressPercent}%)
                  </span>
                </div>

                <div className="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden border border-slate-800">
                  <div 
                    className="bg-amber-500 h-full transition-all duration-300" 
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>

                <div className="space-y-1.5 pt-1">
                  {opp.action_checklist.map((item, idx) => (
                    <div 
                      key={idx}
                      onClick={() => handleToggleChecklist(opp, idx)}
                      className={`flex items-start gap-2.5 p-2 rounded-lg cursor-pointer transition border text-xs ${
                        item.done 
                          ? 'bg-emerald-950/20 border-emerald-900/30 text-slate-300' 
                          : 'bg-slate-950/40 border-slate-800/80 text-slate-300 hover:border-slate-700'
                      }`}
                    >
                      <button className="mt-0.5 text-amber-400">
                        {item.done ? (
                          <CheckSquare className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <Square className="w-4 h-4 text-slate-600" />
                        )}
                      </button>
                      <div className="flex-1">
                        <span className={item.done ? 'line-through text-slate-400' : ''}>
                          {item.task}
                        </span>
                        {item.notes && (
                          <p className="text-[11px] text-amber-300/80 mt-0.5 italic">
                            Evidence note: {item.notes}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Honest Outcome Notes */}
              <div className="pt-2 border-t border-slate-800/80">
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="font-semibold text-slate-400 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-slate-500" />
                    Honest Outcome Record (Mandatory for closure)
                  </span>
                  {editingNotesId !== opp.id && (
                    <button
                      onClick={() => {
                        setEditingNotesId(opp.id);
                        setTempNotes(opp.honest_outcome_notes || '');
                      }}
                      className="text-amber-400 hover:text-amber-300 text-[11px] font-medium"
                    >
                      Edit Note
                    </button>
                  )}
                </div>

                {editingNotesId === opp.id ? (
                  <div className="space-y-2">
                    <textarea
                      rows={2}
                      value={tempNotes}
                      onChange={(e) => setTempNotes(e.target.value)}
                      placeholder="Record real customer conversation result, reason for abandonment, or payment details..."
                      className="w-full p-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-amber-500"
                    />
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setEditingNotesId(null)}
                        className="px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleSaveNotes(opp.id)}
                        className="flex items-center gap-1 px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold rounded-md shadow-sm"
                      >
                        <Save className="w-3 h-3" />
                        Save Record
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/60 italic">
                    {opp.honest_outcome_notes || 'No outcome note recorded yet.'}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Add Opportunity Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-5 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <Lightbulb className="w-4 h-4 text-amber-400" />
                Formulate Opportunity Hypothesis
              </h3>
              <button 
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-200 text-sm font-mono"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                  Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Document Intake Portal for Licensed Consultancies"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                  Description / Economic Value *
                </label>
                <textarea
                  rows={2}
                  required
                  placeholder="What customer problem is solved? What evidence backs this?"
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                    Target Customer
                  </label>
                  <input
                    type="text"
                    placeholder="Licensed agency owners"
                    value={newCustomer}
                    onChange={(e) => setNewCustomer(e.target.value)}
                    className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-amber-500"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                    Business Model
                  </label>
                  <input
                    type="text"
                    placeholder="Outcome-fee per verified candidate"
                    value={newModel}
                    onChange={(e) => setNewModel(e.target.value)}
                    className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-amber-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                    Est. Revenue (NPR)
                  </label>
                  <input
                    type="number"
                    value={newRevenue}
                    onChange={(e) => setNewRevenue(e.target.value)}
                    className="w-full p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-amber-500"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                    Confidence Score ({newConfidence}%)
                  </label>
                  <input
                    type="range"
                    min="10"
                    max="100"
                    value={newConfidence}
                    onChange={(e) => setNewConfidence(parseInt(e.target.value, 10))}
                    className="w-full mt-2 accent-amber-500"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3.5 py-1.5 text-xs text-slate-400 hover:text-slate-200 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold rounded-lg shadow-sm transition disabled:opacity-50"
                >
                  {isSubmitting ? 'Formulating...' : 'Create Opportunity'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
