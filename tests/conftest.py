"""Suite configuration for z4j-hueyperiodic."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    # Huey before 2.5.1 reads the clock with ``datetime.utcnow()``, which
    # Python 3.12 deprecated. The repository turns warnings into errors and the
    # gate runs this suite on the declared Huey floor as well, where that
    # warning is Huey's own and says nothing about the adapter. Ignore exactly
    # that message when it is raised from inside Huey; everything else stays
    # fatal.
    config.addinivalue_line(
        "filterwarnings",
        "ignore:datetime.datetime.utcnow:DeprecationWarning:huey",
    )
