"""z4j-hueyperiodic - scheduler adapter for Huey's @periodic_task."""

from __future__ import annotations

from z4j_hueyperiodic.scheduler import HueyPeriodicAdapter

try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("z4j-hueyperiodic")
except PackageNotFoundError:  # source checkout, no installed metadata
    from z4j_core.version import __version__  # type: ignore[no-redef]

__all__ = ["HueyPeriodicAdapter", "__version__"]
