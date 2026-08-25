"""The :class:`HueyPeriodicAdapter` - read-only scheduler adapter
for Huey's built-in ``@periodic_task`` decorators.

Huey's periodic tasks are decorator-defined and live in the
process's ``huey._registry``. They cannot be created, edited, or
deleted at runtime - the storage is the Python source itself.

This adapter therefore implements only the read path
(``list_schedules`` / ``get_schedule``). Create and update raise
``NotImplementedError``; the remaining mutation methods return failed
command results. The dashboard hides those buttons via the capability
advertisement.
"""

from __future__ import annotations

import inspect
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from z4j_core.models import CommandResult, Schedule, ScheduleKind

from z4j_hueyperiodic.capabilities import DEFAULT_CAPABILITIES

logger = logging.getLogger("z4j.adapter.hueyperiodic.scheduler")

_NAME = "huey-periodic"


class HueyPeriodicAdapter:
    """Scheduler adapter for Huey periodic tasks.

    Args:
        huey: A live ``huey.api.Huey`` instance - same one passed
              to :class:`HueyEngineAdapter`.
        project_id: Optional project id used when minting Schedule
                    rows. Defaults to a deterministic placeholder
                    for local-only test setups.
    """

    name: str = _NAME

    def __init__(
        self,
        *,
        huey: Any,
        project_id: UUID | None = None,
    ) -> None:
        self.huey = huey
        self._project_id = project_id or uuid4()

    def connect_signals(self, sink: Any) -> None:
        return

    def disconnect_signals(self) -> None:
        return

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def list_schedules(self) -> list[Schedule]:
        out: list[Schedule] = []
        for task_class, validate_fn in _iter_periodic_tasks(self.huey):
            try:
                out.append(self._to_schedule(task_class, validate_fn))
            except Exception:
                logger.exception(
                    "z4j hueyperiodic: failed to map %r; skipping this authoritative snapshot",
                    getattr(task_class, "name", "?"),
                )
                raise
        return out

    async def get_schedule(self, schedule_id: str) -> Schedule | None:
        for s in await self.list_schedules():
            if str(s.id) == schedule_id or s.name == schedule_id:
                return s
        return None

    # ------------------------------------------------------------------
    # Write - none. Decorator-defined, source-controlled.
    # ------------------------------------------------------------------

    async def create_schedule(self, spec: Schedule) -> Schedule:
        raise NotImplementedError(
            "Huey periodic tasks are decorator-defined; edit your source and redeploy.",
        )

    async def update_schedule(
        self,
        schedule_id: str,
        spec: Schedule,
    ) -> Schedule:
        raise NotImplementedError(
            "Huey periodic tasks are decorator-defined; edit your source and redeploy.",
        )

    async def delete_schedule(self, schedule_id: str) -> CommandResult:
        return CommandResult(
            status="failed",
            error=(
                "Huey periodic tasks are decorator-defined; "
                "delete the @periodic_task in your source."
            ),
        )

    async def enable_schedule(self, schedule_id: str) -> CommandResult:
        return CommandResult(
            status="failed",
            error="Huey periodic tasks have no enable/disable toggle",
        )

    async def disable_schedule(self, schedule_id: str) -> CommandResult:
        return CommandResult(
            status="failed",
            error="Huey periodic tasks have no enable/disable toggle",
        )

    async def trigger_now(self, schedule_id: str) -> CommandResult:
        return CommandResult(
            status="failed",
            error=(
                "Huey periodic tasks have no trigger-now primitive; "
                "call the underlying task callable directly."
            ),
        )

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def capabilities(self) -> set[str]:
        return set(DEFAULT_CAPABILITIES)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _to_schedule(self, task_class: Any, validate_fn: Any) -> Schedule:
        now = datetime.now(UTC)
        name = getattr(task_class, "name", None) or task_class.__name__
        expression = _crontab_expression(validate_fn)
        sid = uuid4()
        return Schedule(
            id=sid,
            project_id=self._project_id,
            engine="huey",
            scheduler=self.name,
            name=name,
            task_name=name,
            kind=ScheduleKind.CRON,
            expression=expression,
            timezone="UTC",
            is_enabled=True,
            external_id=name,
            created_at=now,
            updated_at=now,
        )


def _iter_periodic_tasks(huey: Any):
    """Yield ``(task_class, validate_datetime)`` pairs.

    Huey 3.x exposes periodic tasks via ``registry.periodic_tasks``
    (a method or property returning instances) or
    ``registry._periodic_tasks`` (the underlying list). Huey 2.x
    used ``_periodic`` with ``(task_class, validate_fn)`` tuples.
    Try both for forward+backward compatibility.
    """
    registry = getattr(huey, "_registry", None)
    if registry is None:
        return

    # Huey 3.x: ``registry.periodic_tasks`` is a *list* of task
    # instances (not a method). Older code may also expose
    # ``_periodic_tasks`` for the same. Try both.
    candidates = list(
        getattr(registry, "periodic_tasks", None)
        or getattr(registry, "_periodic_tasks", None)
        or [],
    )
    for entry in candidates:
        validate_fn = getattr(entry, "validate_datetime", None) or getattr(
            entry, "validate_func", None
        )
        yield entry, validate_fn

    # Huey 2.x fallback.
    legacy = getattr(registry, "_periodic", None) or []
    for entry in legacy:
        if isinstance(entry, tuple) and len(entry) >= 2:
            yield entry[0], entry[1]
        else:
            yield entry, None


def _crontab_expression(validate_fn: Any) -> str:
    """Recover an equivalent five-field cron from Huey's validator closure."""
    target = getattr(validate_fn, "__func__", validate_fn)
    if not callable(target):
        raise TypeError("periodic task has no callable datetime validator")
    closure = inspect.getclosurevars(target)
    wrapped = closure.nonlocals.get("validate_datetime")
    if callable(wrapped):
        target = wrapped
        closure = inspect.getclosurevars(target)
    settings = closure.nonlocals.get("cron_settings")
    if not isinstance(settings, list) or len(settings) != 5:
        raise ValueError("periodic validator is not a Huey crontab closure")

    # Huey stores month, day, weekday, hour, minute. Cron renders the reverse
    # time fields: minute, hour, day, month, weekday.
    month, day, weekday, hour, minute = settings
    fields = (
        _cron_field(minute, range(60)),
        _cron_field(hour, range(24)),
        _cron_field(day, range(1, 32)),
        _cron_field(month, range(1, 13)),
        _cron_field(weekday, range(8)),
    )
    return " ".join(fields)


def _cron_field(values: Any, accepted: range) -> str:
    selected = sorted({int(value) for value in values})
    full = list(accepted)
    if selected == full:
        return "*"
    if not selected:
        raise ValueError("Huey crontab field matches no values")
    if len(selected) == 1:
        return str(selected[0])
    step = selected[1] - selected[0]
    if step > 1 and selected[0] == full[0] and selected == full[::step]:
        return f"*/{step}"
    return ",".join(str(value) for value in selected)


__all__ = ["HueyPeriodicAdapter"]
