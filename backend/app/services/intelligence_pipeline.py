"""Small, explicit bridge from strategy signals to decisions.

This service only promotes signals that meet the caller's confidence
threshold and have causal evidence. It does not execute the resulting
decision or manufacture evidence.
"""

from __future__ import annotations

from typing import Any


class IntelligencePipeline:
    """Filter, validate, and formulate a decision from a strategy signal."""

    def process_strategy_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        if signal.get("confidence", 0) < 0.5 or signal.get("is_noisy", False):
            return {"status": "filtered", "reason": "Low confidence or noise"}

        causal_link = self._verify_causality(signal)
        if not causal_link.get("verified", False):
            return {"status": "unverified", "causal_data": causal_link}

        return {
            "status": "decided",
            "decision": self._formulate_decision(signal, causal_link),
        }

    def _verify_causality(self, signal: dict[str, Any]) -> dict[str, Any]:
        causal_data = signal.get("causal_data")
        if not isinstance(causal_data, dict):
            return {"verified": False, "reason": "No causal evidence supplied"}
        return {
            "verified": bool(causal_data.get("verified", False)),
            "evidence_score": causal_data.get("evidence_score"),
        }

    def _formulate_decision(
        self, signal: dict[str, Any], causal: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "decision_id": signal.get("decision_id"),
            "action": signal.get("action", "PROCEED"),
            "rationale": "Causality verified with supplied evidence.",
            "evidence_score": causal.get("evidence_score"),
        }