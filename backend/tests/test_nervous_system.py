"""Test Hami's non-legacy event-driven nervous system.

The nervous system recovers useful behavior from the historical Forge cycle
without reviving FORGEOS_LEGACY_INTELLIGENCE_ENABLED:
- forge_loop.run_cycle: state → patterns → beliefs → questions → tasks
- research_task_engine.resume_running_tasks: eligible work → requeue
- execution_engine.run_autonomous_action_cycle: opportunities → proposed actions

Verifies safety, structure, and the continuous loop architecture.
"""

import inspect

from app.api import scheduled
from app.services import research_task_engine, execution_engine


class TestNervousSystemStructure:
    """Verify the nervous system has the correct structure."""
    
    def test_run_nervous_system_exists(self):
        """run_nervous_system must exist in scheduled module."""
        assert hasattr(scheduled, 'run_nervous_system')
        assert callable(scheduled.run_nervous_system)
    
    def test_no_legacy_flag_check(self):
        """Nervous system must not check FORGEOS_LEGACY_INTELLIGENCE_ENABLED."""
        source = inspect.getsource(scheduled.run_nervous_system)
        assert "FORGEOS_LEGACY_INTELLIGENCE_ENABLED" not in source
    
    def test_uses_three_engines(self):
        """Nervous system must use forge_loop, research_task_engine, execution_engine."""
        source = inspect.getsource(scheduled.run_nervous_system)
        assert "forge_loop" in source
        assert "research_task_engine" in source
        assert "execution_engine" in source
    
    def test_no_network_fetching(self):
        """Nervous system must not do network fetching (collector excluded)."""
        source = inspect.getsource(scheduled.run_nervous_system)
        assert "collector_runner" not in source
    
    def test_failure_isolation_structure(self):
        """Each engine must have its own try/except for isolation."""
        source = inspect.getsource(scheduled.run_nervous_system)
        # Three engines, each with try/except
        assert source.count("try:") >= 3
        assert source.count("except Exception") >= 3


class TestSafetyBoundaries:
    """Verify the nervous system preserves safety boundaries."""
    
    def test_autonomy_proposes_never_executes(self):
        """Autonomy cycle must propose actions, never execute them."""
        source = inspect.getsource(execution_engine.run_autonomous_action_cycle)
        # Must NOT call start_action (execution)
        assert "start_action" not in source
    
    def test_research_engine_has_retry(self):
        """Research engine must support retries for failed tasks."""
        assert hasattr(research_task_engine, 'retry_task')
        assert hasattr(research_task_engine, 'fail_task')
        assert hasattr(research_task_engine, 'defer_task')
    
    def test_resume_only_stale(self):
        """Resume must only touch stale running tasks, not all tasks."""
        source = inspect.getsource(research_task_engine.resume_running_tasks)
        assert "stale" in source.lower() or "cutoff" in source


class TestContinuousLoopArchitecture:
    """Verify the architecture supports EVENT → WORK → FOLLOW-ON."""
    
    def test_forge_cycle_generates_questions(self):
        """Forge cycle must generate research questions (work creation)."""
        from app.services import forge_loop
        source = inspect.getsource(forge_loop.run_cycle)
        # Must have curiosity scan (question generation)
        assert "curiosity" in source.lower() or "question" in source.lower()
    
    def test_questions_lead_to_tasks(self):
        """Research planner must create tasks for questions (work planning)."""
        from app.services import research_planner
        assert hasattr(research_planner, 'plan_tasks_for_open_questions')
    
    def test_tasks_have_lifecycle(self):
        """Tasks must have full lifecycle: plan → run → complete/fail/retry."""
        assert hasattr(research_task_engine, 'create_task')
        assert hasattr(research_task_engine, 'begin_task')
        assert hasattr(research_task_engine, 'finish_task')
        assert hasattr(research_task_engine, 'fail_task')
        assert hasattr(research_task_engine, 'retry_task')
    
    def test_independent_branches(self):
        """Multiple tasks must coexist (no global singleton lock)."""
        from app import models
        # ResearchTask is a table; multiple rows = multiple branches
        assert hasattr(models, 'ResearchTask')
        # Tasks have status, not a global lock
        columns = [c.name for c in models.ResearchTask.__table__.columns]
        assert "status" in columns
