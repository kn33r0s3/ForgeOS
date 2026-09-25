"""Calculations for realized offer economics.

These helpers intentionally accept only recorded values. They do not forecast
revenue, infer a payment from a stated price, or treat a draft as income.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RealizedEconomics:
    received_npr: Decimal
    direct_cost_npr: Decimal
    hours: Decimal
    net_npr: Decimal
    hourly_result_npr: Decimal | None


def calculate_realized_economics(
    *,
    received_npr: Decimal,
    direct_cost_npr: Decimal,
    hours: Decimal,
) -> RealizedEconomics:
    """Calculate net and hourly result from actual recorded inputs."""
    for name, value in (
        ("received_npr", received_npr),
        ("direct_cost_npr", direct_cost_npr),
        ("hours", hours),
    ):
        if not value.is_finite():
            raise ValueError(f"{name} must be finite")
        if value < 0:
            raise ValueError(f"{name} cannot be negative")

    net_npr = received_npr - direct_cost_npr
    hourly_result_npr = net_npr / hours if hours > 0 else None
    return RealizedEconomics(
        received_npr=received_npr,
        direct_cost_npr=direct_cost_npr,
        hours=hours,
        net_npr=net_npr,
        hourly_result_npr=hourly_result_npr,
    )
