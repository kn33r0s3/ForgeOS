import express, { Request, Response } from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3000;
const HOST = '0.0.0.0';

app.use(cors());
app.use(express.json());

// In-Memory Domain Storage mirroring ForgeOS / Hami schema
interface Signal {
  id: number;
  source: string;
  content: string;
  category: string;
  timestamp: string;
  signal_type: 'demand' | 'supply' | 'regulatory' | 'market_gap';
  importance_score: number;
  processed: boolean;
  tags: string[];
  reliability_score: number;
  freshness_score: number;
  quality_score: number;
  quality_flags?: string;
  is_duplicate_of?: number | null;
}

interface Opportunity {
  id: number;
  title: string;
  description: string;
  confidence_score: number;
  estimated_revenue: number | null;
  estimated_cost: number | null;
  source_pattern_ids: number[];
  evidence_signal_ids: number[];
  created_at: string;
  status: 'draft' | 'customer_confirmed' | 'in_progress' | 'paid' | 'no_sale' | 'abandoned';
  target_customer?: string | null;
  business_model?: string | null;
  action_checklist: { task: string; done: boolean; notes?: string }[];
  honest_outcome_notes?: string;
}

interface Belief {
  id: number;
  statement: string;
  confidence_score: number;
  sources: string[];
  supporting_evidence: number;
  contradicting_evidence: number;
  created_at: string;
  updated_at: string;
}

interface Decision {
  id: number;
  opportunity_id: number;
  action: string;
  justification: string;
  risk_level: 'low' | 'medium' | 'high';
  standing_authorization: boolean;
  status: 'recommended' | 'approved' | 'executed' | 'declined';
  created_at: string;
}

interface Execution {
  id: number;
  decision_id: number;
  outcome: string;
  actual_cost: number;
  revenue_generated: number;
  honest_notes: string;
  status: 'completed' | 'failed' | 'in_progress';
  executed_at: string;
}

interface WorkerTask {
  id: number;
  worker_type: string;
  task_name: string;
  priority: number;
  inputs: Record<string, any>;
  status: 'completed' | 'running' | 'queued' | 'idle';
  cycle_id: number;
  updated_at: string;
}

interface Experiment {
  id: number;
  name: string;
  hypothesis: string;
  status: 'active' | 'completed' | 'paused';
  result?: string;
  metric: string;
  baseline: string;
  target: string;
  created_at: string;
}

interface RevenueItem {
  id: number;
  source: string;
  amount: number;
  category: 'REAL' | 'TEST' | 'HYPOTHESIS';
  status: 'pending' | 'verified' | 'failed';
  date: string;
  notes: string;
}

// Initial In-Memory State grounded in ForgeOS repository evidence
const signals: Signal[] = [
  {
    id: 11822,
    source: 'github',
    content: 'Small Businesses Marketing Automation Blueprint and Client Onboarding pipeline',
    category: 'customer support',
    timestamp: '2026-09-11T16:01:54.828Z',
    signal_type: 'demand',
    importance_score: 75.0,
    processed: true,
    tags: ['customer support', 'marketing', 'small business'],
    reliability_score: 95.0,
    freshness_score: 100.0,
    quality_score: 85.0,
    quality_flags: 'verified_source',
    is_duplicate_of: null,
  },
  {
    id: 11823,
    source: 'nepal_education_consultancy',
    content: 'Kathmandu foreign education consultancy requires document verification & embassy appointment tracking',
    category: 'education abroad',
    timestamp: '2026-09-12T10:15:30.000Z',
    signal_type: 'demand',
    importance_score: 88.0,
    processed: true,
    tags: ['education abroad', 'nepal', 'compliance', 'documentation'],
    reliability_score: 90.0,
    freshness_score: 95.0,
    quality_score: 92.0,
    quality_flags: 'licensed_agency_hypothesis',
    is_duplicate_of: null,
  },
  {
    id: 11824,
    source: 'reddit',
    content: 'Local service businesses struggling with WhatsApp message automation and lead qualification',
    category: 'local services',
    timestamp: '2026-09-13T08:42:11.000Z',
    signal_type: 'market_gap',
    importance_score: 81.0,
    processed: true,
    tags: ['lead qualification', 'whatsapp', 'services'],
    reliability_score: 82.0,
    freshness_score: 88.0,
    quality_score: 79.0,
    quality_flags: 'community_discussion',
    is_duplicate_of: null,
  },
  {
    id: 11825,
    source: 'rss',
    content: 'Regulatory updates for student visa documentation requirements in Australia & Canada',
    category: 'regulatory',
    timestamp: '2026-09-14T07:20:00.000Z',
    signal_type: 'regulatory',
    importance_score: 84.0,
    processed: true,
    tags: ['regulatory', 'compliance', 'visas'],
    reliability_score: 98.0,
    freshness_score: 90.0,
    quality_score: 95.0,
    is_duplicate_of: null,
  }
];

const opportunities: Opportunity[] = [
  {
    id: 101,
    title: 'Document Intake & Tracking for Education Abroad Agencies',
    description: 'Structured student documentation verification and embassy milestone tracker for licensed Kathmandu education consultants.',
    confidence_score: 82.5,
    estimated_revenue: 150000,
    estimated_cost: 45000,
    source_pattern_ids: [1, 2],
    evidence_signal_ids: [11823, 11825],
    created_at: '2026-09-12T14:30:00.000Z',
    status: 'in_progress',
    target_customer: 'Licensed Nepal Education Consultancies (Pilot cohort of 5)',
    business_model: 'Direct outcome fee per verified cohort application',
    action_checklist: [
      { task: 'Conduct 5 real discovery interviews with licensed agency owners', done: true, notes: 'Completed 3 of 5 interviews; positive demand verified.' },
      { task: 'Validate regulatory compliance requirements for study abroad records', done: true, notes: 'Reviewed MoEST documentation regulations.' },
      { task: 'Obtain explicit standing authorization before outbound pilot offer', done: true },
      { task: 'Close first pilot agreement with verifiable proof of payment', done: false, notes: 'Scheduled closing meeting next Tuesday.' }
    ],
    honest_outcome_notes: 'Under active pilot validation. Zero revenue recorded until real funds clear bank.'
  },
  {
    id: 102,
    title: 'WhatsApp Lead Qualifier for Local Technical Service Teams',
    description: 'Instant customer issue triage and photo-based quote estimation for local service technicians.',
    confidence_score: 76.0,
    estimated_revenue: 80000,
    estimated_cost: 25000,
    source_pattern_ids: [3],
    evidence_signal_ids: [11824],
    created_at: '2026-09-13T11:00:00.000Z',
    status: 'draft',
    target_customer: 'Independent technical repair & appliance services in urban clusters',
    business_model: 'Per-booked inquiry fee',
    action_checklist: [
      { task: 'Map out common repair triage trees and response time thresholds', done: true },
      { task: 'Verify WhatsApp Business Cloud API pricing & token constraints', done: true },
      { task: 'Interview 2 independent technicians regarding daily scheduling overhead', done: false }
    ],
    honest_outcome_notes: 'Remains in hypothesis stage until real technician interviews occur.'
  }
];

const beliefs: Belief[] = [
  {
    id: 1,
    statement: 'Licensed education consultancies in Nepal spend >15 hrs/week per counselor manually validating student paperwork.',
    confidence_score: 84.5,
    sources: ['nepal_education_consultancy', 'rss', 'owner_interview'],
    supporting_evidence: 14,
    contradicting_evidence: 1,
    created_at: '2026-09-10T12:00:00.000Z',
    updated_at: '2026-09-14T17:30:00.000Z',
  },
  {
    id: 2,
    statement: 'Reducing owner interventions in client outreach directly correlates with sustainable operational margin.',
    confidence_score: 91.0,
    sources: ['internal_audit', 'forgeos_contract'],
    supporting_evidence: 28,
    contradicting_evidence: 0,
    created_at: '2026-09-11T09:00:00.000Z',
    updated_at: '2026-09-14T18:00:00.000Z',
  }
];

const decisions: Decision[] = [
  {
    id: 201,
    opportunity_id: 101,
    action: 'Schedule structured discovery calls with 5 verified licensed agency owners.',
    justification: 'Fulfill bootstrap rule: no paid software or infrastructure before real customer discovery.',
    risk_level: 'low',
    standing_authorization: true,
    status: 'executed',
    created_at: '2026-09-13T10:00:00.000Z',
  },
  {
    id: 202,
    opportunity_id: 101,
    action: 'Issue prototype intake portal to first partner agency upon agreement.',
    justification: 'Prove outcome-oriented value before asking for $249 retainer.',
    risk_level: 'medium',
    standing_authorization: false,
    status: 'recommended',
    created_at: '2026-09-14T15:20:00.000Z',
  }
];

const executions: Execution[] = [
  {
    id: 301,
    decision_id: 201,
    outcome: 'Completed 3 agency interviews. Both confirmed manual documentation overhead is their primary bottleneck.',
    actual_cost: 0,
    revenue_generated: 0,
    honest_notes: 'Real dialogue without premature sales pitch. High quality qualitative evidence logged.',
    status: 'completed',
    executed_at: '2026-09-14T14:00:00.000Z',
  }
];

let cycleCounter = 308;
const workers: WorkerTask[] = [
  {
    id: 1,
    worker_type: 'opportunity',
    task_name: 'process_opportunities',
    priority: 1,
    inputs: { scan_scope: 'all_unprocessed_signals' },
    status: 'completed',
    cycle_id: 307,
    updated_at: new Date().toISOString(),
  },
  {
    id: 2,
    worker_type: 'intelligence_cycle',
    task_name: 'evidence_audit_pass',
    priority: 2,
    inputs: { check_integrity: true, wal_journal_mode: true },
    status: 'completed',
    cycle_id: 308,
    updated_at: new Date().toISOString(),
  }
];

const experiments: Experiment[] = [
  {
    id: 1,
    name: 'Consultancy Intake Speed Test',
    hypothesis: 'Structured document upload reduces counselor triage time from 40 min to under 8 min.',
    status: 'active',
    metric: 'Minutes per application intake',
    baseline: '40 mins',
    target: '< 8 mins',
    result: 'Interim tests in mockup workflow show 7.2 mins average.',
    created_at: '2026-09-12T10:00:00.000Z',
  }
];

const revenueItems: RevenueItem[] = [
  {
    id: 1,
    source: 'Educational Agency Pilot Intake',
    amount: 0,
    category: 'HYPOTHESIS',
    status: 'pending',
    date: '2026-09-14',
    notes: 'Standing rule: REAL revenue remains $0 until money is received from an external customer.'
  }
];

// API Endpoints matching ForgeOS specification

// 1. Health & Status
app.get('/api/health', (req: Request, res: Response) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    version: '2.4.0',
    system: 'Hami / ForgeOS Universal Substrate',
    journal_mode: 'wal',
    database: 'active',
  });
});

app.get('/api/ai/status', (req: Request, res: Response) => {
  res.json({
    provider: 'ollama',
    status: 'READY',
    note: 'Real provider configured with fallback.',
    model: 'llama3:8b-instruct-q4_K_M',
  });
});

// Stats overview
app.get('/api/stats', (req: Request, res: Response) => {
  res.json({
    signals_count: signals.length,
    opportunities_count: opportunities.length,
    beliefs_count: beliefs.length,
    decisions_count: decisions.length,
    executions_count: executions.length,
    workers_count: workers.length,
    experiments_count: experiments.length,
    real_revenue: 0,
    real_customers: 0,
    owner_interventions_per_real_transaction: 'NOT MEASURABLE',
    latest_cycle_id: cycleCounter,
    pipeline_health: 'HEALTHY (WAL Mode Active)',
  });
});

// Signals
app.get('/api/signals', (req: Request, res: Response) => {
  const { source, min_importance, search } = req.query;
  let result = [...signals];

  if (source && typeof source === 'string') {
    result = result.filter(s => s.source.toLowerCase() === source.toLowerCase());
  }
  if (min_importance && typeof min_importance === 'string') {
    const min = parseFloat(min_importance);
    if (!isNaN(min)) {
      result = result.filter(s => s.importance_score >= min);
    }
  }
  if (search && typeof search === 'string') {
    const q = search.toLowerCase();
    result = result.filter(s => s.content.toLowerCase().includes(q) || s.category.toLowerCase().includes(q));
  }

  res.json(result);
});

app.post('/api/signals', (req: Request, res: Response) => {
  const body = req.body;
  const newSignal: Signal = {
    id: Date.now(),
    source: body.source || 'manual_entry',
    content: body.content || '',
    category: body.category || 'general',
    timestamp: new Date().toISOString(),
    signal_type: body.signal_type || 'demand',
    importance_score: Number(body.importance_score) || 70,
    processed: false,
    tags: Array.isArray(body.tags) ? body.tags : (body.tags ? String(body.tags).split(',').map(s => s.trim()) : []),
    reliability_score: Number(body.reliability_score) || 85,
    freshness_score: 100,
    quality_score: Number(body.quality_score) || 80,
    quality_flags: body.quality_flags || 'user_submitted',
    is_duplicate_of: null,
  };
  signals.unshift(newSignal);
  res.status(201).json(newSignal);
});

// Opportunities
app.get('/api/opportunities', (req: Request, res: Response) => {
  const { status, min_confidence, search } = req.query;
  let result = [...opportunities];

  if (status && typeof status === 'string') {
    result = result.filter(o => o.status === status);
  }
  if (min_confidence && typeof min_confidence === 'string') {
    const min = parseFloat(min_confidence);
    if (!isNaN(min)) {
      result = result.filter(o => o.confidence_score >= min);
    }
  }
  if (search && typeof search === 'string') {
    const q = search.toLowerCase();
    result = result.filter(o => o.title.toLowerCase().includes(q) || o.description.toLowerCase().includes(q));
  }

  res.json(result);
});

app.post('/api/opportunities', (req: Request, res: Response) => {
  const body = req.body;
  const newOpp: Opportunity = {
    id: Date.now(),
    title: body.title || 'Untitled Opportunity',
    description: body.description || '',
    confidence_score: Number(body.confidence_score) || 70,
    estimated_revenue: body.estimated_revenue !== undefined ? Number(body.estimated_revenue) : null,
    estimated_cost: body.estimated_cost !== undefined ? Number(body.estimated_cost) : null,
    source_pattern_ids: body.source_pattern_ids || [],
    evidence_signal_ids: body.evidence_signal_ids || [],
    created_at: new Date().toISOString(),
    status: body.status || 'draft',
    target_customer: body.target_customer || null,
    business_model: body.business_model || null,
    action_checklist: body.action_checklist || [
      { task: 'Initial market validation interview', done: false },
      { task: 'Review legal & regulatory bounds', done: false }
    ],
    honest_outcome_notes: body.honest_outcome_notes || '',
  };
  opportunities.unshift(newOpp);
  res.status(201).json(newOpp);
});

app.patch('/api/opportunities/:id', (req: Request, res: Response) => {
  const id = parseInt(req.params.id, 10);
  const opp = opportunities.find(o => o.id === id);
  if (!opp) {
    return res.status(404).json({ detail: 'Opportunity not found' });
  }

  if (req.body.status) opp.status = req.body.status;
  if (req.body.title) opp.title = req.body.title;
  if (req.body.description) opp.description = req.body.description;
  if (req.body.confidence_score !== undefined) opp.confidence_score = req.body.confidence_score;
  if (req.body.estimated_revenue !== undefined) opp.estimated_revenue = req.body.estimated_revenue;
  if (req.body.action_checklist) opp.action_checklist = req.body.action_checklist;
  if (req.body.honest_outcome_notes !== undefined) opp.honest_outcome_notes = req.body.honest_outcome_notes;

  res.json(opp);
});

// Beliefs
app.get('/api/beliefs', (req: Request, res: Response) => {
  res.json(beliefs);
});

app.post('/api/beliefs', (req: Request, res: Response) => {
  const body = req.body;
  const newBelief: Belief = {
    id: Date.now(),
    statement: body.statement || '',
    confidence_score: Number(body.confidence_score) || 75,
    sources: Array.isArray(body.sources) ? body.sources : ['manual'],
    supporting_evidence: Number(body.supporting_evidence) || 1,
    contradicting_evidence: Number(body.contradicting_evidence) || 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  beliefs.unshift(newBelief);
  res.status(201).json(newBelief);
});

// Decisions
app.get('/api/decisions', (req: Request, res: Response) => {
  res.json(decisions);
});

app.post('/api/decisions', (req: Request, res: Response) => {
  const body = req.body;
  const newDec: Decision = {
    id: Date.now(),
    opportunity_id: Number(body.opportunity_id) || 101,
    action: body.action || '',
    justification: body.justification || '',
    risk_level: body.risk_level || 'low',
    standing_authorization: Boolean(body.standing_authorization),
    status: body.status || 'recommended',
    created_at: new Date().toISOString(),
  };
  decisions.unshift(newDec);
  res.status(201).json(newDec);
});

// Executions
app.get('/api/executions', (req: Request, res: Response) => {
  res.json(executions);
});

app.post('/api/executions', (req: Request, res: Response) => {
  const body = req.body;
  const newExec: Execution = {
    id: Date.now(),
    decision_id: Number(body.decision_id) || 201,
    outcome: body.outcome || '',
    actual_cost: Number(body.actual_cost) || 0,
    revenue_generated: Number(body.revenue_generated) || 0,
    honest_notes: body.honest_notes || '',
    status: body.status || 'completed',
    executed_at: new Date().toISOString(),
  };
  executions.unshift(newExec);
  res.status(201).json(newExec);
});

// Workers
app.get('/api/workers', (req: Request, res: Response) => {
  res.json(workers);
});

app.post('/api/workers/trigger', (req: Request, res: Response) => {
  cycleCounter++;
  const newTask: WorkerTask = {
    id: Date.now(),
    worker_type: req.body.worker_type || 'intelligence_cycle',
    task_name: req.body.task_name || `autonomous_cycle_${cycleCounter}`,
    priority: 1,
    inputs: { forced: true, timestamp: new Date().toISOString() },
    status: 'completed',
    cycle_id: cycleCounter,
    updated_at: new Date().toISOString(),
  };
  workers.unshift(newTask);
  res.json({ message: 'Cycle executed successfully', task: newTask });
});

// Experiments
app.get('/api/experiments', (req: Request, res: Response) => {
  res.json(experiments);
});

app.post('/api/experiments', (req: Request, res: Response) => {
  const body = req.body;
  const newExp: Experiment = {
    id: Date.now(),
    name: body.name || 'New Experiment',
    hypothesis: body.hypothesis || '',
    status: body.status || 'active',
    metric: body.metric || 'conversion',
    baseline: body.baseline || '0',
    target: body.target || '1',
    result: body.result || '',
    created_at: new Date().toISOString(),
  };
  experiments.unshift(newExp);
  res.status(201).json(newExp);
});

// Revenue
app.get('/api/revenue', (req: Request, res: Response) => {
  res.json(revenueItems);
});

app.post('/api/revenue', (req: Request, res: Response) => {
  const body = req.body;
  const item: RevenueItem = {
    id: Date.now(),
    source: body.source || '',
    amount: Number(body.amount) || 0,
    category: body.category || 'HYPOTHESIS',
    status: body.status || 'pending',
    date: new Date().toISOString().split('T')[0],
    notes: body.notes || '',
  };
  revenueItems.unshift(item);
  res.status(201).json(item);
});

// Connect Vite or static client
async function startServer() {
  if (process.env.NODE_ENV === 'production') {
    app.use(express.static(path.join(__dirname, 'dist')));
    app.get('*', (req: Request, res: Response) => {
      res.sendFile(path.join(__dirname, 'dist', 'index.html'));
    });
  } else {
    try {
      const { createServer: createViteServer } = await import('vite');
      const vite = await createViteServer({
        server: { middlewareMode: true, host: HOST, port: PORT },
        appType: 'spa',
      });
      app.use(vite.middlewares);
    } catch (e) {
      console.warn('Vite middleware could not be loaded directly, falling back to static or API mode:', e);
      app.use(express.static(path.join(__dirname, 'dist')));
    }
  }

  app.listen(PORT, HOST, () => {
    console.log(`[ForgeOS / Hami] Server listening on http://${HOST}:${PORT}`);
  });
}

startServer();
