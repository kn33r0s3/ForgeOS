from datetime import date, datetime, timezone
import json
from pathlib import Path

import pytest

from app import models
from app.services import (
    collector_runner,
    research_planner,
    research_task_engine,
    source_clearance_registry,
)
from app.services.collectors import world_bank
from app.services.research_evidence_assessment import world_bank_requirement_eligibility


INDICATOR_ID = "SP.POP.TOTL"
SOURCE_ORGANIZATION = (
    "World Population Prospects, United Nations (UN), publisher: UN Population Division"
)
METADATA_PAYLOAD = [
    {"page": 1, "pages": 1, "per_page": "1", "total": 1},
    [
        {
            "id": INDICATOR_ID,
            "name": "Population, total",
            "unit": "",
            "source": {"id": "2", "value": "World Development Indicators"},
            "sourceNote": "Total population, midyear estimates.",
            "sourceOrganization": SOURCE_ORGANIZATION,
        }
    ],
]
OBSERVATION_PAYLOAD = [
    {"page": 1, "pages": 1, "per_page": 21, "total": 1, "sourceid": "2"},
    [
        {
            "indicator": {"id": INDICATOR_ID, "value": "Population, total"},
            "country": {"id": "NP", "value": "Nepal"},
            "countryiso3code": "NPL",
            "date": "2022",
            "value": 29715436,
            "unit": "",
            "source": None,
            "decimal": 0,
        }
    ],
]


def _mock_api(monkeypatch):
    requested = []

    def fake_read_json(endpoint, params):
        requested.append((endpoint, params))
        if endpoint.endswith(f"/country/NPL/indicator/{INDICATOR_ID}"):
            return OBSERVATION_PAYLOAD
        if endpoint.endswith(f"/indicator/{INDICATOR_ID}"):
            return METADATA_PAYLOAD
        raise AssertionError(f"Unexpected World Bank endpoint: {endpoint}")

    monkeypatch.setattr(world_bank.WorldBankCollector, "_verify_live_policy", lambda *_: None)
    monkeypatch.setattr(world_bank.WorldBankCollector, "_request_authorization", lambda *_: None)
    monkeypatch.setattr(world_bank, "_read_json", fake_read_json)
    return requested


def test_world_bank_clearance_is_bounded_current_and_attributed(db):
    entry = next(
        item
        for item in source_clearance_registry.source_clearances()
        if item.collector == "world_bank_indicators"
    )
    assert entry.registry_id == "world-bank-indicators-v2"
    assert entry.url == world_bank.API_ROOT
    assert entry.allowed_operation == "read_indicator_observations_and_indicator_attribution"
    assert set(entry.allowed_fields) >= {
        "indicator.id",
        "indicator.value",
        "country.id",
        "country.value",
        "date",
        "value",
        "unit",
        "sourceOrganization",
    }
    assert entry.min_interval_seconds == 1
    assert set(entry.provenance_requirements) >= {
        "canonical_url",
        "source_registry_id",
        "source_organization",
        "third_party_sources_indicated",
        "attribution",
    }
    assert source_clearance_registry.collector_is_cleared(
        "world_bank_indicators", today=date(2026, 9, 27)
    )
    assert source_clearance_registry.capabilities_for_requirement(
        "population_baseline", today=date(2026, 9, 27)
    ) == (entry,)
    assert not source_clearance_registry.capabilities_for_requirement(
        "buyer_willingness_to_pay", today=date(2026, 9, 27)
    )
    authorization = source_clearance_registry.authorize_request(
        entry.url,
        collector=entry.collector,
        db=db,
        today=date(2026, 9, 27),
        now=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
    )
    assert authorization.entry == entry
    with pytest.raises(source_clearance_registry.SourceRateLimitError):
        source_clearance_registry.authorize_request(
            entry.url,
            collector=entry.collector,
            db=db,
            today=date(2026, 9, 27),
            now=datetime(2026, 9, 27, 12, 0, 0, 500000, tzinfo=timezone.utc),
        )
    source_register = Path(__file__).resolve().parents[2] / "docs" / "PUBLIC_SOURCES.md"
    register_text = source_register.read_text()
    assert all(
        reference in register_text
        if reference.startswith("https://")
        else (source_register.parents[1] / reference).exists()
        for reference in entry.evidence_references
    )


def test_world_bank_parser_keeps_permitted_fields_and_third_party_attribution(db, monkeypatch):
    requested = _mock_api(monkeypatch)
    rows = world_bank.WorldBankCollector().fetch_indicator(
        db=db,
        country_code="NPL",
        indicator_id=INDICATOR_ID,
        start_year=2022,
        end_year=2022,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["content"] == "Country: Nepal, Indicator: Population, total, Year: 2022, Value: 29715436"
    assert row["external_id"] == "NPL:SP.POP.TOTL:2022"
    assert row["provenance"]["source_id"] == "NPL:SP.POP.TOTL:2022"
    assert row["provenance"]["source_type"] == "world_bank_indicators"
    assert row["provenance"]["traceable"] is True
    assert row["provenance"]["world_bank_source_id"] == "2"
    assert row["canonical_url"].startswith(
        "https://api.worldbank.org/v2/country/NPL/indicator/SP.POP.TOTL?"
    )
    assert row["provenance"]["source_registry_id"] == "world-bank-indicators-v2"
    assert row["provenance"]["source_name"] == "World Development Indicators"
    assert row["provenance"]["source_organization"] == SOURCE_ORGANIZATION
    assert row["provenance"]["third_party_sources_indicated"] is True
    assert row["provenance"]["ownership_assessment"].startswith("third-party source organizations listed")
    assert "CC BY 4.0" in row["provenance"]["license_basis"]
    assert row["provenance"]["license_status"] == "unconfirmed_third_party"
    assert row["provenance"]["license_compatibility_verified"] is False
    assert requested[0][0] == f"{world_bank.API_ROOT}/indicator/{INDICATOR_ID}"
    assert requested[1][0] == f"{world_bank.API_ROOT}/country/NPL/indicator/{INDICATOR_ID}"
    assert requested[1][1]["format"] == "json"
    assert requested[1][1]["date"] == "2022:2022"
    assert set(row["provenance"]["observation"]) == {
        "indicator",
        "country",
        "date",
        "value",
        "unit",
        "source",
    }
    assert "countryiso3code" not in row["provenance"]["observation"]
    assert "decimal" not in row["provenance"]["observation"]


def test_world_bank_scope_validation_fails_closed(db, monkeypatch):
    requested = _mock_api(monkeypatch)
    collector = world_bank.WorldBankCollector()
    with pytest.raises(ValueError, match="ISO code"):
        collector.fetch_indicator(
            db=db,
            country_code="NPL/../../bad",
            indicator_id=INDICATOR_ID,
            start_year=2022,
            end_year=2022,
        )
    with pytest.raises(ValueError, match="year range"):
        collector.fetch_indicator(
            db=db,
            country_code="NPL",
            indicator_id=INDICATOR_ID,
            start_year=2000,
            end_year=2022,
        )
    assert requested == []


def test_world_bank_macro_evidence_never_satisfies_market_requirements():
    provenance = {
        "source_registry_id": "world-bank-indicators-v2",
        "canonical_url": "https://api.worldbank.org/v2/country/NPL/indicator/SP.POP.TOTL",
        "attribution": "World Bank, World Development Indicators",
        "indicator_id": INDICATOR_ID,
        "country_code": "NPL",
        "year": 2022,
        "value": 29715436,
        "third_party_sources_indicated": False,
        "license_status": "dataset_default_requires_attribution; indicator_specific_license_unreported",
    }
    eligible, reason = world_bank_requirement_eligibility(
        "population_baseline",
        provenance,
        expected_country="NPL",
        expected_indicator=INDICATOR_ID,
        expected_years=(2022, 2022),
    )
    assert eligible is True
    assert reason == "attributable_macro_indicator_observation"

    for requirement_id in ("buyer_willingness_to_pay", "product_demand"):
        eligible, reason = world_bank_requirement_eligibility(requirement_id, provenance)
        assert eligible is False
        assert reason == "macro_indicator_data_cannot_validate_micro_demand_or_buyer_willingness_to_pay"
    for requirement_id in ("customer_pain", "problem_incidence"):
        eligible, reason = world_bank_requirement_eligibility(requirement_id, provenance)
        assert eligible is False
        assert reason == "macro_indicator_data_cannot_validate_customer_pain_or_micro_incidence"
    eligible, reason = world_bank_requirement_eligibility("alternatives_and_costs", provenance)
    assert eligible is False
    assert reason == "macro_indicator_data_cannot_validate_product_alternatives_or_prices"

    mismatch, mismatch_reason = world_bank_requirement_eligibility(
        "population_baseline",
        provenance,
        expected_country="USA",
        expected_indicator=INDICATOR_ID,
        expected_years=(2022, 2022),
    )
    assert mismatch is False
    assert mismatch_reason == "world_bank_observation_country_out_of_scope"


def test_unconfirmed_third_party_world_bank_data_cannot_satisfy_requirements():
    provenance = {
        "source_registry_id": "world-bank-indicators-v2",
        "canonical_url": "https://api.worldbank.org/v2/country/NPL/indicator/SP.POP.TOTL",
        "attribution": "World Bank, World Development Indicators",
        "indicator_id": INDICATOR_ID,
        "country_code": "NPL",
        "year": 2022,
        "value": 29715436,
        "third_party_sources_indicated": True,
        "license_status": "unconfirmed_third_party",
        "license_compatibility_verified": False,
    }

    eligible, reason = world_bank_requirement_eligibility("population_baseline", provenance)

    assert eligible is False
    assert reason == "world_bank_third_party_license_unconfirmed"

    provenance["license_status"] = "confirmed_cc_by_4.0"
    eligible, reason = world_bank_requirement_eligibility("population_baseline", provenance)
    assert eligible is False
    assert reason == "world_bank_third_party_license_unconfirmed"


def test_planner_keeps_unlicensed_macro_and_demand_requirements_unresolved(
    db, monkeypatch
):
    requested = _mock_api(monkeypatch)
    question = models.ResearchQuestion(
        question=f"Check population baseline WB:NPL:{INDICATOR_ID}:2022"
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    tasks = research_planner.plan_tasks_for_question(db, question)
    task = next(task for task in tasks if task.source == "world_bank_indicators")
    result = collector_runner.execute_task(db, task)
    db.refresh(question)

    assert result["status"] == "completed"
    population = next(
        item for item in question.research_plan["requirements"]
        if item["id"] == "population_baseline"
    )
    assert population["status"] == "terminal_unresolved"
    assert population["terminal_reason"] == "world_bank_third_party_license_unconfirmed"
    assert population["evidence_ids"] == []
    assert db.query(models.Evidence).filter_by(source="world_bank_indicators").count() == 1
    buyer_requirement = next(
        item for item in question.research_plan["requirements"]
        if item["id"] == "buyer_willingness_to_pay"
    )
    assert buyer_requirement["status"] == "terminal_unresolved"
    assert buyer_requirement["terminal_reason"] == (
        "macro_indicator_data_cannot_validate_micro_demand_or_buyer_willingness_to_pay"
    )
    assert len(requested) == 2


def test_world_bank_observations_persist_idempotently(db, monkeypatch):
    _mock_api(monkeypatch)
    first = world_bank.fetch_indicator(
        "NPL",
        INDICATOR_ID,
        2022,
        2022,
        db=db,
    )
    second = world_bank.fetch_indicator(
        "NPL",
        INDICATOR_ID,
        2022,
        2022,
        db=db,
    )

    evidence = db.query(models.Evidence).filter_by(source="world_bank_indicators").all()
    signal = db.query(models.Signal).filter_by(source="world_bank_indicators").one()
    provenance = json.loads(evidence[0].provenance)
    assert len(first) == len(second) == 1
    assert first[0].id == second[0].id == evidence[0].id
    assert len(evidence) == 1
    assert signal.external_id == f"NPL:{INDICATOR_ID}:2022"
    assert provenance["third_party_sources_indicated"] is True
    assert provenance["license_status"] == "unconfirmed_third_party"
    assert provenance["attribution"].startswith("World Bank, World Development Indicators")


def test_world_bank_task_query_requires_structured_bounded_scope(db):
    question = models.ResearchQuestion(question="Population baseline WB:NPL:SP.POP.TOTL:2022")
    db.add(question)
    db.commit()
    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        source="world_bank_indicators",
        query="unbounded natural language query",
    )
    with pytest.raises(ValueError, match="JSON object"):
        world_bank.WorldBankCollector().collect(task.query, db=db)
