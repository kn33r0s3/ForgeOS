from app.services.intelligence_pipeline import IntelligencePipeline


def test_pipeline_filters_low_confidence_signal():
    result = IntelligencePipeline().process_strategy_signal({"confidence": 0.4})

    assert result == {"status": "filtered", "reason": "Low confidence or noise"}


def test_pipeline_does_not_claim_causality_without_evidence():
    result = IntelligencePipeline().process_strategy_signal({"confidence": 0.9})

    assert result["status"] == "unverified"
    assert result["causal_data"]["reason"] == "No causal evidence supplied"


def test_pipeline_formulates_decision_from_verified_evidence():
    result = IntelligencePipeline().process_strategy_signal(
        {
            "confidence": 0.9,
            "action": "INTERVIEW",
            "causal_data": {"verified": True, "evidence_score": 0.85},
        }
    )

    assert result["status"] == "decided"
    assert result["decision"]["action"] == "INTERVIEW"
    assert result["decision"]["evidence_score"] == 0.85