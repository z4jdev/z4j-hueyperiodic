# z4j-hueyperiodic

[![PyPI version](https://img.shields.io/pypi/v/z4j-hueyperiodic.svg)](https://pypi.org/project/z4j-hueyperiodic/)
[![Python](https://img.shields.io/pypi/pyversions/z4j-hueyperiodic.svg)](https://pypi.org/project/z4j-hueyperiodic/)
[![License](https://img.shields.io/pypi/l/z4j-hueyperiodic.svg)](https://github.com/z4jdev/z4j-hueyperiodic/blob/main/LICENSE)

The Huey `@periodic_task` scheduler adapter for [z4j](https://z4j.com).

Surfaces registered `@periodic_task` decorators from your Huey app on
the dashboard's Schedules page as read-only inventory.

## Compatibility

- Huey 2.4+ and <4
- Python 3.11+

Full per-adapter matrix at <https://z4j.dev/reference/compatibility/>.

## What it ships

| Capability | Notes |
|---|---|
| List schedules | registered periodic tasks that the adapter can map |
| Read | by registered name |
| Boot inventory | full snapshot at agent connect; existing schedules show up without editing |

This adapter is **read-only** (`capabilities()` returns `{list, read}`).
Huey's periodic tasks are decorator-defined in your source (the
`@periodic_task` argument *is* the schedule), so create / update / delete /
enable / disable / trigger-now are all out of scope, those need a source
edit and deploy round-trip. The dashboard greys out the buttons it can't
honor.

## Install

```bash
pip install z4j-huey z4j-hueyperiodic
```

```python
import os

from huey import RedisHuey, crontab
from z4j_bare import install_agent
from z4j_huey import HueyEngineAdapter
from z4j_hueyperiodic import HueyPeriodicAdapter

huey = RedisHuey("myapp", url="redis://localhost")

@huey.periodic_task(crontab(minute="*/5"))
def cleanup():
    ...

install_agent(
    engines=[HueyEngineAdapter(huey=huey)],
    schedulers=[HueyPeriodicAdapter(huey=huey)],
    brain_url="https://brain.example.com",
    token="z4j_agent_...",
    project_id="my-project",
    hmac_secret=os.environ["Z4J_HMAC_SECRET"],
)
```

## Pairs with

- [`z4j-huey`](https://github.com/z4jdev/z4j-huey), engine adapter

## Reliability

- The adapter reads Huey's periodic-task registry during inventory snapshots;
  it installs no Huey hooks and does not alter decorator runtime behavior or
  schedule definitions.

## Documentation

Full docs at [z4j.dev/schedulers/huey-periodic/](https://z4j.dev/schedulers/huey-periodic/).

## License

Apache-2.0, see [LICENSE](LICENSE).

## Links

- Homepage: https://z4j.com
- Documentation: https://z4j.dev
- PyPI: https://pypi.org/project/z4j-hueyperiodic/
- Issues: https://github.com/z4jdev/z4j-hueyperiodic/issues
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Security: security@z4j.com (see [SECURITY.md](SECURITY.md))
