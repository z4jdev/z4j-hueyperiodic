"""Capability tokens for the Huey periodic-task scheduler adapter.

Read-only by design: Huey's periodic tasks are decorator-defined
in source code, not runtime-managed.
"""

from __future__ import annotations

DEFAULT_CAPABILITIES: frozenset[str] = frozenset(
    {
        "list",
        "read",
    },
)


__all__ = ["DEFAULT_CAPABILITIES"]
