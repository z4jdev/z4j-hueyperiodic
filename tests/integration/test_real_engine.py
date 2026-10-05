"""The periodic adapter against a real consumer, on every supported Huey major.

A real ``huey.consumer.Consumer`` with its periodic scheduler enabled runs a
``@periodic_task``, and the adapter's inventory is compared with what Huey
actually ran: the schedule's name is the name of the task the scheduler
enqueued, and the cron expression is the one the decorator was given.

Storage follows the suite's convention: ``Z4J_HUEY_TEST_REDIS_URL`` selects a
real Redis (the gate's integration lane sets it), otherwise Huey's in-memory
storage. Nothing here skips: the case that needs the crontab syntax Huey 3.4
added is defined only where that syntax works, and a guard fails if the
detection stops tracking the installed release.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import threading
import time
import uuid
from datetime import datetime
from importlib.metadata import version
from typing import Any

import pytest

pytest.importorskip("huey")

pytestmark = pytest.mark.integration

from huey import MemoryHuey, RedisHuey, crontab  # noqa: E402
from huey import signals as huey_signals  # noqa: E402
from z4j_core.models import ScheduleKind  # noqa: E402
from z4j_hueyperiodic import HueyPeriodicAdapter  # noqa: E402

HUEY_VERSION = tuple(int(part) for part in version("huey").split(".")[:2])
#: Huey 3.4 made a stepped range (``0-30/10``) honour its step; before that the
#: step was ignored and the whole range matched.
HAS_STEPPED_RANGES = not crontab(minute="0-30/10")(datetime(2020, 1, 1, 0, 5))


def _make_huey() -> Any:
    name = f"z4jperiodic{uuid.uuid4().hex[:16]}"
    url = os.environ.get("Z4J_HUEY_TEST_REDIS_URL")
    if url:
        return RedisHuey(name, url=url)
    return MemoryHuey(name)


@contextlib.contextmanager
def _running_consumer(huey: Any):
    """A real consumer: one worker thread and the periodic scheduler thread."""
    consumer = huey.create_consumer(
        workers=1,
        periodic=True,
        initial_delay=0.01,
        backoff=1.0,
        max_delay=0.02,
        scheduler_interval=1,
        check_worker_health=False,
    )
    # Consumer.start() installs the process signal handlers a standalone
    # consumer wants. The test process keeps its own.
    names = ("SIGINT", "SIGTERM", "SIGHUP")
    saved = {
        number: signal.getsignal(number)
        for number in (getattr(signal, name, None) for name in names)
        if number is not None
    }
    try:
        consumer.start()
    finally:
        for number, handler in saved.items():
            signal.signal(number, handler)
    try:
        yield consumer
    finally:
        consumer.stop_flag.set()
        threads = [thread for _, thread in consumer.worker_threads] + [consumer.scheduler]
        for thread in threads:
            thread.join(10)
        alive = [thread.name for thread in threads if thread.is_alive()]
        with contextlib.suppress(Exception):
            huey.flush()
        pool = getattr(huey.storage, "pool", None)
        if pool is not None:
            pool.disconnect()
        assert not alive, f"consumer threads did not stop: {alive}"


@pytest.mark.asyncio
async def test_the_inventory_names_the_task_the_scheduler_actually_runs() -> None:
    huey = _make_huey()
    completed: list[str] = []
    ran = threading.Event()

    @huey.periodic_task(crontab())
    def heartbeat() -> None:
        return None

    @huey.periodic_task(crontab(minute="*/5", hour="3"))
    def nightly_sweep() -> None:
        return None

    @huey.task()
    def not_periodic() -> None:
        return None

    @huey.signal(huey_signals.SIGNAL_COMPLETE)
    def _record(_signal: str, task: Any, *_args: Any) -> None:
        completed.append(task.name)
        if task.name == "heartbeat":
            ran.set()

    adapter = HueyPeriodicAdapter(huey=huey)
    with _running_consumer(huey):
        deadline = time.monotonic() + 20
        while not ran.is_set():
            assert time.monotonic() < deadline, "the periodic task never ran"
            await asyncio.sleep(0.01)
        schedules = await adapter.list_schedules()

    by_name = {schedule.name: schedule for schedule in schedules}
    assert set(by_name) == {"heartbeat", "nightly_sweep"}
    assert "heartbeat" in completed

    heartbeat_schedule = by_name["heartbeat"]
    assert heartbeat_schedule.task_name == "heartbeat"
    assert heartbeat_schedule.external_id == "heartbeat"
    assert heartbeat_schedule.expression == "* * * * *"
    assert heartbeat_schedule.kind == ScheduleKind.CRON
    assert heartbeat_schedule.engine == "huey"
    assert heartbeat_schedule.scheduler == "huey-periodic"
    assert heartbeat_schedule.is_enabled is True
    assert by_name["nightly_sweep"].expression == "*/5 3 * * *"

    found = await adapter.get_schedule("nightly_sweep")
    assert found is not None
    assert found.expression == "*/5 3 * * *"
    assert adapter.capabilities() == {"list", "read"}


@pytest.mark.asyncio
async def test_the_crontab_forms_both_majors_accept_render_as_cron() -> None:
    huey = MemoryHuey(f"z4jperiodic{uuid.uuid4().hex[:16]}")

    @huey.periodic_task(crontab(minute="0", hour="*/6"))
    def six_hourly() -> None:
        return None

    @huey.periodic_task(crontab(minute="15,45", day_of_week="1-5"))
    def weekdays() -> None:
        return None

    @huey.periodic_task(crontab(minute="30", hour="2", day="1", month="3,9"))
    def twice_a_year() -> None:
        return None

    @huey.periodic_task(crontab(minute="0,30"))
    def half_hourly() -> None:
        return None

    expressions = {
        schedule.name: schedule.expression
        for schedule in await HueyPeriodicAdapter(huey=huey).list_schedules()
    }
    assert expressions == {
        "six_hourly": "0 */6 * * *",
        "weekdays": "15,45 * * * 1,2,3,4,5",
        "twice_a_year": "30 2 1 3,9 *",
        # A list that is exactly a step from the field's first value renders
        # as that step: the adapter recovers an equivalent expression, not the
        # decorator's spelling.
        "half_hourly": "*/30 * * * *",
    }


def test_the_stepped_range_case_exists_exactly_from_huey_3_4() -> None:
    assert ("test_stepped_and_wrapping_ranges_and_helpers_render_as_cron" in globals()) == (
        HUEY_VERSION >= (3, 4)
    )
    assert (HUEY_VERSION >= (3, 4)) == HAS_STEPPED_RANGES


if HAS_STEPPED_RANGES:

    @pytest.mark.asyncio
    async def test_stepped_and_wrapping_ranges_and_helpers_render_as_cron() -> None:
        """Huey 3.4 added stepped and wrap-around ranges and two helpers."""
        huey = MemoryHuey(f"z4jperiodic{uuid.uuid4().hex[:16]}")

        @huey.periodic_task(crontab(minute="0-30/10"))
        def stepped_range() -> None:
            return None

        @huey.periodic_task(crontab(minute="0", hour="22-2"))
        def overnight() -> None:
            return None

        @huey.periodic_task(crontab.hourly())
        def hourly() -> None:
            return None

        @huey.periodic_task(crontab.daily())
        def daily() -> None:
            return None

        expressions = {
            schedule.name: schedule.expression
            for schedule in await HueyPeriodicAdapter(huey=huey).list_schedules()
        }
        assert expressions == {
            "stepped_range": "0,10,20,30 * * * *",
            "overnight": "0 0,1,2,22,23 * * *",
            "hourly": "0 * * * *",
            "daily": "0 0 * * *",
        }
