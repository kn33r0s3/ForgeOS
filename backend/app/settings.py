"""Startup settings gate (renovation, Phase 3).

Lists environment variables that MUST be set for the app to start. If any
is missing, startup prints one clear line per missing name —
``Missing setting: NAME`` — and refuses to start. Values are never printed.

The list is EMPTY today, honestly: the app starts on its SQLite fallback
with no external services, so nothing is genuinely required. Add a name
here only when startup truly cannot proceed without it — never to satisfy
a checklist.
"""

import os
import sys

# Names that MUST be set for startup. Empty = nothing required today.
REQUIRED_ENV_VARS: list[str] = []


def check_required_env(required: "list[str] | None" = None) -> None:
    """Fail startup loudly if any required env var is missing.

    Prints ``Missing setting: NAME`` (one line per name, never values)
    and raises SystemExit(1). A no-op when nothing is required.
    """
    names = REQUIRED_ENV_VARS if required is None else required
    missing = [name for name in names if not os.getenv(name)]
    if not missing:
        return
    for name in missing:
        print(f"Missing setting: {name}", file=sys.stderr)
    raise SystemExit(1)
