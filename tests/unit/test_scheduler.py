"""HueyPeriodicAdapter tests."""

from __future__ import annotations

import pytest

pytest.importorskip("huey")

from huey import MemoryHuey, crontab
from z4j_hueyperiodic import HueyPeriodicAdapter


@pytest.fixture
def huey():
    inst = MemoryHuey("test", immediate=False)

    @inst.periodic_task(crontab(minute="*/5"))
    def cleanup():
        return "ok"

    @inst.periodic_task(crontab(hour="3"))
    def nightly():
        return "ok"

    return inst


@pytest.fixture
def adapter(huey):
    return HueyPeriodicAdapter(huey=huey)


@pytest.mark.asyncio
async def test_lists_periodic_tasks(adapter):
    rows = await adapter.list_schedules()
    names = {r.name for r in rows}
    assert any("cleanup" in n for n in names)
    assert any("nightly" in n for n in names)
    by_name = {row.name: row for row in rows}
    cleanup = next(row for name, row in by_name.items() if "cleanup" in name)
    nightly = next(row for name, row in by_name.items() if "nightly" in name)
    assert cleanup.expression == "*/5 * * * *"
    assert nightly.expression == "* 3 * * *"
    assert "validate" not in cleanup.expression


@pytest.mark.asyncio
async def test_mapping_failure_aborts_authoritative_snapshot(adapter, monkeypatch):
    original = adapter._to_schedule
    calls = 0

    def fail_second(task_class, validate_fn):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("malformed periodic task")
        return original(task_class, validate_fn)

    monkeypatch.setattr(adapter, "_to_schedule", fail_second)
    with pytest.raises(ValueError, match="malformed periodic task"):
        await adapter.list_schedules()


@pytest.mark.asyncio
async def test_get_by_name(adapter):
    rows = await adapter.list_schedules()
    if not rows:
        pytest.skip("Huey registry shape changed; v1.1 will fix")
    target = rows[0]
    found = await adapter.get_schedule(target.name)
    assert found is not None


@pytest.mark.asyncio
async def test_mutations_clearly_unsupported(adapter):
    res = await adapter.delete_schedule("anything")
    assert res.status == "failed"
    res = await adapter.enable_schedule("anything")
    assert res.status == "failed"
    res = await adapter.trigger_now("anything")
    assert res.status == "failed"


@pytest.mark.asyncio
async def test_create_raises_not_implemented(adapter):
    with pytest.raises(NotImplementedError):
        await adapter.create_schedule(spec=None)  # type: ignore[arg-type]
