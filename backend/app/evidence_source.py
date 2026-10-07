"""Canonical evidence source labels (renovation, Phase 4).

The four labels the whole system uses to say what a row IS:

- REAL: a fact from the real world (a real person, real money, real event).
- TEST: produced by the test suite. Never counts as traction.
- MOCK: placeholder / fixture / generated stand-in. Never counts as traction.
- HYPOTHESIS: an untested belief or prediction. Never counts as traction.

Only REAL rows with attached proof feed public numbers (see
services/public_stats.py). New rows default to MOCK — nothing is REAL
unless it is explicitly labeled REAL with proof.

Why a new file: no existing module defines these four labels. AGENTS.md's
bootstrap rule names them but defines nothing; models.py's ``data_scope``
is a different axis (REAL vs SANDBOX environment), not an epistemic label.
"""

REAL = "REAL"
TEST = "TEST"
MOCK = "MOCK"
HYPOTHESIS = "HYPOTHESIS"

ALL = (REAL, TEST, MOCK, HYPOTHESIS)


def validate(value: str) -> str:
    """Return the uppercased label, or raise ValueError for anything else."""
    normalized = (value or "").strip().upper()
    if normalized not in ALL:
        raise ValueError(
            f"Invalid evidence source: {value!r}. Must be one of {ALL}."
        )
    return normalized


def is_real(value: str | None) -> bool:
    """True only for the REAL label."""
    return (value or "").strip().upper() == REAL
