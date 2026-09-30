from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ExperimentProposalCreate(BaseModel):
    source_analyze_id: Optional[int] = None
    source_signal_id: Optional[int] = None
    source_research_question_id: Optional[int] = None
    source_research_task_ids: Optional[list[int]] = None
    problem_statement: str = Field(..., min_length=1)
    hypothesis: str = Field(..., min_length=1)
    evidence_summary: Optional[str] = None
    target: Optional[str] = None
    offer: Optional[str] = None
    action_type: str = Field(default="research")
    channel: Optional[str] = None


class ExperimentAuthorize(BaseModel):
    authorization_status: str = Field(default="allowed")
    authorization_reason: Optional[str] = None
    authorized_by: Optional[str] = None


class ExperimentOutcomeCreate(BaseModel):
    response_received: str = Field(default="none")
    response_raw: Optional[str] = None
    execution_notes: Optional[str] = None
    revenue_amount: float = 0.0
    revenue_currency: str = "USD"
    learning_event_id: Optional[int] = None
    next_decision: Optional[str] = None


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    opportunity_id: Optional[int] = None
    action: str
    result: Optional[str] = None
    lesson: Optional[str] = None
    created_at: datetime

    source_analyze_id: Optional[int] = None
    source_signal_id: Optional[int] = None
    source_research_question_id: Optional[int] = None
    source_research_task_ids: Optional[list[int]] = None

    authorization_status: str = "require_approval"
    authorization_reason: Optional[str] = None
    authorized_by: Optional[str] = None
    authorized_at: Optional[datetime] = None

    execution_status: str = "proposed"
    executed_at: Optional[datetime] = None
    execution_notes: Optional[str] = None

    response_received: str = "none"
    response_raw: Optional[str] = None
    response_received_at: Optional[datetime] = None

    revenue_amount: float = 0.0
    revenue_currency: str = "USD"
    revenue_recorded_at: Optional[datetime] = None

    learning_event_id: Optional[int] = None
    next_decision: Optional[str] = None

    # compatibility projection
    hypothesis: Optional[str] = None
    expected_result: Optional[str] = None
    revenue: Optional[float] = None
    conversions: Optional[int] = None
    confidence_change: Optional[float] = None
    strategy_id: Optional[int] = None
    action_type: Optional[str] = None
    status: str = "planned"
    execution_mode: Optional[str] = None
    requires_owner_approval: bool = False
    approved_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    costs: Optional[float] = None
    required_inputs: Optional[str] = None
    estimated_cost: Optional[float] = None
    risk_score: Optional[float] = None
    policy_decision: Optional[str] = None
    policy_reason: Optional[str] = None
    attempt_number: int = 1
