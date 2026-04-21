# z4j-hueyperiodic

[![PyPI version](https://img.shields.io/pypi/v/z4j-hueyperiodic.svg)](https://pypi.org/project/z4j-hueyperiodic/)
[![Python](https://img.shields.io/pypi/pyversions/z4j-hueyperiodic.svg)](https://pypi.org/project/z4j-hueyperiodic/)
[![License](https://img.shields.io/pypi/l/z4j-hueyperiodic.svg)](https://github.com/z4jdev/z4j-hueyperiodic/blob/main/LICENSE)


z4j scheduler adapter for Huey's built-in `@periodic_task` decorator.

```python
from huey import RedisHuey, crontab
from z4j_huey import HueyEngineAdapter
from z4j_hueyperiodic import HueyPeriodicAdapter

huey = RedisHuey("myapp")

@huey.periodic_task(crontab(minute="*/5"))
def cleanup():
    ...

# In your z4j-bare bootstrap:
from z4j_bare import install_agent
install_agent(
    engines=[HueyEngineAdapter(huey=huey)],
    schedulers=[HueyPeriodicAdapter(huey=huey)],
)
```

## Capabilities

- ✅ List `@periodic_task` schedules
- ✅ Read individual schedule by id
- ❌ Create / update / delete - Huey periodic tasks are
  decorator-driven (compile-time), not runtime mutable. Edit the
  source and redeploy; this adapter intentionally raises
  `NotImplementedError` for those.
- ❌ Trigger-now - Huey doesn't expose a "fire this periodic now"
  primitive; users can call the underlying task callable directly.

Read-only by design.

## License

Apache 2.0 - see [LICENSE](LICENSE). This package is deliberately permissively licensed so that proprietary Django / Flask / FastAPI applications can import it without any license concerns.

## Links

- Homepage: <https://z4j.com>
- Documentation: <https://z4j.dev>
- Source: <https://github.com/z4jdev/z4j-hueyperiodic>
- Issues: <https://github.com/z4jdev/z4j-hueyperiodic/issues>
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Security: `security@z4j.com` (see [SECURITY.md](SECURITY.md))
