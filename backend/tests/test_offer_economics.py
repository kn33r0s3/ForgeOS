from decimal import Decimal

import pytest

from app.services.offer_economics import calculate_realized_economics


def test_realized_economics_uses_only_recorded_values():
    result = calculate_realized_economics(
        received_npr=Decimal("1500"),
        direct_cost_npr=Decimal("300"),
        hours=Decimal("4"),
    )

    assert result.net_npr == Decimal("1200")
    assert result.hourly_result_npr == Decimal("300")


def test_zero_hours_does_not_invent_an_hourly_result():
    result = calculate_realized_economics(
        received_npr=Decimal("0"),
        direct_cost_npr=Decimal("50"),
        hours=Decimal("0"),
    )

    assert result.net_npr == Decimal("-50")
    assert result.hourly_result_npr is None


@pytest.mark.parametrize("field", ["received_npr", "direct_cost_npr", "hours"])
def test_negative_inputs_are_rejected(field):
    values = {
        "received_npr": Decimal("1"),
        "direct_cost_npr": Decimal("1"),
        "hours": Decimal("1"),
    }
    values[field] = Decimal("-1")

    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_realized_economics(**values)
